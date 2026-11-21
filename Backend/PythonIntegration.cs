using System.Net;
using System.Net.Http.Json;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace TripFlow.Backend;

internal sealed record PythonApiSettings
{
    public string? BaseUrl { get; init; }
    public string? ApiKey { get; init; }
    public string? CallbackKey { get; init; }
    public int TaskTimeoutSeconds { get; init; } = 300;
}

internal sealed class PythonApiClient(HttpClient http, PythonApiSettings settings, IWebHostEnvironment environment,
    TimeProvider clock)
{
    internal static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);
    private Uri? BaseUri => Uri.TryCreate(settings.BaseUrl, UriKind.Absolute, out var uri)
        && uri.UserInfo.Length == 0 && uri.Query.Length == 0 && uri.Fragment.Length == 0
        && (uri.Scheme == Uri.UriSchemeHttps
            || (environment.IsDevelopment() && uri.IsLoopback && uri.Scheme == Uri.UriSchemeHttp))
        ? uri
        : null;

    public bool IsConfigured => BaseUri is not null && !string.IsNullOrWhiteSpace(settings.ApiKey)
        && !string.IsNullOrWhiteSpace(settings.CallbackKey);

    public DateTimeOffset Deadline(DateTimeOffset now) => now.AddSeconds(Math.Clamp(settings.TaskTimeoutSeconds, 1, 86400));

    public static IResult Unavailable() => Results.Problem(statusCode: 503, title: "Python integration is unavailable.");

    public async Task<IResult> Submit(PythonTask task, FileStore store, Func<TripCard, object> cardView,
        CancellationToken cancellationToken)
    {
        if (!IsConfigured)
            return Unavailable();

        var url = new Uri(BaseUri!.AbsoluteUri.TrimEnd('/') + "/v1/" + task.Kind);
        using var request = new HttpRequestMessage(HttpMethod.Post, url)
        {
            Content = new StringContent(JsonSerializer.Serialize(task.Payload, JsonOptions), Encoding.UTF8, "application/json")
        };
        request.Headers.Add("X-API-Key", settings.ApiKey);

        var accepted = false;
        ErrorDetail? rejection = null;
        var failureStatus = StatusCodes.Status502BadGateway;
        try
        {
            using var response = await http.SendAsync(request, cancellationToken);
            if (response.StatusCode == HttpStatusCode.Accepted)
            {
                var receipt = await response.Content.ReadFromJsonAsync<UpstreamAcceptance>(JsonOptions, cancellationToken);
                accepted = receipt?.TaskId == task.Id && receipt.Status == "accepted";
            }
            else if ((int)response.StatusCode is >= 400 and < 500 and not (408 or 429))
            {
                rejection = new ErrorDetail("PYTHON_REJECTED", "Python rejected the task.");
                var body = await response.Content.ReadFromJsonAsync<UpstreamError>(JsonOptions, cancellationToken);
                if ((body?.TaskId is null || body.TaskId == task.Id) && ErrorDetail.IsValid(body?.Error))
                    rejection = body!.Error;
            }
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            failureStatus = StatusCodes.Status504GatewayTimeout;
        }
        catch (HttpRequestException)
        {
            // The saved task is reused if the caller retries after an uncertain acceptance.
        }
        catch (JsonException)
        {
            // A malformed response cannot confirm acceptance or replace a known rejection.
        }

        var now = clock.GetUtcNow();
        var result = store.Change(data =>
        {
            if (PythonTaskState.Find(data, task.Id) is not { } match)
                return Results.NotFound();
            if (match.Task.CardVersion != match.Card.Version)
                return Results.Problem(statusCode: 409, title: "The task inputs have changed.");
            if (match.Task.CallbackReceived)
                return Results.Accepted(value: cardView(match.Card));
            if (match.Task.Finished)
                return Results.Problem(statusCode: 409, title: "This task already ended.");
            if (match.Task.Deadline <= now)
            {
                PythonTaskState.Fail(match.Card, match.Task, PythonTaskState.TimedOut);
                failureStatus = StatusCodes.Status504GatewayTimeout;
                return Results.NoContent();
            }
            if (match.Task.Accepted || accepted)
            {
                match.Task.Accepted = true;
                return Results.Accepted(value: cardView(match.Card));
            }
            if (rejection is not null)
            {
                PythonTaskState.Fail(match.Card, match.Task, rejection);
                return Results.NoContent();
            }
            return SubmissionError(failureStatus, task.Id, "Python acceptance could not be confirmed. Retry the same request.");
        });
        return result is IStatusCodeHttpResult { StatusCode: 204 }
            ? SubmissionError(failureStatus, task.Id,
                failureStatus == 504 ? PythonTaskState.TimedOut.Message : "Python rejected the task.")
            : result;
    }

    private static IResult SubmissionError(int status, Guid taskId, string title) =>
        Results.Problem(statusCode: status, title: title,
            extensions: new Dictionary<string, object?> { ["taskId"] = taskId });

    private sealed record UpstreamAcceptance(Guid TaskId, string? Status);
    private sealed record UpstreamError(Guid? TaskId, ErrorDetail? Error);
}

