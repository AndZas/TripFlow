using System.Text.Json;
using System.Text.Json.Serialization;

namespace TripFlow.Backend;

internal static class PlanningStatus
{
    public const string NotStarted = "not_started";
    public const string Pending = "pending";
    public const string Succeeded = "succeeded";
    public const string Partial = "partial";
    public const string Failed = "failed";
    public const string Stale = "stale";
}

internal sealed class TripPlanning
{
    public RecommendationQueue Hotels { get; set; } = new();
    public RecommendationQueue Attractions { get; set; } = new();
    public Guid? HotelId { get; set; }
    public List<Guid> AttractionIds { get; set; } = [];
    public BudgetState Budget { get; set; } = new();

    public RecommendationQueue Queue(string target) => target == "hotels" ? Hotels : Attractions;

    public void OnTripChanged(TripDetails previous, TripDetails current)
    {
        if (previous.DestinationId != current.DestinationId || previous.StartDate != current.StartDate ||
            previous.EndDate != current.EndDate || previous.Travelers != current.Travelers)
        {
            // Keep the author's choice visible, but prices from the old dates/group cannot be used in a new estimate.
            Hotels.ResetForTrip(HotelId is Guid id ? [id] : []);
            Attractions.ResetForTrip(AttractionIds);
        }
        else
        {
            Hotels.HasMore = null;
            Attractions.HasMore = null;
            Hotels.LastCompletedSearch = null;
            Attractions.LastCompletedSearch = null;
        }
    }

    public void InvalidateBudget()
    {
        if (Budget.Status != PlanningStatus.NotStarted)
            Budget = new() { Status = PlanningStatus.Stale };
    }
}

internal sealed class RecommendationQueue
{
    public List<CandidateView> Items { get; set; } = [];
    public string Status { get; set; } = PlanningStatus.NotStarted;
    public bool? HasMore { get; set; }
    public ErrorDetail? Error { get; set; }
    public SearchCriteria? LastCompletedSearch { get; set; }
    public Guid? TaskId { get; set; }
    public string? StatusBeforePending { get; set; }

    public void Start(Guid taskId)
    {
        StatusBeforePending = Status;
        Status = PlanningStatus.Pending;
        TaskId = taskId;
    }

    public void Cancel()
    {
        if (Status == PlanningStatus.Pending)
            Status = StatusBeforePending ?? PlanningStatus.NotStarted;
        TaskId = null;
    }

    public void ResetForTrip(IEnumerable<Guid> selections)
    {
        var ids = selections.ToHashSet();
        Items = Items.Where(item => ids.Contains(item.Id)).Select(item => item with { NeedsReview = true }).ToList();
        Status = PlanningStatus.NotStarted;
        HasMore = null;
        Error = null;
        LastCompletedSearch = null;
        TaskId = null;
    }
}

internal sealed class BudgetState
{
    public string Status { get; set; } = PlanningStatus.NotStarted;
    public Guid? TaskId { get; set; }
    public BudgetSummary? Summary { get; set; }
    public ErrorDetail? Error { get; set; }
}

internal sealed class PythonTask
{
    public const string Recommendations = "recommendations";
    public const string Budget = "budget";

    public required Guid Id { get; init; }
    public required Guid CardId { get; init; }
    public TripCard Card { get; private set; } = null!;
    public required string Kind { get; init; }
    public required long CardVersion { get; init; }
    public required JsonElement Payload { get; init; }
    public DateTimeOffset Deadline { get; init; }
    public CardGenerationInput? Generation { get; init; }
    public Guid? GenerationBatchId { get; init; }
    public Dictionary<string, RecommendationTaskTarget> Targets { get; init; } = [];
    public DateTimeOffset? NextAttemptAt { get; set; }
    public string? PollPath { get; set; }
    public bool Accepted { get; set; }
    public bool Finished { get; set; }
}

internal sealed record RecommendationTaskTarget(int Count, SearchCriteria? Criteria, string[]? Exclusions);
internal sealed record CardGenerationInput(string? Target, string? Refinement, Guid? ReplaceAttractionId);
internal sealed record SearchCriteria(long? MaxTotalRub, string? Refinement);
internal sealed record PythonRecommendationRequest(Guid TaskId, TripDetails Trip, string Targets,
    int Count, long? MaxTotalRub, string? Refinement, string[] ExcludedObjectIds);
internal sealed record HotelSelectionInput([property: JsonRequired] Guid? HotelId);
internal sealed record AttractionSelectionInput(Guid[]? AttractionIds);

internal sealed record CandidateView(Guid Id, TripCandidate Candidate,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] bool NeedsReview = false);

internal sealed record TripCandidate(
    string ObjectId, string Name, [property: JsonRequired] string? Address,
    [property: JsonRequired] CandidateCoordinates? Coordinates, [property: JsonRequired] string? ImageUrl,
    string SourceUrl, [property: JsonRequired] JsonElement Price, string? Description, string? RecommendationReason,
    int? Stars, string? Category, TariffSnapshot? Tariff);

