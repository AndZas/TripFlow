using System.Security.Claims;
using Microsoft.EntityFrameworkCore;

namespace TripFlow.Backend;

internal static partial class DashboardEndpoints
{
    public static void MapDashboardEndpoints(this RouteGroupBuilder api)
    {
        var dashboards = api.MapGroup("/dashboards").RequireAuthorization();
        dashboards.MapGet("", ListDashboards).WithTags("Дашборды").WithSummary("Список моих дашбордов")
            .Produces<DashboardSummaryView[]>();
        dashboards.MapPost("", CreateDashboard).WithTags("Дашборды").WithSummary("Создать дашборд")
            .Produces<DashboardSummaryView>(StatusCodes.Status201Created).ProducesValidationProblem();
        dashboards.MapPost("/join", JoinDashboard).WithTags("Дашборды").WithSummary("Вступить по приглашению")
            .Produces<DashboardSummaryView>();

        var dashboard = dashboards.MapGroup("/{dashboardId:guid}");
        dashboard.MapGet("", GetDashboard).WithTags("Дашборды").WithSummary("Открыть дашборд и посмотреть карточки")
            .Produces<DashboardView>();
        dashboard.MapDelete("", DeleteDashboard).WithTags("Дашборды").WithSummary("Удалить дашборд со всеми карточками")
            .Produces(StatusCodes.Status204NoContent)
            .ProducesProblem(StatusCodes.Status403Forbidden).ProducesProblem(StatusCodes.Status404NotFound);
        dashboard.MapPost("/invite", CreateInvite).WithTags("Дашборды").WithSummary("Получить новый токен приглашения")
            .Produces<InviteView>();
        dashboard.MapPost("/cards", CreateCard).WithTags("Карточки и голоса").WithSummary("Создать черновик карточки")
            .Produces<TripCardView>(StatusCodes.Status201Created).ProducesValidationProblem();

        var card = dashboard.MapGroup("/cards/{cardId:guid}").WithTags("Карточки и голоса");
        card.MapGet("", GetCard).WithSummary("Посмотреть карточку").Produces<TripCardView>();
        card.MapPut("", UpdateCard).WithSummary("Изменить параметры карточки")
            .Produces<TripCardView>().ProducesValidationProblem();
        card.MapDelete("", DeleteCard).WithSummary("Удалить свою карточку")
            .Produces(StatusCodes.Status204NoContent)
            .ProducesProblem(StatusCodes.Status403Forbidden).ProducesProblem(StatusCodes.Status404NotFound);
        card.MapPost("/publish", PublishCard).WithSummary("Опубликовать карточку").Produces<TripCardView>();
        card.MapPut("/vote", PutVote).WithSummary("Проголосовать или подтвердить голос")
            .Produces<TripCardView>().ProducesProblem(StatusCodes.Status409Conflict);
        card.MapDelete("/vote", RemoveVote).WithSummary("Снять свой голос").Produces(StatusCodes.Status204NoContent);
        MapPlanningEndpoints(card);
    }

    private static IResult ListDashboards(ClaimsPrincipal user, PostgresStore store) =>
        store.Read(data => Results.Ok(AccessibleDashboards(data, user.AccountId())
            .Select(dashboard => new DashboardSummaryView(
                dashboard.Id, dashboard.Name, dashboard.Description, dashboard.OwnerId, dashboard.Members.Count))
            .ToArray()));

    private static IResult CreateDashboard(DashboardRequest request, ClaimsPrincipal user, PostgresStore store)
    {
        var name = request.Name?.Trim();
        var description = CleanOptional(request.Description);
        var errors = new Dictionary<string, string[]>();
        if (name is not { Length: > 0 and <= 100 })
            errors["name"] = ["Enter a name between 1 and 100 characters."];
        if (description is { Length: > 1000 })
            errors["description"] = ["Use at most 1000 characters."];
        if (errors.Count > 0)
            return Results.ValidationProblem(errors);

        var ownerId = user.AccountId();
        return store.Change(data =>
        {
            var dashboardId = Guid.NewGuid();
            var dashboard = new Dashboard
            {
                Id = dashboardId, Name = name!, Description = description, OwnerId = ownerId,
                Members = [new DashboardMember(dashboardId, ownerId)]
            };
            data.Dashboards.Add(dashboard);
            return Results.Created($"/api/dashboards/{dashboard.Id}", DashboardSummary(dashboard));
        });
    }

