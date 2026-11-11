using System.Security.Claims;

namespace TripFlow.Backend;

internal static class DashboardEndpoints
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
        dashboard.MapPost("/invite", CreateInvite).WithTags("Дашборды").WithSummary("Получить новый токен приглашения")
            .Produces<InviteView>();
        dashboard.MapPost("/cards", CreateCard).WithTags("Карточки и голоса").WithSummary("Создать черновик карточки")
            .Produces<TripCardView>(StatusCodes.Status201Created).ProducesValidationProblem();

        var card = dashboard.MapGroup("/cards/{cardId:guid}").WithTags("Карточки и голоса");
        card.MapGet("", GetCard).WithSummary("Посмотреть карточку").Produces<TripCardView>();
        card.MapPut("", UpdateCard).WithSummary("Изменить параметры карточки")
            .Produces<TripCardView>().ProducesValidationProblem();
        card.MapPost("/publish", PublishCard).WithSummary("Опубликовать карточку").Produces<TripCardView>();
        card.MapPut("/vote", PutVote).WithSummary("Проголосовать или подтвердить голос")
            .Produces<TripCardView>().ProducesProblem(StatusCodes.Status409Conflict);
        card.MapDelete("/vote", RemoveVote).WithSummary("Снять свой голос").Produces(StatusCodes.Status204NoContent);
    }

    private static IResult ListDashboards(ClaimsPrincipal user, FileStore store) =>
        store.Read(data => Results.Ok(data.Dashboards
            .Where(dashboard => dashboard.MemberIds.Contains(user.AccountId()))
            .Select(DashboardSummary).ToArray()));

    private static IResult CreateDashboard(DashboardRequest request, ClaimsPrincipal user, FileStore store)
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
            var dashboard = new Dashboard
            {
                Id = Guid.NewGuid(), Name = name!, Description = description, OwnerId = ownerId,
                MemberIds = [ownerId]
            };
            data.Dashboards.Add(dashboard);
            return Results.Created($"/api/dashboards/{dashboard.Id}", DashboardSummary(dashboard));
        });
    }

    private static IResult GetDashboard(Guid dashboardId, ClaimsPrincipal user, FileStore store)
    {
        var accountId = user.AccountId();
        return store.Read(data =>
        {
            var dashboard = FindDashboard(data, dashboardId, accountId);
            return dashboard is null ? Results.NotFound() : Results.Ok(new DashboardView(
                dashboard.Id, dashboard.Name, dashboard.Description, dashboard.OwnerId, dashboard.MemberIds.Count,
                dashboard.Cards.Where(card => CanSee(card, accountId)).Select(card => CardView(card, accountId)).ToArray()));
        });
    }

    private static IResult CreateInvite(Guid dashboardId, ClaimsPrincipal user, FileStore store) =>
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

    private static IResult JoinDashboard(InviteRequest request, ClaimsPrincipal user, FileStore store)
    {
        if (request.Token is not { Length: 64 })
            return Results.NotFound();

        var hash = SecretTokens.Hash(request.Token);
        return store.Change(data =>
        {
            var dashboard = data.Dashboards.Find(dashboard => dashboard.InviteHash == hash);
            if (dashboard is null)
                return Results.NotFound();
            dashboard.MemberIds.Add(user.AccountId());
            return Results.Ok(DashboardSummary(dashboard));
        });
    }

    private static IResult CreateCard(Guid dashboardId, TripRequest request, ClaimsPrincipal user,
        FileStore store, DestinationCatalog catalog)
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

            var card = new TripCard { Id = Guid.NewGuid(), AuthorId = accountId, Trip = ToTripDetails(request) };
            dashboard.Cards.Add(card);
            return Results.Created($"/api/dashboards/{dashboardId}/cards/{card.Id}", CardView(card, accountId));
        });
    }

    private static IResult GetCard(Guid dashboardId, Guid cardId, ClaimsPrincipal user, FileStore store)
    {
        var accountId = user.AccountId();
        return store.Read(data =>
        {
            var card = FindCard(data, dashboardId, cardId, accountId);
            return card is null ? Results.NotFound() : Results.Ok(CardView(card, accountId));
        });
    }

    private static IResult UpdateCard(Guid dashboardId, Guid cardId, TripRequest request, ClaimsPrincipal user,
        FileStore store, DestinationCatalog catalog) =>
        ChangeOwnCard(dashboardId, cardId, user, store, card =>
        {
            var errors = ValidateTrip(request, catalog);
            if (errors.Count > 0)
                return Results.ValidationProblem(errors);

            var trip = ToTripDetails(request);
            if (card.Trip != trip)
            {
                card.Trip = trip;
                card.Version++;
            }
            return Results.Ok(CardView(card, user.AccountId()));
        });

    private static IResult PublishCard(Guid dashboardId, Guid cardId, ClaimsPrincipal user, FileStore store) =>
        ChangeOwnCard(dashboardId, cardId, user, store, card =>
        {
            card.IsPublished = true;
            return Results.Ok(CardView(card, user.AccountId()));
        });

    private static IResult PutVote(Guid dashboardId, Guid cardId, VoteRequest request, ClaimsPrincipal user,
        FileStore store)
    {
        var accountId = user.AccountId();
        return store.Change(data =>
        {
            var card = FindCard(data, dashboardId, cardId, accountId);
            if (card is not { IsPublished: true })
                return Results.NotFound();
            if (request.CardVersion != card.Version)
                return Results.Problem(statusCode: 409, title: "The card has changed. Read the current version before voting.");

            card.Votes[accountId] = card.Version;
            return Results.Ok(CardView(card, accountId));
        });
    }

    private static IResult RemoveVote(Guid dashboardId, Guid cardId, ClaimsPrincipal user, FileStore store)
    {
        var accountId = user.AccountId();
        return store.Change(data =>
        {
            var card = FindCard(data, dashboardId, cardId, accountId);
            if (card is not { IsPublished: true })
                return Results.NotFound();

            card.Votes.Remove(accountId);
            return Results.NoContent();
        });
    }

    private static IResult ChangeOwnCard(Guid dashboardId, Guid cardId, ClaimsPrincipal user, FileStore store,
        Func<TripCard, IResult> change)
    {
        var accountId = user.AccountId();
        return store.Change(data =>
        {
            var card = FindCard(data, dashboardId, cardId, accountId);
            if (card is null)
                return Results.NotFound();
            return card.AuthorId == accountId ? change(card) : Results.Forbid();
        });
    }

    private static Dashboard? FindDashboard(StoreData data, Guid id, Guid accountId) =>
        data.Dashboards.Find(dashboard => dashboard.Id == id && dashboard.MemberIds.Contains(accountId));

    private static TripCard? FindCard(StoreData data, Guid dashboardId, Guid cardId, Guid accountId) =>
        FindDashboard(data, dashboardId, accountId)?.Cards.Find(card => card.Id == cardId && CanSee(card, accountId));

    private static bool CanSee(TripCard card, Guid accountId) => card.IsPublished || card.AuthorId == accountId;

    private static DashboardSummaryView DashboardSummary(Dashboard dashboard) =>
        new(dashboard.Id, dashboard.Name, dashboard.Description, dashboard.OwnerId, dashboard.MemberIds.Count);

    private static TripCardView CardView(TripCard card, Guid accountId)
    {
        var hasVote = card.Votes.TryGetValue(accountId, out var votedVersion);
        return new TripCardView(card.Id, card.AuthorId, card.Trip, card.IsPublished, card.Version,
            card.Votes.Count, hasVote ? votedVersion : null, hasVote && votedVersion != card.Version);
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
        int VoteCount, long? MyVoteVersion, bool MyVoteNeedsReview);
    internal sealed record InviteView(string Token);
}
