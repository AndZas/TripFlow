using System.Data;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.ChangeTracking;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Npgsql;

namespace TripFlow.Backend;

internal sealed class TripFlowDbContext(DbContextOptions<TripFlowDbContext> options) : DbContext(options)
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    public DbSet<Account> Accounts => Set<Account>();
    public DbSet<Session> Sessions => Set<Session>();
    public DbSet<Dashboard> Dashboards => Set<Dashboard>();
    public DbSet<TripCard> Cards => Set<TripCard>();
    public DbSet<PythonTask> PythonTasks => Set<PythonTask>();

    protected override void OnModelCreating(ModelBuilder model)
    {
        var accounts = model.Entity<Account>();
        accounts.ToTable("accounts");
        accounts.Property(account => account.Id).ValueGeneratedNever();
        accounts.HasIndex(account => account.NormalizedEmail).IsUnique();

        var sessions = model.Entity<Session>();
        sessions.ToTable("sessions");
        sessions.HasKey(session => session.TokenHash);
        sessions.HasIndex(session => session.ExpiresAt);
        sessions.HasOne<Account>().WithMany().HasForeignKey(session => session.AccountId);

        var dashboards = model.Entity<Dashboard>();
        dashboards.ToTable("dashboards");
        dashboards.Property(dashboard => dashboard.Id).ValueGeneratedNever();
        dashboards.HasIndex(dashboard => dashboard.InviteHash).IsUnique();
        dashboards.HasOne<Account>().WithMany().HasForeignKey(dashboard => dashboard.OwnerId)
            .OnDelete(DeleteBehavior.Restrict);
        dashboards.HasMany(dashboard => dashboard.Members).WithOne().HasForeignKey(member => member.DashboardId);
        dashboards.HasMany(dashboard => dashboard.Cards).WithOne().HasForeignKey(card => card.DashboardId);

        var members = model.Entity<DashboardMember>();
        members.ToTable("dashboard_members");
        members.HasKey(member => new { member.DashboardId, member.AccountId });
        members.HasOne<Account>().WithMany().HasForeignKey(member => member.AccountId);

        var cards = model.Entity<TripCard>();
        cards.ToTable("cards");
        cards.Property(card => card.Id).ValueGeneratedNever();
        cards.ComplexProperty(card => card.Trip).IsRequired();
        MapJson(cards.Property(card => card.Planning));
        cards.HasOne<Account>().WithMany().HasForeignKey(card => card.AuthorId)
            .OnDelete(DeleteBehavior.Restrict);
        cards.HasMany(card => card.Votes).WithOne().HasForeignKey(vote => vote.CardId);
        cards.HasMany(card => card.PythonTasks).WithOne(task => task.Card).HasForeignKey(task => task.CardId);

        var votes = model.Entity<CardVote>();
        votes.ToTable("card_votes");
        votes.HasKey(vote => new { vote.CardId, vote.AccountId });
        votes.HasOne<Account>().WithMany().HasForeignKey(vote => vote.AccountId);

        var tasks = model.Entity<PythonTask>();
        tasks.ToTable("python_tasks");
        tasks.Property(task => task.Id).ValueGeneratedNever();
        tasks.Property(task => task.Payload).HasColumnType("jsonb");
        MapJson(tasks.Property(task => task.Generation));
        MapJson(tasks.Property(task => task.Targets));
        tasks.HasIndex(task => task.NextAttemptAt).HasFilter("NOT \"Finished\"");
        tasks.HasIndex(task => task.Deadline).HasFilter("NOT \"Finished\"");
    }

    private static void MapJson<T>(PropertyBuilder<T> property) where T : class?
    {
        property.HasColumnType("jsonb").HasConversion(
            value => Serialize(value),
            json => Deserialize<T>(json),
            new ValueComparer<T>(
                (left, right) => Serialize(left) == Serialize(right),
                value => Serialize(value).GetHashCode(StringComparison.Ordinal),
                value => Deserialize<T>(Serialize(value))));
    }

    private static string Serialize<T>(T value) => JsonSerializer.Serialize(value, JsonOptions);
    private static T Deserialize<T>(string json) => JsonSerializer.Deserialize<T>(json, JsonOptions)!;
}