    private static IResult GetDashboard(Guid dashboardId, ClaimsPrincipal user, PostgresStore store)
    {
        var accountId = user.AccountId();
        return store.Read(data =>
        {
            var dashboard = AccessibleDashboards(data, accountId)
                .Include(dashboard => dashboard.Members)
                .Include(dashboard => dashboard.Cards.Where(card => card.IsPublished || card.AuthorId == accountId))
                .ThenInclude(card => card.Votes).AsSplitQuery()
                .SingleOrDefault(dashboard => dashboard.Id == dashboardId);
            return dashboard is null ? Results.NotFound() : Results.Ok(new DashboardView(
                dashboard.Id, dashboard.Name, dashboard.Description, dashboard.OwnerId, dashboard.Members.Count,
                dashboard.Cards.Select(card => CardView(card, accountId)).ToArray()));
        });
    }

    private static IResult DeleteDashboard(Guid dashboardId, ClaimsPrincipal user, PostgresStore store)
    {
        var accountId = user.AccountId();
        return store.Change(data =>
        {
            var dashboard = FindDashboard(data, dashboardId, accountId);
            if (dashboard is null)
                return Results.NotFound();
            if (dashboard.OwnerId != accountId)
                return Results.Forbid();

            data.Dashboards.Remove(dashboard);
            return Results.NoContent();
        });
    }

    private static IResult CreateInvite(Guid dashboardId, ClaimsPrincipal user, PostgresStore store) =>
        store.Change(data =>
        {
            var dashboard = FindDashboard(data, dashboardId, user.AccountId());
            if (dashboard is null)
                return Results.NotFound();
            if (dashboard.OwnerId != user.AccountId())
                return Results.Forbid();

            var token = SecretTokens.Create();
            dashboard.InviteHash = SecretTokens.Hash(token);
            return Results.Ok(new InviteView(token));
        });

    private static IResult JoinDashboard(InviteRequest request, ClaimsPrincipal user, PostgresStore store)
    {
        if (request.Token is not { Length: 64 })
            return Results.NotFound();

        var hash = SecretTokens.Hash(request.Token);
        var accountId = user.AccountId();
        return store.Change(data =>
        {
            var dashboard = data.Dashboards.Include(dashboard => dashboard.Members)
                .SingleOrDefault(dashboard => dashboard.InviteHash == hash);
            if (dashboard is null)
                return Results.NotFound();
            if (!dashboard.Members.Any(member => member.AccountId == accountId))
                dashboard.Members.Add(new DashboardMember(dashboard.Id, accountId));
            return Results.Ok(DashboardSummary(dashboard));
        });
    }

    private static IResult CreateCard(Guid dashboardId, TripRequest request, ClaimsPrincipal user,
        PostgresStore store, DestinationCatalog catalog)
    {
        var accountId = user.AccountId();
        return store.Change(data =>
        {
            var dashboard = FindDashboard(data, dashboardId, accountId);
            if (dashboard is null)
                return Results.NotFound();
            var errors = ValidateTrip(request, catalog);
            if (errors.Count > 0)
                return Results.ValidationProblem(errors);

            var card = new TripCard
            {
                Id = Guid.NewGuid(), DashboardId = dashboardId, AuthorId = accountId, Trip = ToTripDetails(request)
            };
            dashboard.Cards.Add(card);
            return Results.Created($"/api/dashboards/{dashboardId}/cards/{card.Id}", CardView(card, accountId));
        });
    }

