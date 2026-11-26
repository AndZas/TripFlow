using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace TripFlow.Backend;

internal sealed record Account(Guid Id, string Email, string PasswordHash)
{
    public string NormalizedEmail { get; private set; } = Email.ToUpperInvariant();
}

internal sealed class Dashboard
{
    public required Guid Id { get; init; }
    public required Guid OwnerId { get; init; }
    public required string Name { get; init; }
    public string? Description { get; init; }
    public string? InviteHash { get; set; }
    public List<DashboardMember> Members { get; init; } = [];
    public List<TripCard> Cards { get; init; } = [];
}

internal sealed class TripCard
{
    public required Guid Id { get; init; }
    public required Guid DashboardId { get; init; }
    public required Guid AuthorId { get; init; }
    public required TripDetails Trip { get; set; }
    public bool IsPublished { get; set; }
    public long Version { get; set; } = 1;
    public List<CardVote> Votes { get; init; } = [];
    public TripPlanning Planning { get; init; } = new();
    public List<PythonTask> PythonTasks { get; init; } = [];
}

internal sealed record DashboardMember(Guid DashboardId, Guid AccountId);

internal sealed class CardVote(Guid cardId, Guid accountId, long cardVersion)
{
    public Guid CardId { get; private set; } = cardId;
    public Guid AccountId { get; private set; } = accountId;
    public long CardVersion { get; set; } = cardVersion;
}

internal sealed record TripDetails(string DestinationId, DateOnly StartDate, DateOnly EndDate,
    int Travelers, long BudgetRub, string? Preferences);

internal sealed record Coordinates(double Latitude, double Longitude);
internal sealed record Destination(string Id, string City, string? RegionName, string CountryCode,
    string CountryName, Coordinates Coordinates);

internal sealed class DestinationCatalog
{
    public DestinationCatalog()
    {
        using var file = File.OpenRead(Path.Combine(AppContext.BaseDirectory, "destinations.json"));
        var catalog = JsonSerializer.Deserialize<CatalogFile>(file, new JsonSerializerOptions(JsonSerializerDefaults.Web))
            ?? throw new InvalidDataException("The destination catalog is empty.");
        Destinations = catalog.Destinations;
    }

    public IReadOnlyList<Destination> Destinations { get; }

    private sealed record CatalogFile(Destination[] Destinations);
}

internal static class SecretTokens
{
    public static string Create() => Convert.ToHexStringLower(RandomNumberGenerator.GetBytes(32));

    public static string Hash(string value) =>
        Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(value)));
}

internal static class LocalEnvironment
{
    public static string? ReadValue(string path, string key)
    {
        if (!File.Exists(path))
            return null;

        foreach (var line in File.ReadLines(path))
        {
            var assignment = line.TrimStart();
            if (assignment.StartsWith("export ", StringComparison.Ordinal))
                assignment = assignment["export ".Length..];
            var separator = assignment.IndexOf('=');
            if (separator >= 0 && assignment[..separator].Trim() == key)
                return assignment[(separator + 1)..].Trim().Trim('"', '\'');
        }
        return null;
    }
}