internal sealed class PostgresStore(IDbContextFactory<TripFlowDbContext> factory)
{
    public T Read<T>(Func<TripFlowDbContext, T> read)
    {
        using var data = factory.CreateDbContext();
        data.ChangeTracker.QueryTrackingBehavior = QueryTrackingBehavior.NoTracking;
        using var transaction = data.Database.BeginTransaction(IsolationLevel.RepeatableRead);
        var result = read(data);
        transaction.Commit();
        return result;
    }

    public IResult Change(Func<TripFlowDbContext, IResult> change)
    {
        using var data = factory.CreateDbContext();
        using var transaction = data.Database.BeginTransaction();
        // Serialize writes from HTTP endpoints and the worker until their database transaction commits.
        data.Database.ExecuteSqlRaw("SELECT pg_advisory_xact_lock(226017, 1)");
        var result = change(data);
        if (result is IStatusCodeHttpResult { StatusCode: >= 200 and < 300 })
        {
            data.SaveChanges();
            transaction.Commit();
        }
        return result;
    }

    public static bool IsUnavailable(Exception error) =>
        error is NpgsqlException { IsTransient: true }
            or DbUpdateException { InnerException: NpgsqlException { IsTransient: true } };
}

internal static class PostgresConfiguration
{
    public static string ConnectionString(IConfiguration configuration, string contentRoot)
    {
        var connectionString = configuration.GetConnectionString("TripFlow");
        if (!string.IsNullOrWhiteSpace(connectionString))
            return connectionString;

        var databaseUrl = configuration["TRIPFLOW_DATABASE_URL"];
        if (!string.IsNullOrWhiteSpace(databaseUrl))
            return FromDatabaseUrl(databaseUrl);

        var file = Path.Combine(contentRoot, ".env");
        var password = configuration["TRIPFLOW_POSTGRES_PASSWORD"]
            ?? LocalEnvironment.ReadValue(file, "TRIPFLOW_POSTGRES_PASSWORD");
        if (string.IsNullOrWhiteSpace(password))
            throw new InvalidOperationException(
                "Set TRIPFLOW_POSTGRES_PASSWORD in Backend/.env or configure ConnectionStrings__TripFlow.");

        var port = configuration["TRIPFLOW_POSTGRES_PORT"]
            ?? LocalEnvironment.ReadValue(file, "TRIPFLOW_POSTGRES_PORT") ?? "5433";
        if (!int.TryParse(port, out var portNumber) || portNumber is < 1 or > 65535)
            throw new InvalidOperationException("TRIPFLOW_POSTGRES_PORT must be a valid port number.");

        return new NpgsqlConnectionStringBuilder
        {
            Host = configuration["TRIPFLOW_POSTGRES_HOST"] ?? "127.0.0.1",
            Port = portNumber,
            Database = "tripflow",
            Username = "tripflow",
            Password = password
        }.ConnectionString;
    }

    private static string FromDatabaseUrl(string value)
    {
        if (!Uri.TryCreate(value, UriKind.Absolute, out var uri)
            || uri.Scheme is not ("postgres" or "postgresql") || string.IsNullOrEmpty(uri.Host)
            || uri.AbsolutePath.Length <= 1 || uri.Query.Length > 0 || uri.Fragment.Length > 0)
            throw new InvalidOperationException("TRIPFLOW_DATABASE_URL must be an internal PostgreSQL URL.");

        var credentials = uri.UserInfo.Split(':', 2);
        if (credentials.Length != 2 || credentials.Any(string.IsNullOrEmpty))
            throw new InvalidOperationException("TRIPFLOW_DATABASE_URL must contain a PostgreSQL user and password.");

        return new NpgsqlConnectionStringBuilder
        {
            Host = uri.Host,
            Port = uri.IsDefaultPort ? 5432 : uri.Port,
            Database = Uri.UnescapeDataString(uri.AbsolutePath[1..]),
            Username = Uri.UnescapeDataString(credentials[0]),
            Password = Uri.UnescapeDataString(credentials[1])
        }.ConnectionString;
    }
}
