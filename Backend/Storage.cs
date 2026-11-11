using System.Security.Cryptography;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Unicode;

namespace TripFlow.Backend;

internal sealed class FileStore
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        Encoder = JavaScriptEncoder.Create(UnicodeRanges.BasicLatin, UnicodeRanges.Cyrillic),
        WriteIndented = true
    };
    private readonly string _path;
    private readonly object _gate = new();
    private StoreData _data;

    public FileStore(string path)
    {
        _path = Path.GetFullPath(path);
        _data = File.Exists(_path) ? Deserialize(File.ReadAllBytes(_path)) : new StoreData();
    }

    public T Read<T>(Func<StoreData, T> read)
    {
        lock (_gate)
            return read(_data);
    }

    public IResult Change(Func<StoreData, IResult> change)
    {
        lock (_gate)
        {
            // Keep the previous snapshot if validation or saving fails.
            var next = Deserialize(JsonSerializer.SerializeToUtf8Bytes(_data, JsonOptions));
            var result = change(next);
            if (result is IStatusCodeHttpResult { StatusCode: >= 200 and < 300 })
            {
                Save(next);
                _data = next;
            }
            return result;
        }
    }

    private void Save(StoreData next)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
        var temporaryPath = _path + ".tmp";
        try
        {
            File.WriteAllBytes(temporaryPath, JsonSerializer.SerializeToUtf8Bytes(next, JsonOptions));
            File.Move(temporaryPath, _path, overwrite: true);
        }
        finally
        {
            File.Delete(temporaryPath);
        }
    }

    private static StoreData Deserialize(byte[] bytes) =>
        JsonSerializer.Deserialize<StoreData>(bytes, JsonOptions)
        ?? throw new InvalidDataException("The TripFlow data file is empty.");
}

internal sealed class StoreData
{
    public List<Account> Accounts { get; init; } = [];
    public List<Dashboard> Dashboards { get; init; } = [];
}

internal sealed record Account(Guid Id, string Email, string PasswordHash);

internal sealed class Dashboard
{
    public required Guid Id { get; init; }
    public required Guid OwnerId { get; init; }
    public required string Name { get; init; }
    public string? Description { get; init; }
    public string? InviteHash { get; set; }
    public HashSet<Guid> MemberIds { get; init; } = [];
    public List<TripCard> Cards { get; init; } = [];
}

internal sealed class TripCard
{
    public required Guid Id { get; init; }
    public required Guid AuthorId { get; init; }
    public required TripDetails Trip { get; set; }
    public bool IsPublished { get; set; }
    public long Version { get; set; } = 1;
    public Dictionary<Guid, long> Votes { get; init; } = [];
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