internal sealed record CandidateCoordinates([property: JsonRequired] double Latitude, [property: JsonRequired] double Longitude);
internal sealed record AdmissionPriceQuote([property: JsonRequired] long AmountRub, string Basis, string Kind,
    bool IsFromPrice = false, string? SourceUrl = null);
internal sealed record TariffSnapshot([property: JsonRequired] string? Name, IncludedService[] IncludedServices);
internal sealed record IncludedService(string Service, string Status, [property: JsonRequired] DateOnly[]? Dates,
    [property: JsonRequired] string? SourceUrl);
internal sealed record ErrorDetail(string Code, string Message, Dictionary<string, string[]>? Fields = null)
{
    public static bool IsValid(ErrorDetail? error) => error is not null && !string.IsNullOrWhiteSpace(error.Code)
        && !string.IsNullOrWhiteSpace(error.Message) && (error.Fields?.Values.All(messages =>
            messages is { Length: > 0 } && messages.All(message => !string.IsNullOrWhiteSpace(message))) ?? true);
}

internal sealed record BudgetExpenses(
    [property: JsonRequired] long FoodTotalRub,
    [property: JsonRequired] long LocalTransportTotalRub,
    [property: JsonRequired] long OtherExpensesTotalRub,
    [property: JsonRequired] long ReserveTotalRub);
internal sealed record BudgetSummary(long CardVersion, long? AccommodationRub, long AttractionsRub,
    BudgetExpenses Expenses, long TotalRub, long PerPersonRub, bool Complete, bool IsLowerBound, long? RemainingRub);

internal sealed record SelectionView(Guid? HotelId, IReadOnlyList<Guid> AttractionIds);
internal sealed record RecommendationsView(RecommendationListView Hotels, RecommendationListView Attractions);
internal sealed record RecommendationListView(string Status, IReadOnlyList<CandidateView> Items, bool? HasMore, ErrorDetail? Error)
{
    public static RecommendationListView From(RecommendationQueue queue) => queue.Status == PlanningStatus.Pending
        ? new(queue.Status, queue.Items, null, null)
        : new(queue.Status, queue.Items, queue.HasMore, queue.Error);
}

internal sealed record BudgetView(string Status, BudgetSummary? Result, ErrorDetail? Error)
{
    public static BudgetView From(BudgetState budget) => new(budget.Status, budget.Summary, budget.Error);
}

internal static class PlanningBudget
{
    public static AdmissionPriceQuote? AdmissionPrice(JsonElement price) => price.ValueKind == JsonValueKind.Null
        ? null
        : price.Deserialize<AdmissionPriceQuote>(PythonApiClient.JsonOptions);

    public static long? AdmissionTotal(AdmissionPriceQuote? price, int travelers) => price is null
        ? null
        : price.Basis == "group_admission" ? price.AmountRub : checked(price.AmountRub * travelers);

    public static long? HotelPrice(JsonElement price) => price.ValueKind == JsonValueKind.Number ? price.GetInt64() : null;

    public static BudgetSummary Calculate(PythonTask task, BudgetExpenses expenses)
    {
        var input = task.Payload.Deserialize<PythonBudgetRequest>(PythonApiClient.JsonOptions)!;
        var overnight = input.Trip.EndDate > input.Trip.StartDate;
        var accommodation = overnight ? input.SelectedHotel?.Price : 0L;
        var visits = input.SelectedAttractions.Select(place =>
            (Cost: AdmissionTotal(place.Price, input.Trip.Travelers), FromPrice: place.Price?.IsFromPrice == true)).ToArray();
        var attractions = visits.Sum(visit => visit.Cost ?? 0);
        var total = checked((accommodation ?? 0) + attractions + expenses.FoodTotalRub + expenses.LocalTransportTotalRub
            + expenses.OtherExpensesTotalRub + expenses.ReserveTotalRub);
        var complete = accommodation is not null && visits.All(visit => visit.Cost is not null);
        var lowerBound = !complete || visits.Any(visit => visit.FromPrice);
        return new BudgetSummary(task.CardVersion, accommodation, attractions, expenses, total,
            (long)Math.Ceiling((decimal)total / input.Trip.Travelers), complete, lowerBound,
            lowerBound ? null : input.Trip.BudgetRub - total);
    }
}

internal sealed record PythonBudgetRequest(Guid TaskId, TripDetails Trip, PythonSelectedHotel? SelectedHotel,
    PythonSelectedAttraction[] SelectedAttractions);
internal sealed record PythonSelectedHotel(string ObjectId, long? Price);
internal sealed record PythonSelectedAttraction(string ObjectId, AdmissionPriceQuote? Price);
