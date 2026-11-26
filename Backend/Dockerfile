FROM mcr.microsoft.com/dotnet/sdk:10.0 AS backend-build
WORKDIR /src

COPY Backend/TripFlow.Backend.csproj Backend/
COPY shared/data/destinations.json shared/data/
RUN dotnet restore Backend/TripFlow.Backend.csproj

COPY Backend/*.cs Backend/
COPY Backend/Migrations/*.cs Backend/Migrations/
RUN dotnet publish Backend/TripFlow.Backend.csproj -c Release --no-restore -o /out -p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS backend-runtime
WORKDIR /app
COPY --from=backend-build /out/ ./
USER $APP_UID
ENV ASPNETCORE_HTTP_PORTS=8080
EXPOSE 8080
ENTRYPOINT ["dotnet", "TripFlow.Backend.dll"]

FROM node:24-bookworm-slim AS frontend-build
WORKDIR /src/Frontend/TripFlow
COPY Frontend/TripFlow/package.json Frontend/TripFlow/package-lock.json ./
RUN npm ci
COPY Frontend/TripFlow/index.html Frontend/TripFlow/tsconfig.json Frontend/TripFlow/vite.config.ts ./
COPY Frontend/TripFlow/src/ src/
COPY Frontend/TripFlow/public/ public/
RUN npm run build

FROM backend-runtime AS site
COPY --from=frontend-build /src/Frontend/TripFlow/dist/ wwwroot/
