using System.Security.Claims;
using System.Text.Json;

namespace TripFlow.Backend;

internal static partial class DashboardEndpoints
{
    private static void MapPlanningEndpoints(RouteGroupBuilder card)
    {
        card.MapPost("/generation", StartGeneration).WithSummary("Запустить подбор или догенерацию")
            .Produces<TripCardView>(StatusCodes.Status202Accepted).ProducesValidationProblem()
            .ProducesProblem(StatusCodes.Status409Conflict).ProducesProblem(StatusCodes.Status502BadGateway)
            .ProducesProblem(StatusCodes.Status503ServiceUnavailable).ProducesProblem(StatusCodes.Status504GatewayTimeout);
        card.MapPut("/hotel", SelectHotel).WithSummary("Выбрать отель со снимком тарифа")
            .Produces<TripCardView>().ProducesValidationProblem();
        card.MapPut("/attractions", SelectAttractions).WithSummary("Сохранить выбранные достопримечательности")
            .Produces<TripCardView>().ProducesValidationProblem();
        card.MapPost("/budget", StartBudget).WithSummary("Запустить расчёт бюджета")
            .Produces<TripCardView>(StatusCodes.Status202Accepted).ProducesProblem(StatusCodes.Status409Conflict)
            .ProducesProblem(StatusCodes.Status502BadGateway).ProducesProblem(StatusCodes.Status503ServiceUnavailable)
            .ProducesProblem(StatusCodes.Status504GatewayTimeout);
    }

    private static async Task<IResult> StartGeneration(Guid dashboardId, Guid cardId, CardGenerationInput request,
        ClaimsPrincipal user, PostgresStore store, PythonTaskWorker worker, TimeProvider clock, CancellationToken cancellationToken)
    {
        var accountId = user.AccountId();
        var prepared = ChangeOwnCard(dashboardId, cardId, user, store, (_, card) =>
        {
            string[] keys = request.Target switch
            {
                "all" => ["hotels", "attractions"],
                "hotels" => ["hotels"],
                "attractions" => ["attractions"],
                _ => []
            };
            if (keys.Length == 0)
                return PlanningValidation("target", "Use all, hotels, or attractions.");
            var input = request with { Refinement = CleanOptional(request.Refinement) };
            if (input.Refinement?.Length > 2000)
                return PlanningValidation("refinement", "Use at most 2000 characters.");

            var now = clock.GetUtcNow();
            PythonTaskState.Expire(card, now);
            var active = card.PythonTasks.Where(task => task.Kind == PythonTask.Recommendations && !task.Finished);
            var existing = active.FirstOrDefault(task => task.Generation == input && task.CardVersion == card.Version);
            if (existing?.GenerationBatchId is Guid batchId)
                return Prepare(card.PythonTasks.Where(task => task.GenerationBatchId == batchId));
            if (existing is not null)
                return Prepare([existing]);
            if (active.Any(task => task.Targets.Keys.Any(keys.Contains)))
                return PlanningConflict("A requested target is already being searched.");

            var plan = card.Planning;
            var replacement = plan.Attractions.Items.Find(item => !item.NeedsReview && item.Id == input.ReplaceAttractionId
                && plan.AttractionIds.Contains(item.Id));
            if (input.ReplaceAttractionId is not null && (input.Target != "attractions" || replacement is null))
                return PlanningValidation("replaceAttractionId", "Use a currently selected attraction for its additional search.");

            var targets = new Dictionary<string, RecommendationTaskTarget>();
            foreach (var key in keys)
            {
                var queue = plan.Queue(key);
                var criteria = new SearchCriteria(RecommendationLimit(card, key, replacement), input.Refinement);
                if (queue.HasMore == false && queue.LastCompletedSearch == criteria)
                    return PlanningConflict("Search is exhausted for a requested target. Change its refinement or limit.");
                var exclusions = queue.Items.Where(item => !item.NeedsReview).Select(item => item.Candidate.ObjectId)
                    .Distinct(StringComparer.Ordinal).ToArray();
                var count = key == "hotels" ? 3 : 4;
                targets.Add(key, new(count, criteria, exclusions));
            }
            if (!worker.IsConfigured)
                return PythonApiClient.Unavailable();

            var generationBatchId = Guid.NewGuid();
            var tasks = new List<PythonTask>();
            foreach (var (key, target) in targets)
            {
                var taskId = Guid.NewGuid();
                var body = new PythonRecommendationRequest(taskId, card.Trip, key, target.Count,
                    target.Criteria?.MaxTotalRub, target.Criteria?.Refinement, target.Exclusions ?? []);
                tasks.Add(CreateTask(card, taskId, PythonTask.Recommendations, now, worker.Deadline(now), body,
                    input, generationBatchId, new() { [key] = target }));
                plan.Queue(key).Start(taskId);
            }
            return Prepare(tasks);
        });
        return await SubmitPrepared(prepared, dashboardId, cardId, accountId, store, worker, cancellationToken);
    }

