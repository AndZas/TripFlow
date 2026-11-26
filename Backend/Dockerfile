FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

COPY Backend/TripFlow.Backend.csproj Backend/
COPY shared/data/destinations.json shared/data/
RUN dotnet restore Backend/TripFlow.Backend.csproj

COPY Backend/*.cs Backend/
COPY Backend/Migrations/*.cs Backend/Migrations/
RUN dotnet publish Backend/TripFlow.Backend.csproj -c Release --no-restore -o /out -p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=build /out/ ./
USER $APP_UID
ENV ASPNETCORE_HTTP_PORTS=8080
EXPOSE 8080
ENTRYPOINT ["dotnet", "TripFlow.Backend.dll"]