internal static class PythonTaskState
{
    public static readonly ErrorDetail TimedOut = new("TASK_TIMEOUT", "The Python result did not arrive before the deadline.");

    public static (TripCard Card, PythonTask Task)? Find(StoreData data, Guid taskId)
    {
        foreach (var card in data.Dashboards.SelectMany(dashboard => dashboard.Cards))
        {
            var task = card.PythonTasks.Find(task => task.Id == taskId);
            if (task is not null)
                return (card, task);
        }
        return null;
    }

    public static bool HasExpired(TripCard card, DateTimeOffset now) =>
        card.PythonTasks.Any(task => !task.Finished && task.Deadline <= now);

    public static void Expire(TripCard card, DateTimeOffset now)
    {
        foreach (var task in card.PythonTasks.Where(task => !task.Finished && task.Deadline <= now))
            Fail(card, task, TimedOut);
    }

    public static void Fail(TripCard card, PythonTask task, ErrorDetail error)
    {
        task.Finished = true;
        if (task.CardVersion != card.Version)
            return;
        if (task.Kind == PythonTask.Budget && card.Planning.Budget.TaskId == task.Id)
        {
            card.Planning.Budget = new BudgetState { Status = PlanningStatus.Failed, TaskId = task.Id, Error = error };
        }
        else if (task.Kind == PythonTask.Recommendations)
        {
            foreach (var key in task.Targets.Keys)
            {
                var queue = card.Planning.Queue(key);
                if (queue.TaskId != task.Id)
                    continue;
                queue.Status = PlanningStatus.Failed;
                queue.Error = error;
                queue.HasMore = null;
            }
        }
    }
}

internal static class PythonEventEndpoints
{
    public static void MapPythonEvents(this WebApplication app) =>
        app.MapPost("/internal/tripflow/events", ReceiveEvent)
            .WithTags("Python API").WithSummary("Принять итог подбора или расчёта бюджета")
            .Accepts<JsonElement>("application/json")
            .Produces(StatusCodes.Status204NoContent)
            .ProducesProblem(StatusCodes.Status400BadRequest).ProducesProblem(StatusCodes.Status401Unauthorized)
            .ProducesProblem(StatusCodes.Status404NotFound).Produces(StatusCodes.Status415UnsupportedMediaType);

    private static async Task<IResult> ReceiveEvent(HttpRequest request, PythonApiSettings settings,
        FileStore store, TimeProvider clock, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(settings.CallbackKey) ||
            !request.Headers.TryGetValue("X-Callback-Key", out var keys) || keys.Count != 1 ||
            !CryptographicOperations.FixedTimeEquals(Encoding.UTF8.GetBytes(keys[0]!),
                Encoding.UTF8.GetBytes(settings.CallbackKey)))
            return Results.Unauthorized();
        if (!request.HasJsonContentType())
            return Results.StatusCode(StatusCodes.Status415UnsupportedMediaType);