    private static IResult SelectHotel(Guid dashboardId, Guid cardId, HotelSelectionInput request,
        ClaimsPrincipal user, PostgresStore store) =>
        ChangeOwnCard(dashboardId, cardId, user, store, (_, card) =>
        {
            var plan = card.Planning;
            if (request.HotelId is Guid id && !plan.Hotels.Items.Any(item => item.Id == id && !item.NeedsReview))
                return PlanningValidation("hotelId", "Select an available hotel variant for this card.");
            if (plan.HotelId != request.HotelId)
            {
                plan.HotelId = request.HotelId;
                CardInputsChanged(card);
                plan.Hotels.Items.RemoveAll(item => item.NeedsReview);
            }
            return Results.Ok(CardView(card, user.AccountId(), includePlanning: true));
        });

    private static IResult SelectAttractions(Guid dashboardId, Guid cardId, AttractionSelectionInput request,
        ClaimsPrincipal user, PostgresStore store) =>
        ChangeOwnCard(dashboardId, cardId, user, store, (_, card) =>
        {
            if (request.AttractionIds is not { Length: <= 100 } ids || ids.Distinct().Count() != ids.Length)
                return PlanningValidation("attractionIds", "Provide a list of up to 100 distinct attraction IDs.");

            var plan = card.Planning;
            if (ids.Any(id => !plan.Attractions.Items.Any(item => item.Id == id && !item.NeedsReview)))
                return PlanningValidation("attractionIds", "Select only available attraction variants for this card.");
            if (!plan.AttractionIds.SequenceEqual(ids))
            {
                plan.AttractionIds = [.. ids];
                CardInputsChanged(card);
                plan.Attractions.Items.RemoveAll(item => item.NeedsReview);
            }
            return Results.Ok(CardView(card, user.AccountId(), includePlanning: true));
        });

    private static async Task<IResult> StartBudget(Guid dashboardId, Guid cardId, ClaimsPrincipal user,
        PostgresStore store, PythonTaskWorker worker, TimeProvider clock, CancellationToken cancellationToken)
    {
        var accountId = user.AccountId();
        var prepared = ChangeOwnCard(dashboardId, cardId, user, store, (_, card) =>
        {
            var now = clock.GetUtcNow();
            PythonTaskState.Expire(card, now);
            var plan = card.Planning;
            var hotel = plan.Hotels.Items.Find(item => item.Id == plan.HotelId);
            var attractions = plan.AttractionIds.Select(id => plan.Attractions.Items.Find(item => item.Id == id)).ToArray();
            if (hotel?.NeedsReview == true || attractions.Any(item => item is null or { NeedsReview: true })
                || (plan.HotelId is not null && hotel is null))
                return PlanningConflict("Update or remove the selections from the previous trip parameters.");
            var existing = card.PythonTasks.Find(task => task.Id == plan.Budget.TaskId && !task.Finished);
            if (existing is not null)
                return Prepare([existing]);
            if (!worker.IsConfigured)
                return PythonApiClient.Unavailable();

            var selectedHotel = hotel is null ? null : new PythonSelectedHotel(hotel.Candidate.ObjectId,
                PlanningBudget.HotelPrice(hotel.Candidate.Price));
            var taskId = Guid.NewGuid();
            var request = new PythonBudgetRequest(taskId, card.Trip, selectedHotel, attractions.Select(item =>
                new PythonSelectedAttraction(item!.Candidate.ObjectId, PlanningBudget.AdmissionPrice(item.Candidate.Price))).ToArray());
            var task = CreateTask(card, taskId, PythonTask.Budget, now, worker.Deadline(now), request);
            plan.Budget = new BudgetState { Status = PlanningStatus.Pending, TaskId = taskId };
            return Prepare([task]);
        });
        return await SubmitPrepared(prepared, dashboardId, cardId, accountId, store, worker, cancellationToken);
    }