    private static IResult GetCard(Guid dashboardId, Guid cardId, ClaimsPrincipal user, PostgresStore store, TimeProvider clock)
    {
        var accountId = user.AccountId();
        var now = clock.GetUtcNow();
        var card = store.Read(data => FindCard(data, dashboardId, cardId, accountId));
        if (card is null)
            return Results.NotFound();
        if (!PythonTaskState.HasExpired(card, now))
            return Results.Ok(CardView(card, accountId, includePlanning: true));

        return store.Change(data =>
        {
            var current = FindCard(data, dashboardId, cardId, accountId);
            if (current is null)
                return Results.NotFound();
            PythonTaskState.Expire(current, now);
            return Results.Ok(CardView(current, accountId, includePlanning: true));
        });
    }

    private static IResult UpdateCard(Guid dashboardId, Guid cardId, TripRequest request, ClaimsPrincipal user,
        PostgresStore store, DestinationCatalog catalog) =>
        ChangeOwnCard(dashboardId, cardId, user, store, (_, card) =>
        {
            var errors = ValidateTrip(request, catalog);
            if (errors.Count > 0)
                return Results.ValidationProblem(errors);

            var trip = ToTripDetails(request);
            if (card.Trip != trip)
            {
                CardInputsChanged(card);
                card.Planning.OnTripChanged(card.Trip, trip);
                card.Trip = trip;
            }
            return Results.Ok(CardView(card, user.AccountId(), includePlanning: true));
        });

    private static IResult DeleteCard(Guid dashboardId, Guid cardId, ClaimsPrincipal user, PostgresStore store) =>
        ChangeOwnCard(dashboardId, cardId, user, store, (data, card) =>
        {
            data.Cards.Remove(card);
            return Results.NoContent();
        });

    private static IResult PublishCard(Guid dashboardId, Guid cardId, ClaimsPrincipal user, PostgresStore store) =>
        ChangeOwnCard(dashboardId, cardId, user, store, (_, card) =>
        {
            card.IsPublished = true;
            return Results.Ok(CardView(card, user.AccountId()));
        });

    private static IResult PutVote(Guid dashboardId, Guid cardId, VoteRequest request, ClaimsPrincipal user,
        PostgresStore store)
    {
        var accountId = user.AccountId();
        return store.Change(data =>
        {
            var card = FindCard(data, dashboardId, cardId, accountId, includeTasks: false);
            if (card is not { IsPublished: true })
                return Results.NotFound();
            if (request.CardVersion != card.Version)
                return Results.Problem(statusCode: 409, title: "The card has changed. Read the current version before voting.");

            var vote = card.Votes.Find(vote => vote.AccountId == accountId);
            if (vote is null)
                card.Votes.Add(new CardVote(card.Id, accountId, card.Version));
            else
                vote.CardVersion = card.Version;
            return Results.Ok(CardView(card, accountId));
        });
    }

    private static IResult RemoveVote(Guid dashboardId, Guid cardId, ClaimsPrincipal user, PostgresStore store)
    {
        var accountId = user.AccountId();
        return store.Change(data =>
        {
            var card = FindCard(data, dashboardId, cardId, accountId, includeTasks: false);
            if (card is not { IsPublished: true })
                return Results.NotFound();

            var vote = card.Votes.Find(vote => vote.AccountId == accountId);
            if (vote is not null)
                data.Remove(vote);
            return Results.NoContent();
        });
    }

    private static IResult ChangeOwnCard(Guid dashboardId, Guid cardId, ClaimsPrincipal user, PostgresStore store,
        Func<TripFlowDbContext, TripCard, IResult> change)
    {
        var accountId = user.AccountId();
        return store.Change(data =>
        {
            var card = FindCard(data, dashboardId, cardId, accountId);
            if (card is null)
                return Results.NotFound();
            return card.AuthorId == accountId ? change(data, card) : Results.Forbid();
        });
    }

    private static IQueryable<Dashboard> AccessibleDashboards(TripFlowDbContext data, Guid accountId) =>
        data.Dashboards.Where(dashboard => dashboard.Members.Any(member => member.AccountId == accountId));

    private static Dashboard? FindDashboard(TripFlowDbContext data, Guid id, Guid accountId) =>
        AccessibleDashboards(data, accountId).SingleOrDefault(dashboard => dashboard.Id == id);