        JsonElement payload;
        PythonEvent? message;
        try
        {
            payload = await request.ReadFromJsonAsync<JsonElement>(cancellationToken);
            message = payload.Deserialize<PythonEvent>(PythonApiClient.JsonOptions);
        }
        catch (JsonException)
        {
            return InvalidEvent("Invalid callback JSON.");
        }
        if (string.IsNullOrWhiteSpace(message?.TaskId) || string.IsNullOrWhiteSpace(message.Event))
            return InvalidEvent("An event requires a task ID and event type.");
        if (!Guid.TryParseExact(message.TaskId, "D", out var taskId))
            return Results.NotFound();

        var now = clock.GetUtcNow();
        return store.Change(data =>
        {
            if (PythonTaskState.Find(data, taskId) is not { } match)
                return Results.NotFound();
            var (card, task) = match;
            if (task.CallbackReceived)
                return Results.NoContent();
            if (!task.Finished && task.Deadline <= now)
                PythonTaskState.Fail(card, task, PythonTaskState.TimedOut);
            if (task.Finished || task.CardVersion != card.Version)
            {
                task.CallbackReceived = true;
                task.Finished = true;
                return Results.NoContent();
            }

            string? error;
            try
            {
                error = (task.Kind, message.Event) switch
                {
                    (PythonTask.Recommendations, "recommendations.finished") => ApplyRecommendations(card, task,
                        payload.Deserialize<RecommendationsFinished>(PythonApiClient.JsonOptions)!),
                    (PythonTask.Budget, "budget.finished") => ApplyBudget(card, task,
                        payload.Deserialize<BudgetFinished>(PythonApiClient.JsonOptions)!),
                    _ => "The event type does not match the task."
                };
            }
            catch (JsonException)
            {
                return InvalidEvent("Callback fields do not match the event schema.");
            }
            if (error is not null)
                return InvalidEvent(error);
            task.Accepted = true;
            task.CallbackReceived = true;
            task.Finished = true;
            return Results.NoContent();
        });
    }

    private static string? ApplyRecommendations(TripCard card, PythonTask task, RecommendationsFinished message)
    {
        if (message.Results is not { } results || results.Count != task.Targets.Count)
            return "The result must include every requested target.";

        foreach (var (key, target) in task.Targets)
        {
            if (!results.TryGetValue(key, out var result) || result?.Items is not { } candidates ||
                candidates.Length > target.Count || !ValidTargetResult(result, candidates.Length))
                return "Invalid result for a recommendation target.";

            var queue = card.Planning.Queue(key);
            queue.Status = result.Status;
            queue.Error = result.Error;
            queue.HasMore = result.HasMore;
            if (result.Status == PlanningStatus.Failed)
                continue;

            var isHotel = key == "hotels";
            var excluded = (target.Exclusions ?? []).Concat(queue.Items.Where(item => !item.NeedsReview)
                .Select(item => item.Candidate.ObjectId)).ToHashSet(StringComparer.Ordinal);
            foreach (var candidate in candidates)
            {
                if (!ValidCandidate(candidate, isHotel))
                    return "Invalid candidate in the result.";
                if (WithinLimit(candidate, isHotel, target.Criteria?.MaxTotalRub, card.Trip.Travelers)
                    && excluded.Add(candidate.ObjectId))
                    queue.Items.Add(new CandidateView(Guid.NewGuid(), candidate));
            }
            queue.LastCompletedSearch = target.Criteria;
        }
        return null;
    }

    private static bool ValidTargetResult(RecommendationResult result, int count) =>
        result.Status switch
        {
            PlanningStatus.Succeeded => result.Error is null,
            PlanningStatus.Partial => count > 0 && (result.Error is null || ErrorDetail.IsValid(result.Error)),
            PlanningStatus.Failed => count == 0 && result.HasMore is null && ErrorDetail.IsValid(result.Error),
            _ => false
        };

    private static string? ApplyBudget(TripCard card, PythonTask task, BudgetFinished message)
    {
        if (message.Status == PlanningStatus.Failed)
        {
            if (message.Expenses is not null || !ErrorDetail.IsValid(message.Error))
                return "A failed budget event requires an error and null expenses.";
            PythonTaskState.Fail(card, task, message.Error!);
            return null;
        }
        if (message.Status != PlanningStatus.Succeeded || message.Error is not null || message.Expenses is not
            { FoodTotalRub: >= 0, LocalTransportTotalRub: >= 0, OtherExpensesTotalRub: >= 0, ReserveTotalRub: >= 0 } expenses)
            return "A successful budget event requires four nonnegative expenses.";
        try
        {
            card.Planning.Budget = new BudgetState
            {
                TaskId = task.Id, Status = PlanningStatus.Succeeded, Summary = PlanningBudget.Calculate(task, expenses)
            };
            return null;
        }
        catch (OverflowException)
        {
            return "The budget cannot be represented in whole rubles.";
        }
    }

    private static bool ValidCandidate(TripCandidate? candidate, bool isHotel)
    {
        if (candidate is null || string.IsNullOrWhiteSpace(candidate.ObjectId) || string.IsNullOrWhiteSpace(candidate.Name)
            || !IsHttps(candidate.SourceUrl) || (candidate.ImageUrl is not null && !IsHttps(candidate.ImageUrl))
            || candidate.Coordinates is { } point && (point.Latitude is < -90 or > 90 || point.Longitude is < -180 or > 180))
            return false;

        if (isHotel)
            return (candidate.Stars is null or >= 1 and <= 5)
                && (candidate.Price.ValueKind == JsonValueKind.Null ||
                    candidate.Price.ValueKind == JsonValueKind.Number && candidate.Price.TryGetInt64(out var amount) && amount >= 0)
                && (candidate.Tariff is null || ValidTariff(candidate.Tariff));
        return candidate.Tariff is null && candidate.Price.ValueKind switch
        {
            JsonValueKind.Null => true,
            JsonValueKind.Object => PlanningBudget.AdmissionPrice(candidate.Price) is
                { AmountRub: >= 0, Basis: "group_admission" or "person_admission", Kind: "source" or "estimate" } price
                && (price.SourceUrl is null || IsHttps(price.SourceUrl)),
            _ => false
        };
    }

    private static bool ValidTariff(TariffSnapshot tariff) => tariff.IncludedServices is not null
        && tariff.IncludedServices.All(service => service is not null && !string.IsNullOrWhiteSpace(service.Service)
            && service.Status is "confirmed" or "contradicted" or "unknown"
            && (service.SourceUrl is null ? service.Status != "confirmed" : IsHttps(service.SourceUrl)));

    private static bool WithinLimit(TripCandidate candidate, bool isHotel, long? limit, int travelers)
    {
        if (limit is null)
            return true;
        if (isHotel)
            return PlanningBudget.HotelPrice(candidate.Price) is not long amount || amount <= limit;
        var admission = PlanningBudget.AdmissionPrice(candidate.Price);
        return admission is null || admission.AmountRub <= (admission.Basis == "person_admission" ? limit / travelers : limit);
    }

    private static bool IsHttps(string? url) => Uri.TryCreate(url, UriKind.Absolute, out var uri)
        && uri.Scheme == Uri.UriSchemeHttps && !string.IsNullOrWhiteSpace(uri.Host);

    private static IResult InvalidEvent(string title) => Results.Problem(statusCode: 400, title: title);

    private sealed record PythonEvent(string? TaskId, string? Event);
    private sealed record RecommendationsFinished(Dictionary<string, RecommendationResult?>? Results);
    private sealed record RecommendationResult(string Status, TripCandidate[]? Items,
        [property: JsonRequired] bool? HasMore, ErrorDetail? Error);
    private sealed record BudgetFinished(string? Status, [property: JsonRequired] BudgetExpenses? Expenses, ErrorDetail? Error);
}
