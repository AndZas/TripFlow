using System;
using System.Text.Json;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace TripFlow.Backend.Migrations
{
    /// <inheritdoc />
    public partial class InitialPostgres : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "accounts",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    Email = table.Column<string>(type: "text", nullable: false),
                    PasswordHash = table.Column<string>(type: "text", nullable: false),
                    NormalizedEmail = table.Column<string>(type: "text", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_accounts", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "dashboards",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    OwnerId = table.Column<Guid>(type: "uuid", nullable: false),
                    Name = table.Column<string>(type: "text", nullable: false),
                    Description = table.Column<string>(type: "text", nullable: true),
                    InviteHash = table.Column<string>(type: "text", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_dashboards", x => x.Id);
                    table.ForeignKey(
                        name: "FK_dashboards_accounts_OwnerId",
                        column: x => x.OwnerId,
                        principalTable: "accounts",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                });

            migrationBuilder.CreateTable(
                name: "sessions",
                columns: table => new
                {
                    TokenHash = table.Column<string>(type: "text", nullable: false),
                    AccountId = table.Column<Guid>(type: "uuid", nullable: false),
                    ExpiresAt = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_sessions", x => x.TokenHash);
                    table.ForeignKey(
                        name: "FK_sessions_accounts_AccountId",
                        column: x => x.AccountId,
                        principalTable: "accounts",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "cards",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    DashboardId = table.Column<Guid>(type: "uuid", nullable: false),
                    AuthorId = table.Column<Guid>(type: "uuid", nullable: false),
                    IsPublished = table.Column<bool>(type: "boolean", nullable: false),
                    Version = table.Column<long>(type: "bigint", nullable: false),
                    Planning = table.Column<string>(type: "jsonb", nullable: false),
                    Trip_BudgetRub = table.Column<long>(type: "bigint", nullable: false),
                    Trip_DestinationId = table.Column<string>(type: "text", nullable: false),
                    Trip_EndDate = table.Column<DateOnly>(type: "date", nullable: false),
                    Trip_Preferences = table.Column<string>(type: "text", nullable: true),
                    Trip_StartDate = table.Column<DateOnly>(type: "date", nullable: false),
                    Trip_Travelers = table.Column<int>(type: "integer", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_cards", x => x.Id);
                    table.ForeignKey(
                        name: "FK_cards_accounts_AuthorId",
                        column: x => x.AuthorId,
                        principalTable: "accounts",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "FK_cards_dashboards_DashboardId",
                        column: x => x.DashboardId,
                        principalTable: "dashboards",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "dashboard_members",
                columns: table => new
                {
                    DashboardId = table.Column<Guid>(type: "uuid", nullable: false),
                    AccountId = table.Column<Guid>(type: "uuid", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_dashboard_members", x => new { x.DashboardId, x.AccountId });
                    table.ForeignKey(
                        name: "FK_dashboard_members_accounts_AccountId",
                        column: x => x.AccountId,
                        principalTable: "accounts",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_dashboard_members_dashboards_DashboardId",
                        column: x => x.DashboardId,
                        principalTable: "dashboards",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "card_votes",
                columns: table => new
                {
                    CardId = table.Column<Guid>(type: "uuid", nullable: false),
                    AccountId = table.Column<Guid>(type: "uuid", nullable: false),
                    CardVersion = table.Column<long>(type: "bigint", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_card_votes", x => new { x.CardId, x.AccountId });
                    table.ForeignKey(
                        name: "FK_card_votes_accounts_AccountId",
                        column: x => x.AccountId,
                        principalTable: "accounts",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_card_votes_cards_CardId",
                        column: x => x.CardId,
                        principalTable: "cards",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "python_tasks",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    CardId = table.Column<Guid>(type: "uuid", nullable: false),
                    Kind = table.Column<string>(type: "text", nullable: false),
                    CardVersion = table.Column<long>(type: "bigint", nullable: false),
                    Payload = table.Column<JsonElement>(type: "jsonb", nullable: false),
                    Deadline = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
                    Generation = table.Column<string>(type: "jsonb", nullable: true),
                    GenerationBatchId = table.Column<Guid>(type: "uuid", nullable: true),
                    Targets = table.Column<string>(type: "jsonb", nullable: false),
                    NextAttemptAt = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true),
                    PollPath = table.Column<string>(type: "text", nullable: true),
                    Accepted = table.Column<bool>(type: "boolean", nullable: false),
                    Finished = table.Column<bool>(type: "boolean", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_python_tasks", x => x.Id);
                    table.ForeignKey(
                        name: "FK_python_tasks_cards_CardId",
                        column: x => x.CardId,
                        principalTable: "cards",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "IX_accounts_NormalizedEmail",
                table: "accounts",
                column: "NormalizedEmail",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_card_votes_AccountId",
                table: "card_votes",
                column: "AccountId");

            migrationBuilder.CreateIndex(
                name: "IX_cards_AuthorId",
                table: "cards",
                column: "AuthorId");

            migrationBuilder.CreateIndex(
                name: "IX_cards_DashboardId",
                table: "cards",
                column: "DashboardId");

            migrationBuilder.CreateIndex(
                name: "IX_dashboard_members_AccountId",
                table: "dashboard_members",
                column: "AccountId");

            migrationBuilder.CreateIndex(
                name: "IX_dashboards_InviteHash",
                table: "dashboards",
                column: "InviteHash",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_dashboards_OwnerId",
                table: "dashboards",
                column: "OwnerId");

            migrationBuilder.CreateIndex(
                name: "IX_python_tasks_CardId",
                table: "python_tasks",
                column: "CardId");

            migrationBuilder.CreateIndex(
                name: "IX_python_tasks_Deadline",
                table: "python_tasks",
                column: "Deadline",
                filter: "NOT \"Finished\"");

            migrationBuilder.CreateIndex(
                name: "IX_python_tasks_NextAttemptAt",
                table: "python_tasks",
                column: "NextAttemptAt",
                filter: "NOT \"Finished\"");

            migrationBuilder.CreateIndex(
                name: "IX_sessions_AccountId",
                table: "sessions",
                column: "AccountId");

            migrationBuilder.CreateIndex(
                name: "IX_sessions_ExpiresAt",
                table: "sessions",
                column: "ExpiresAt");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "card_votes");

            migrationBuilder.DropTable(
                name: "dashboard_members");

            migrationBuilder.DropTable(
                name: "python_tasks");

            migrationBuilder.DropTable(
                name: "sessions");

            migrationBuilder.DropTable(
                name: "cards");

            migrationBuilder.DropTable(
                name: "dashboards");

            migrationBuilder.DropTable(
                name: "accounts");
        }
    }
}
