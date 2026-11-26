using System.Net;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.EntityFrameworkCore;

namespace TripFlow.Backend;

internal sealed record PythonApiSettings
{
    private const string LocalKeyName = "API_TRIPFLOW";

    public string? BaseUrl { get; init; } = "https://tripflow-api-x1p5.onrender.com";
    public string? ApiKey { get; init; }
    public int TaskTimeoutSeconds { get; init; } = 300;

    public static PythonApiSettings Load(IConfiguration configuration, string contentRoot)
    {
        var settings = configuration.GetSection("PythonApi").Get<PythonApiSettings>() ?? new();
        var key = settings.ApiKey;
        if (string.IsNullOrWhiteSpace(key))
            key = configuration[LocalKeyName];
        if (string.IsNullOrWhiteSpace(key))
            key = LocalEnvironment.ReadValue(Path.Combine(contentRoot, ".env"), LocalKeyName);
        return settings with { ApiKey = key?.Trim() };
    }
}

internal sealed record PythonResponse(int Status, TimeSpan Delay, string? PollPath = null,
    JsonElement? Result = null, ErrorDetail? Error = null);

internal sealed class PythonApiClient(IHttpClientFactory clients, PythonApiSettings settings,
    IWebHostEnvironment environment, TimeProvider clock)
{
    public const string HttpClientName = "PythonApi";
    internal static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    private Uri? BaseUri => Uri.TryCreate(settings.BaseUrl, UriKind.Absolute, out var uri)
        && uri.UserInfo.Length == 0 && uri.Query.Length == 0 && uri.Fragment.Length == 0
        && (uri.Scheme == Uri.UriSchemeHttps
            || (environment.IsDevelopment() && uri.IsLoopback && uri.Scheme == Uri.UriSchemeHttp))
        ? uri
        : null;

    public bool IsConfigured => BaseUri is not null && !string.IsNullOrWhiteSpace(settings.ApiKey);

    public DateTimeOffset Deadline(DateTimeOffset now) =>
        now.AddSeconds(Math.Clamp(settings.TaskTimeoutSeconds, 1, 86400));

    public static IResult Unavailable() => Results.Problem(statusCode: 503, title: "Python integration is unavailable.");

    public static string TaskPath(Guid taskId) => $"/v1/tasks/{taskId:D}";

    public async Task<PythonResponse> Send(PythonTask task, CancellationToken cancellationToken)
    {
        var baseUri = BaseUri!;
        // Tasks saved by the old client do not have a Location. Try reading them by ID.
        var pollPath = task.PollPath ?? (task.NextAttemptAt is null ? TaskPath(task.Id) : null);
        var polling = pollPath is not null;
        var url = polling
            ? ResolvePollLocation(baseUri, pollPath, task.Id)
            : new Uri(baseUri.AbsoluteUri.TrimEnd('/') + "/v1/" + task.Kind);
        if (url is null)
            return InvalidResult();

        using var http = clients.CreateClient(HttpClientName);
        using var request = new HttpRequestMessage(polling ? HttpMethod.Get : HttpMethod.Post, url);
        if (!polling)
            request.Content = new StringContent(JsonSerializer.Serialize(task.Payload, JsonOptions), Encoding.UTF8, "application/json");
        request.Headers.Add("X-API-Key", settings.ApiKey);

        try
        {
            using var response = await http.SendAsync(request, cancellationToken);
            var retryAfter = response.Headers.RetryAfter;
            var delay = retryAfter?.Delta ?? (retryAfter?.Date - clock.GetUtcNow());
            var normalDelay = delay ?? TimeSpan.FromSeconds(2);
            var retryDelay = delay ?? TimeSpan.FromSeconds(5);
            var status = (int)response.StatusCode;

            if (!polling && response.StatusCode == HttpStatusCode.Accepted)
            {
                var receipt = await response.Content.ReadFromJsonAsync<UpstreamAcceptance>(JsonOptions, cancellationToken);
                var location = ResolvePollLocation(url, response.Headers.Location?.OriginalString, task.Id);
                if (receipt?.TaskId == task.Id && receipt.Status == "accepted" && location is not null)
                    return new(202, normalDelay, PollPath: location.AbsolutePath);
                return new(502, retryDelay);
            }

            if (polling && response.StatusCode == HttpStatusCode.OK)
            {
                var body = await response.Content.ReadFromJsonAsync<UpstreamTaskStatus>(JsonOptions, cancellationToken);
                if (body?.TaskId != task.Id)
                    return InvalidResult();
                return body.Status switch
                {
                    "pending" when body.Result is null => new(202, normalDelay, PollPath: pollPath),
                    "completed" when body.Result is { ValueKind: JsonValueKind.Object } => new(202, normalDelay, pollPath, body.Result),
                    _ => InvalidResult()
                };
            }

            if (status is >= 400 and < 500 and not (408 or 429))
                return new(502, TimeSpan.Zero, Error: await ReadRejection(response, task.Id, polling, cancellationToken));
            return new(status is 408 or 504 ? 504 : 502, retryDelay);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return new(504, TimeSpan.FromSeconds(5));
        }
        catch (HttpRequestException)
        {
            return new(502, TimeSpan.FromSeconds(5));
        }
        catch (JsonException)
        {
            return polling ? InvalidResult() : new(502, TimeSpan.FromSeconds(5));
        }
    }

    private static Uri? ResolvePollLocation(Uri source, string? location, Guid taskId)
    {
        if (!Uri.TryCreate(location, UriKind.Relative, out var relative)
            || !Uri.TryCreate(source, relative, out var uri)
            || uri.GetLeftPart(UriPartial.Authority) != source.GetLeftPart(UriPartial.Authority)
            || uri.UserInfo.Length > 0 || uri.Query.Length > 0 || uri.Fragment.Length > 0
            || !uri.AbsolutePath.EndsWith(TaskPath(taskId), StringComparison.Ordinal))
            return null;
        return uri;
    }

    private static async Task<ErrorDetail> ReadRejection(HttpResponseMessage response, Guid taskId, bool polling,
        CancellationToken cancellationToken)
    {
        try
        {
            var body = await response.Content.ReadFromJsonAsync<UpstreamError>(JsonOptions, cancellationToken);
            if ((body?.TaskId is null || body.TaskId == taskId) && ErrorDetail.IsValid(body?.Error))
                return body!.Error!;
        }
        catch (JsonException)
        {
            // An HTTP rejection is conclusive even if the error body is invalid.
        }
        return polling
            ? new("PYTHON_POLL_REJECTED", "Python rejected the status request.")
            : new("PYTHON_REJECTED", "Python rejected the task.");
    }

    private static PythonResponse InvalidResult() =>
        new(502, TimeSpan.Zero, Error: new("INVALID_PYTHON_RESULT", "Python returned an invalid task status."));

    private sealed record UpstreamAcceptance(Guid TaskId, string? Status);
    private sealed record UpstreamError(Guid? TaskId, ErrorDetail? Error);
    private sealed record UpstreamTaskStatus(Guid TaskId, string? Status, [property: JsonRequired] JsonElement? Result);
}