    private static TripCard? FindCard(TripFlowDbContext data, Guid dashboardId, Guid cardId, Guid accountId,
        bool includeTasks = true)
    {
        var accessible = AccessibleDashboards(data, accountId);
        IQueryable<TripCard> cards = data.Cards.Include(card => card.Votes);
        if (includeTasks)
            cards = cards.Include(card => card.PythonTasks).AsSplitQuery();
        return cards.SingleOrDefault(card => card.Id == cardId && card.DashboardId == dashboardId
            && (card.IsPublished || card.AuthorId == accountId)
            && accessible.Any(dashboard => dashboard.Id == card.DashboardId));
    }

    private static DashboardSummaryView DashboardSummary(Dashboard dashboard) =>
        new(dashboard.Id, dashboard.Name, dashboard.Description, dashboard.OwnerId, dashboard.Members.Count);

    private static TripCardView CardView(TripCard card, Guid accountId, bool includePlanning = false)
    {
        var votedVersion = card.Votes.Find(vote => vote.AccountId == accountId)?.CardVersion;
        var plan = card.Planning;
        return new TripCardView(card.Id, card.AuthorId, card.Trip, card.IsPublished, card.Version,
            card.Votes.Count, votedVersion, votedVersion is not null && votedVersion != card.Version,
            includePlanning ? new(RecommendationListView.From(plan.Hotels), RecommendationListView.From(plan.Attractions)) : null,
            includePlanning ? new(plan.HotelId, plan.AttractionIds) : null,
            includePlanning ? BudgetView.From(plan.Budget) : null);
    }

    private static Dictionary<string, string[]> ValidateTrip(TripRequest request, DestinationCatalog catalog)
    {
        var errors = new Dictionary<string, string[]>();
        if (!catalog.Destinations.Any(destination => destination.Id == request.DestinationId))
            errors["destinationId"] = ["Choose a destination from the catalog."];
        if (request.StartDate is null)
            errors["startDate"] = ["Enter a start date."];
        if (request.EndDate is null || request.EndDate < request.StartDate)
            errors["endDate"] = ["Enter an end date on or after the start date."];
        if (request.Travelers <= 0)
            errors["travelers"] = ["Enter a positive traveler count."];
        if (request.BudgetRub <= 0)
            errors["budgetRub"] = ["Enter a positive budget in whole rubles."];
        if (request.Preferences?.Trim().Length > 2000)
            errors["preferences"] = ["Use at most 2000 characters."];
        return errors;
    }

    private static TripDetails ToTripDetails(TripRequest request) =>
        new(request.DestinationId!, request.StartDate!.Value, request.EndDate!.Value, request.Travelers,
            request.BudgetRub, CleanOptional(request.Preferences));

    private static string? CleanOptional(string? value) => string.IsNullOrWhiteSpace(value) ? null : value.Trim();

    internal sealed record DashboardRequest(string? Name, string? Description);
    internal sealed record InviteRequest(string? Token);
    internal sealed record VoteRequest(long CardVersion);
    internal sealed record TripRequest(string? DestinationId, DateOnly? StartDate, DateOnly? EndDate,
        int Travelers, long BudgetRub, string? Preferences);

    internal sealed record DashboardSummaryView(Guid Id, string Name, string? Description, Guid OwnerId, int MemberCount);
    internal sealed record DashboardView(Guid Id, string Name, string? Description, Guid OwnerId, int MemberCount,
        TripCardView[] Cards);
    internal sealed record TripCardView(Guid Id, Guid AuthorId, TripDetails Trip, bool IsPublished, long Version,
        int VoteCount, long? MyVoteVersion, bool MyVoteNeedsReview,
        [property: System.Text.Json.Serialization.JsonIgnore(Condition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
        RecommendationsView? Recommendations,
        [property: System.Text.Json.Serialization.JsonIgnore(Condition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
        SelectionView? Selection,
        [property: System.Text.Json.Serialization.JsonIgnore(Condition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull)]
        BudgetView? Budget);
    internal sealed record InviteView(string Token);
}
