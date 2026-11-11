using Microsoft.AspNetCore.Authorization;
using Microsoft.OpenApi;
using Swashbuckle.AspNetCore.SwaggerGen;

namespace TripFlow.Backend;

internal sealed class SwaggerAuthorization : IOperationFilter
{
    public void Apply(OpenApiOperation operation, OperationFilterContext context)
    {
        var metadata = context.ApiDescription.ActionDescriptor.EndpointMetadata;
        if (!metadata.OfType<IAuthorizeData>().Any() || metadata.OfType<IAllowAnonymous>().Any())
            return;

        var bearer = new OpenApiSecuritySchemeReference(BearerSessionHandler.SchemeName, context.Document);
        operation.Security = [new OpenApiSecurityRequirement { [bearer] = [] }];
        operation.Responses ??= [];
        operation.Responses.TryAdd("401", new OpenApiResponse { Description = "Требуется действующий токен входа." });
    }
}