    private static PythonTask CreateTask(TripCard card, Guid id, string kind, DateTimeOffset now,
        DateTimeOffset deadline, object body, CardGenerationInput? generation = null,
        Guid? batchId = null, Dictionary<string, RecommendationTaskTarget>? targets = null)
    {
        var task = new PythonTask
        {
            Id = id, CardId = card.Id, Kind = kind, CardVersion = card.Version, Deadline = deadline, NextAttemptAt = now,
            Generation = generation, GenerationBatchId = batchId,
            Payload = JsonSerializer.SerializeToElement(body, PythonApiClient.JsonOptions), Targets = targets ?? []
        };
        card.PythonTasks.Add(task);
        return task;
    }

    private static IResult Prepare(IEnumerable<PythonTask> tasks) => Results.Ok(tasks.ToArray());

    private static async Task<IResult> SubmitPrepared(IResult prepared, Guid dashboardId, Guid cardId, Guid accountId,
        PostgresStore store, PythonTaskWorker worker, CancellationToken cancellationToken)
    {
        if (prepared is not IValueHttpResult { Value: PythonTask[] tasks })
            return prepared;
        var attempts = await Task.WhenAll(tasks.Select(task => worker.Submit(task, cancellationToken)));
        return store.Read<IResult>(data =>
        {
            var card = FindCard(data, dashboardId, cardId, accountId, includeTasks: false);
            if (card is null)
                return Results.NotFound();
            if (card.Version != tasks[0].CardVersion)
                return PlanningConflict("The task inputs have changed.");
            if (attempts.Any(attempt => attempt.Status == StatusCodes.Status202Accepted))
                return Results.Accepted(value: CardView(card, accountId, includePlanning: true));

            return Results.Problem(statusCode: attempts[0].Status, title: attempts[0].Error?.Message
                ?? "Python acceptance could not be confirmed. The backend will retry until the deadline.",
                extensions: new Dictionary<string, object?>
                {
                    ["taskId"] = tasks[0].Id,
                    ["error"] = attempts[0].Error
                });
        });
    }

    private static long? RecommendationLimit(TripCard card, string target, CandidateView? replacement)
    {
        var budget = card.Planning.Budget.Summary;
        if (budget is not { Complete: true, IsLowerBound: false })
            return null;
        var released = target == "hotels" ? budget.AccommodationRub ?? 0
            : replacement is null ? 0 : PlanningBudget.AdmissionTotal(
                PlanningBudget.AdmissionPrice(replacement.Candidate.Price), card.Trip.Travelers) ?? 0;
        return Math.Max(0, card.Trip.BudgetRub - (budget.TotalRub - released));
    }

    private static void CardInputsChanged(TripCard card)
    {
        card.Version++;
        foreach (var task in card.PythonTasks.Where(task => !task.Finished))
            task.Finished = true;
        card.Planning.Hotels.Cancel();
        card.Planning.Attractions.Cancel();
        card.Planning.InvalidateBudget();
    }

    private static IResult PlanningValidation(string field, string message) =>
        Results.ValidationProblem(new Dictionary<string, string[]> { [field] = [message] });

    private static IResult PlanningConflict(string title) => Results.Problem(statusCode: 409, title: title);
}
