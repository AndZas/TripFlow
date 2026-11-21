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
        ClaimsPrincipal user, FileStore store, PythonApiClient python, TimeProvider clock, CancellationToken cancellationToken)
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
            if (existing is not null)
                return Prepare(existing, card, accountId);
            if (active.Any(task => task.Targets.Keys.Any(keys.Contains)))
                return PlanningConflict("A requested target is already being searched.");

            var plan = card.Planning;
            var replacement = plan.Attractions.Items.Find(item => !item.NeedsReview && item.Id == input.ReplaceAttractionId
                && plan.AttractionIds.Contains(item.Id));
            if (input.ReplaceAttractionId is not null && (input.Target != "attractions" || replacement is null))
                return PlanningValidation("replaceAttractionId", "Use a currently selected attraction for its additional search.");

            var taskId = Guid.NewGuid();
            var targets = new Dictionary<string, RecommendationTaskTarget>();
            var outgoing = new Dictionary<string, RecommendationRequestTarget>();
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
                outgoing.Add(key, new(count, criteria.MaxTotalRub, criteria.Refinement, exclusions));
            }
            if (!python.IsConfigured)
                return PythonApiClient.Unavailable();

            var task = CreateTask(card, taskId, PythonTask.Recommendations, python.Deadline(now),
                new { taskId, card.Trip, Targets = outgoing }, input, targets);
            foreach (var key in keys)
                plan.Queue(key).Start(taskId);
            return Prepare(task, card, accountId);
        });
        return await SubmitPrepared(prepared, store, python, cancellationToken);
    }

    private static IResult SelectHotel(Guid dashboardId, Guid cardId, HotelSelectionInput request,
        ClaimsPrincipal user, FileStore store) =>
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
        ClaimsPrincipal user, FileStore store) =>
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
        FileStore store, PythonApiClient python, TimeProvider clock, CancellationToken cancellationToken)
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
                return Prepare(existing, card, accountId);
            if (!python.IsConfigured)
                return PythonApiClient.Unavailable();

            var selectedHotel = hotel is null ? null : new PythonSelectedHotel(hotel.Candidate.ObjectId,
                PlanningBudget.HotelPrice(hotel.Candidate.Price), hotel.Candidate.Tariff ?? new(null, []));
            var taskId = Guid.NewGuid();
            var request = new PythonBudgetRequest(taskId, card.Trip, selectedHotel, attractions.Select(item =>
                new PythonSelectedAttraction(item!.Candidate.ObjectId, PlanningBudget.AdmissionPrice(item.Candidate.Price))).ToArray());
            var task = CreateTask(card, taskId, PythonTask.Budget, python.Deadline(now), request);
            plan.Budget = new BudgetState { Status = PlanningStatus.Pending, TaskId = taskId };
            return Prepare(task, card, accountId);
        });
        return await SubmitPrepared(prepared, store, python, cancellationToken);
    }

    private static PythonTask CreateTask(TripCard card, Guid id, string kind, DateTimeOffset deadline, object body,
        CardGenerationInput? generation = null, Dictionary<string, RecommendationTaskTarget>? targets = null)
    {
        var task = new PythonTask
        {
            Id = id, Kind = kind, CardVersion = card.Version, Deadline = deadline, Generation = generation,
            Payload = JsonSerializer.SerializeToElement(body, PythonApiClient.JsonOptions), Targets = targets ?? []
        };
        card.PythonTasks.Add(task);
        return task;
    }

    private sealed record PreparedTask(PythonTask Task, TripCardView CardView, Guid AccountId);

    private static IResult Prepare(PythonTask task, TripCard card, Guid accountId) =>
        Results.Ok(new PreparedTask(task, CardView(card, accountId, includePlanning: true), accountId));

    private static async Task<IResult> SubmitPrepared(IResult prepared, FileStore store,
        PythonApiClient python, CancellationToken cancellationToken)
    {
        if (prepared is not IValueHttpResult { Value: PreparedTask pending })
            return prepared;
        if (pending.Task.Accepted)
            return Results.Accepted(value: pending.CardView);
        return await python.Submit(pending.Task, store,
            card => CardView(card, pending.AccountId, includePlanning: true), cancellationToken);
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
