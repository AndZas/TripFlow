using System.Net.Http.Headers;
using System.Net.Mail;
using System.Security.Claims;
using System.Text.Encodings.Web;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Identity;
using Microsoft.Extensions.Options;

namespace TripFlow.Backend;

internal static class AccountEndpoints
{
    public static void MapAccountEndpoints(this RouteGroupBuilder api)
    {
        var auth = api.MapGroup("/auth").WithTags("Аккаунт");
        auth.MapPost("/register", Register).WithSummary("Зарегистрироваться и получить токен")
            .Produces<SessionView>(StatusCodes.Status201Created)
            .ProducesValidationProblem().ProducesProblem(StatusCodes.Status409Conflict);
        auth.MapPost("/login", Login).WithSummary("Войти и получить токен")
            .Produces<SessionView>().ProducesProblem(StatusCodes.Status401Unauthorized);
        auth.MapGet("/me", GetCurrentAccount).RequireAuthorization().WithSummary("Посмотреть свой аккаунт")
            .Produces<AccountView>();
        auth.MapPost("/logout", (ClaimsPrincipal user, SessionStore sessions) =>
        {
            sessions.Revoke(user.FindFirstValue(BearerSessionHandler.SessionClaim)!);
            return Results.NoContent();
        }).RequireAuthorization().WithSummary("Завершить текущую сессию")
            .Produces(StatusCodes.Status204NoContent);
    }

    private static IResult Register(Credentials request, FileStore store,
        IPasswordHasher<Account> hasher, SessionStore sessions)
    {
        var email = request.Email?.Trim();
        if (email is null || email.Length > 254 || !MailAddress.TryCreate(email, out var address)
            || address.Address != email)
            return Results.ValidationProblem(new Dictionary<string, string[]> { ["email"] = ["Enter a valid email."] });

        if (request.Password is not { Length: >= 10 and <= 128 })
            return Results.ValidationProblem(new Dictionary<string, string[]>
            {
                ["password"] = ["Use between 10 and 128 characters."]
            });

        var account = new Account(Guid.NewGuid(), email, "");
        account = account with { PasswordHash = hasher.HashPassword(account, request.Password) };
        var saved = store.Change(data =>
        {
            if (FindByEmail(data, email) is not null)
                return Results.Problem(statusCode: 409, title: "This email is already registered.");
            data.Accounts.Add(account);
            return Results.NoContent();
        });
        return saved is IStatusCodeHttpResult { StatusCode: 204 }
            ? Results.Created("/api/auth/me", sessions.Issue(account))
            : saved;
    }

    private static IResult Login(Credentials request, FileStore store,
        IPasswordHasher<Account> hasher, SessionStore sessions)
    {
        if (request.Email is not { Length: > 0 and <= 254 } || request.Password is not { Length: >= 10 and <= 128 })
            return Results.Unauthorized();

        var account = store.Read(data => FindByEmail(data, request.Email.Trim()));
        if (account is null ||
            hasher.VerifyHashedPassword(account, account.PasswordHash, request.Password) == PasswordVerificationResult.Failed)
            return Results.Unauthorized();

        return Results.Ok(sessions.Issue(account));
    }

    private static IResult GetCurrentAccount(ClaimsPrincipal user, FileStore store) =>
        store.Read(data =>
        {
            var account = data.Accounts.Find(account => account.Id == user.AccountId());
            return account is null
                ? Results.Unauthorized()
                : Results.Ok(new AccountView(account.Id, account.Email));
        });

    private static Account? FindByEmail(StoreData data, string email) =>
        data.Accounts.Find(account => string.Equals(account.Email, email, StringComparison.OrdinalIgnoreCase));

    public static Guid AccountId(this ClaimsPrincipal user) =>
        Guid.Parse(user.FindFirstValue(ClaimTypes.NameIdentifier)!);

    internal sealed record Credentials(string? Email, string? Password);
}

internal sealed record AccountView(Guid Id, string Email);
internal sealed record SessionView(string AccessToken, string TokenType, DateTimeOffset ExpiresAt, AccountView User);
internal sealed record Session(Guid AccountId, DateTimeOffset ExpiresAt);

internal sealed class SessionStore(TimeProvider clock)
{
    private readonly object _gate = new();
    private readonly Dictionary<string, Session> _sessions = [];

    public SessionView Issue(Account account)
    {
        var token = SecretTokens.Create();
        var now = clock.GetUtcNow();
        var session = new Session(account.Id, now.AddHours(12));
        lock (_gate)
        {
            foreach (var key in _sessions.Where(entry => entry.Value.ExpiresAt <= now).Select(entry => entry.Key).ToArray())
                _sessions.Remove(key);
            _sessions.Add(SecretTokens.Hash(token), session);
        }
        return new SessionView(token, "Bearer", session.ExpiresAt, new AccountView(account.Id, account.Email));
    }

    public Session? Find(string key)
    {
        lock (_gate)
        {
            return _sessions.TryGetValue(key, out var session) && session.ExpiresAt > clock.GetUtcNow()
                ? session
                : null;
        }
    }

    public void Revoke(string key)
    {
        lock (_gate)
            _sessions.Remove(key);
    }
}

internal sealed class BearerSessionHandler(
    IOptionsMonitor<AuthenticationSchemeOptions> options,
    ILoggerFactory logger,
    UrlEncoder encoder,
    SessionStore sessions) : AuthenticationHandler<AuthenticationSchemeOptions>(options, logger, encoder)
{
    public const string SchemeName = "Bearer";
    public const string SessionClaim = "tripflow-session";

    protected override Task<AuthenticateResult> HandleAuthenticateAsync()
    {
        if (!AuthenticationHeaderValue.TryParse(Request.Headers.Authorization, out var header)
            || !string.Equals(header.Scheme, SchemeName, StringComparison.OrdinalIgnoreCase)
            || header.Parameter is not { Length: 64 } token)
            return Task.FromResult(AuthenticateResult.NoResult());

        var key = SecretTokens.Hash(token);
        var session = sessions.Find(key);
        if (session is null)
            return Task.FromResult(AuthenticateResult.Fail("Invalid or expired session."));

        var identity = new ClaimsIdentity([
            new Claim(ClaimTypes.NameIdentifier, session.AccountId.ToString()),
            new Claim(SessionClaim, key)
        ], SchemeName);
        return Task.FromResult(AuthenticateResult.Success(new AuthenticationTicket(new ClaimsPrincipal(identity), SchemeName)));
    }

    protected override Task HandleChallengeAsync(AuthenticationProperties properties)
    {
        Response.Headers.WWWAuthenticate = SchemeName;
        return base.HandleChallengeAsync(properties);
    }
}
