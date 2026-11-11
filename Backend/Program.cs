using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.AspNetCore.Identity;
using Microsoft.OpenApi;
using TripFlow.Backend;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddProblemDetails();
builder.Services.AddDataProtection().UseEphemeralDataProtectionProvider();
builder.Services.AddSingleton(TimeProvider.System);
builder.Services.AddSingleton<SessionStore>();
builder.Services.AddSingleton<IPasswordHasher<Account>, PasswordHasher<Account>>();
builder.Services.AddSingleton(new DestinationCatalog());
builder.Services.AddSingleton(new FileStore(
    builder.Configuration["TripFlow:StorePath"]
        ?? Path.Combine(builder.Environment.ContentRootPath, "App_Data", "tripflow.json")));
builder.Services.AddAuthentication(BearerSessionHandler.SchemeName)
    .AddScheme<AuthenticationSchemeOptions, BearerSessionHandler>(
        BearerSessionHandler.SchemeName, _ => { });
builder.Services.AddAuthorization();

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
api.MapGet("/health", () => Results.Ok(new { status = "ok" }))
    .WithTags("Справочные маршруты").WithSummary("Проверить работу сервера");
api.MapGet("/destinations", (DestinationCatalog catalog) => Results.Ok(catalog.Destinations))
    .WithTags("Справочные маршруты").WithSummary("Получить список направлений")
    .Produces<Destination[]>();
api.MapAccountEndpoints();
api.MapDashboardEndpoints();
app.Run();
