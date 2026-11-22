from datetime import date
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AnyUrl,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    UrlConstraints,
    ValidationInfo,
    field_validator,
    with_config,
)
from typing_extensions import TypedDict



def nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("expected a nonblank string")
    return value


def blank_to_none(value: str | None) -> str | None:
    return None if value is not None and not value.strip() else value


def blank_url_to_none(value: object) -> object:
    return blank_to_none(value) if isinstance(value, str) else value


def parse_date(value: object) -> date:
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            pass
        else:
            if parsed.isoformat() == value:
                return parsed
    raise ValueError("expected a date in YYYY-MM-DD format")


Identifier = Annotated[StrictStr, Field(min_length=1), AfterValidator(nonblank)]
NullableText = Annotated[StrictStr | None, AfterValidator(blank_to_none)]
CalendarDate = Annotated[date, BeforeValidator(parse_date)]
PositiveInteger = Annotated[int, Field(strict=True, gt=0)]
Rubles = Annotated[int, Field(strict=True, ge=0)]
HttpsUrl = Annotated[AnyUrl, UrlConstraints(allowed_schemes=["https"], host_required=True)]
NullableHttpsUrl = Annotated[HttpsUrl | None, BeforeValidator(blank_url_to_none)]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TripContext(RequestModel):
    destinationId: Identifier
    startDate: CalendarDate
    endDate: CalendarDate
    travelers: PositiveInteger
    budgetRub: PositiveInteger
    preferences: NullableText

    @field_validator("endDate")
    @classmethod
    def validate_end_date(cls, value: date, info: ValidationInfo) -> date:
        start_date = info.data.get("startDate")
        if start_date is not None and value < start_date:
            raise ValueError("must be on or after startDate")
        return value


class RecommendationTarget(RequestModel):
    count: PositiveInteger
    maxTotalRub: Rubles | None
    refinement: NullableText = None
    excludedObjectIds: list[Identifier] = Field(
        default_factory=list, json_schema_extra={"uniqueItems": True}
    )

    @field_validator("excludedObjectIds")
    @classmethod
    def validate_exclusions(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("must contain unique object IDs")
        return sorted(value)


@with_config(ConfigDict(extra="forbid"))
class RecommendationTargets(TypedDict, total=False):
    hotels: RecommendationTarget
    attractions: RecommendationTarget


class AdmissionPriceQuote(RequestModel):
    amountRub: Rubles
    basis: Literal["person_admission", "group_admission"]
    kind: Literal["source", "estimate"]
    isFromPrice: StrictBool = False
    sourceUrl: NullableHttpsUrl = None


class IncludedService(RequestModel):
    service: Identifier
    status: Literal["confirmed", "contradicted", "unknown"]
    dates: list[CalendarDate] | None
    sourceUrl: NullableHttpsUrl

    @field_validator("sourceUrl")
    @classmethod
    def validate_source(cls, value: HttpsUrl | None, info: ValidationInfo) -> HttpsUrl | None:
        if value is None and info.data.get("status") == "confirmed":
            raise ValueError("is required for a confirmed service")
        return value


class TariffSnapshot(RequestModel):
    name: NullableText
    includedServices: list[IncludedService]


class SelectedHotel(RequestModel):
    objectId: Identifier
    price: Rubles | None
    tariff: TariffSnapshot


class SelectedAttraction(RequestModel):
    objectId: Identifier
    price: AdmissionPriceQuote | None


class TaskRequest(RequestModel):
    taskId: Identifier
    trip: TripContext



class RecommendationsRequest(TaskRequest):
    targets: RecommendationTargets = Field(json_schema_extra={"minProperties": 1})

    @field_validator("targets")
    @classmethod
    def validate_targets(cls, value: RecommendationTargets) -> RecommendationTargets:
        if not value:
            raise ValueError("request hotels, attractions, or both")
        return value


class BudgetRequest(TaskRequest):
    selectedHotel: SelectedHotel | None
    selectedAttractions: list[SelectedAttraction]


class TaskAccepted(BaseModel):
    taskId: str
    status: Literal["accepted"] = "accepted"


class ErrorDetail(BaseModel):
    code: str
    message: str
    fields: dict[str, list[str]] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    taskId: str | None
    error: ErrorDetail


class TaskStatus(BaseModel):
    taskId: str
    status: Literal["pending", "completed"]
    result: dict | None