internal static class PythonTaskState
{
    public static readonly ErrorDetail TimedOut = new("TASK_TIMEOUT", "The Python result did not arrive before the deadline.");

    public static (TripCard Card, PythonTask Task)? Find(TripFlowDbContext data, Guid taskId)
    {
        var task = data.PythonTasks.Include(task => task.Card).SingleOrDefault(task => task.Id == taskId);
        return task is null ? null : (task.Card, task);
    }

    public static bool HasExpired(TripCard card, DateTimeOffset now) =>
        card.PythonTasks.Any(task => !task.Finished && task.Deadline <= now);

    public static void Expire(TripCard card, DateTimeOffset now)
    {
        foreach (var task in card.PythonTasks.Where(task => !task.Finished && task.Deadline <= now))
            Fail(card, task, TimedOut);
    }

    public static bool IsCurrent(TripCard card, PythonTask task) =>
        task.CardVersion == card.Version && (task.Kind == PythonTask.Budget
            ? card.Planning.Budget.TaskId == task.Id
            : task.Targets.Count > 0 && task.Targets.Keys.All(key => card.Planning.Queue(key).TaskId == task.Id));

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

internal static class PythonTaskResult
{
    public static string? Apply(TripCard card, PythonTask task, JsonElement payload)
    {
        try
        {
            var message = payload.Deserialize<PythonResultHeader>(PythonApiClient.JsonOptions);
            if (message?.TaskId != task.Id)
                return "The result does not match the task ID.";
            return (task.Kind, message.Event) switch
            {
                (PythonTask.Recommendations, "recommendations.finished") => ApplyRecommendations(card, task,
                    payload.Deserialize<RecommendationsFinished>(PythonApiClient.JsonOptions)!),
                (PythonTask.Budget, "budget.finished") => ApplyBudget(card, task,
                    payload.Deserialize<BudgetFinished>(PythonApiClient.JsonOptions)!),
                _ => "The result type does not match the task."
            };
        }
        catch (JsonException)
        {
            return "The result fields do not match the task schema.";
        }
    }

    private static string? ApplyRecommendations(TripCard card, PythonTask task, RecommendationsFinished message)
    {
        if (message.Results is not { } results || results.Count != task.Targets.Count)
            return "The result must include every requested target.";

        foreach (var (key, target) in task.Targets)
        {
            if (!results.TryGetValue(key, out var result) || result?.Items is not { } candidates ||
                candidates.Length > target.Count || !ValidTargetResult(result, candidates.Length)
                || candidates.Any(candidate => !ValidCandidate(candidate, key == "hotels")))
                return "Invalid result for a recommendation target.";
        }

        foreach (var (key, target) in task.Targets)
        {
            var result = results[key]!;
            var queue = card.Planning.Queue(key);
            queue.Status = result.Status;
            queue.Error = result.Error;
            queue.HasMore = result.HasMore;
            if (result.Status == PlanningStatus.Failed)
                continue;

            var isHotel = key == "hotels";
            var excluded = (target.Exclusions ?? []).Concat(queue.Items.Where(item => !item.NeedsReview)
                .Select(item => item.Candidate.ObjectId)).ToHashSet(StringComparer.Ordinal);
            foreach (var candidate in result.Items!)
            {
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
                return "A failed budget result requires an error and null expenses.";
            PythonTaskState.Fail(card, task, message.Error!);
            return null;
        }
        if (message.Status != PlanningStatus.Succeeded || message.Error is not null || message.Expenses is not
            { FoodTotalRub: >= 0, LocalTransportTotalRub: >= 0, OtherExpensesTotalRub: >= 0, ReserveTotalRub: >= 0 } expenses)
            return "A successful budget result requires four nonnegative expenses.";
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

    private sealed record PythonResultHeader(Guid TaskId, string? Event);
    private sealed record RecommendationsFinished(Dictionary<string, RecommendationResult?>? Results);
    private sealed record RecommendationResult(string Status, TripCandidate[]? Items,
        [property: JsonRequired] bool? HasMore, ErrorDetail? Error);
    private sealed record BudgetFinished(string? Status, [property: JsonRequired] BudgetExpenses? Expenses, ErrorDetail? Error);
}
