using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using Microsoft.OpenApi;
using TripFlow.Backend;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddProblemDetails();
builder.Services.Configure<RouteHandlerOptions>(options => options.ThrowOnBadRequest = false);
builder.Services.AddDataProtection().UseEphemeralDataProtectionProvider();
builder.Services.AddSingleton(TimeProvider.System);
builder.Services.AddSingleton<SessionStore>();
builder.Services.AddSingleton<IPasswordHasher<Account>, PasswordHasher<Account>>();
builder.Services.AddSingleton(new DestinationCatalog());
var connectionString = PostgresConfiguration.ConnectionString(builder.Configuration, builder.Environment.ContentRootPath);
builder.Services.AddDbContextFactory<TripFlowDbContext>(options => options.UseNpgsql(connectionString));
builder.Services.AddSingleton<PostgresStore>();
builder.Services.AddAuthentication(BearerSessionHandler.SchemeName)
    .AddScheme<AuthenticationSchemeOptions, BearerSessionHandler>(
        BearerSessionHandler.SchemeName, _ => { });
builder.Services.AddAuthorization();
builder.Services.AddSingleton(PythonApiSettings.Load(builder.Configuration, builder.Environment.ContentRootPath));
builder.Services.AddHttpClient(PythonApiClient.HttpClientName, client => client.Timeout = TimeSpan.FromSeconds(15))
    .ConfigurePrimaryHttpMessageHandler(() => new HttpClientHandler { AllowAutoRedirect = false });
builder.Services.AddSingleton<PythonApiClient>();
builder.Services.AddSingleton<PythonTaskWorker>();
builder.Services.AddHostedService(services => services.GetRequiredService<PythonTaskWorker>());

if (builder.Environment.IsDevelopment())
{
    builder.Services.AddEndpointsApiExplorer();
    builder.Services.AddSwaggerGen(options =>
    {
        options.SwaggerDoc("v1", new OpenApiInfo
        {
            Title = "TripFlow API",
            Version = "v1",
            Description = "Проверка API TripFlow. Для закрытых маршрутов войдите и вставьте accessToken через Authorize."
        });
        options.AddSecurityDefinition(BearerSessionHandler.SchemeName, new OpenApiSecurityScheme
        {
            Type = SecuritySchemeType.Http,
            Scheme = "bearer",
            Description = "Вставьте значение accessToken из ответа на регистрацию или вход."
        });
        options.OperationFilter<SwaggerAuthorization>();
    });
}

var origins = builder.Configuration.GetSection("Cors:Origins").Get<string[]>() ?? [];
builder.Services.AddCors(options => options.AddDefaultPolicy(policy =>
    policy.WithOrigins(origins).AllowAnyHeader().AllowAnyMethod()));

var app = builder.Build();
await using (var data = await app.Services.GetRequiredService<IDbContextFactory<TripFlowDbContext>>().CreateDbContextAsync())
    await data.Database.MigrateAsync();

app.UseExceptionHandler();
app.UseStatusCodePages();
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI(options => options.SwaggerEndpoint("v1/swagger.json", "TripFlow API v1"));
}

app.UseCors();
app.UseAuthentication();
app.UseAuthorization();

var api = app.MapGroup("/api");
api.MapGet("/health", async (TripFlowDbContext data, CancellationToken cancellationToken) =>
        await data.Database.CanConnectAsync(cancellationToken)
            ? Results.Ok(new { status = "ok" })
            : Results.Problem(statusCode: 503, title: "PostgreSQL is unavailable."))
    .WithTags("Справочные маршруты").WithSummary("Проверить работу сервера и базы данных");
api.MapGet("/destinations", (DestinationCatalog catalog) => Results.Ok(catalog.Destinations))
    .WithTags("Справочные маршруты").WithSummary("Получить список направлений")
    .Produces<Destination[]>();
api.MapAccountEndpoints();
api.MapDashboardEndpoints();
app.Run();
