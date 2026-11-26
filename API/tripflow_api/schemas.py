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
    StringConstraints,
    UrlConstraints,
    ValidationInfo,
    field_validator,
    model_validator,
)



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


class Coordinates(RequestModel):
    latitude: Annotated[float, Field(strict=True, allow_inf_nan=False, ge=-90, le=90)]
    longitude: Annotated[float, Field(strict=True, allow_inf_nan=False, ge=-180, le=180)]


class Destination(Coordinates):
    city: Annotated[StrictStr, StringConstraints(strip_whitespace=True, min_length=1)]
    countryCode: Annotated[StrictStr, StringConstraints(pattern=r"^[A-Za-z]{2}$")]

    @field_validator("countryCode")
    @classmethod
    def uppercase_country(cls, value: str) -> str:
        return value.upper()


class TripDates(RequestModel):
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


class LegacyTrip(TripDates):
    destinationId: Identifier


class LocatedTrip(TripDates):
    destination: Destination


TripContext = LocatedTrip | LegacyTrip


class AdmissionPriceQuote(RequestModel):
    amountRub: Rubles
    basis: Literal["person_admission", "group_admission"]
    kind: Literal["source", "estimate"]
    isFromPrice: StrictBool = False
    sourceUrl: NullableHttpsUrl = None


class SelectedHotel(RequestModel):
    objectId: Identifier
    price: Rubles | None


class SelectedAttraction(RequestModel):
    objectId: Identifier
    price: AdmissionPriceQuote | None


class TaskRequest(RequestModel):
    taskId: Identifier
    trip: TripContext



class RecommendationsRequest(TaskRequest):
    targets: Literal["hotels", "attractions"]
    count: PositiveInteger
    maxTotalRub: Rubles | None
    targetHotelTotalRub: PositiveInteger | None = Field(
        default=None, description="Desired total lodging cost in RUB for all travelers and nights. Used to rank hotels.")
    refinement: NullableText
    excludedObjectIds: list[Identifier] | None = Field(json_schema_extra={"uniqueItems": True})

    @field_validator("excludedObjectIds")
    @classmethod
    def validate_exclusions(cls, value: list[str] | None) -> list[str]:
        if value is None:
            return []
        if len(value) != len(set(value)):
            raise ValueError("must contain unique object IDs")
        return sorted(value)


class BudgetRequest(TaskRequest):
    selectedHotel: SelectedHotel | None
    selectedAttractions: list[SelectedAttraction]

    @field_validator("selectedHotel")
    @classmethod
    def require_known_price(cls, value: SelectedHotel | None, info: ValidationInfo) -> SelectedHotel | None:
        if isinstance(info.data.get("trip"), LocatedTrip) and value is not None and value.price is None:
            raise ValueError("expected a known group price for the selected hotel")
        return value


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


class HotelItem(RequestModel):
    objectId: Identifier
    name: Identifier
    price: Rubles
    stars: Annotated[int, Field(strict=True, ge=1, le=5)] | None
    address: Identifier | None
    coordinates: Coordinates | None
    imageUrl: HttpsUrl | None
    sourceUrl: HttpsUrl


class HotelSearchError(RequestModel):
    code: str
    message: str


class HotelBatch(RequestModel):
    status: Literal["succeeded", "partial", "failed"]
    items: list[HotelItem]
    hasMore: StrictBool | None
    error: HotelSearchError | None = None

    @model_validator(mode="after")
    def check_outcome(self):
        if self.status == "succeeded":
            if self.error:
                raise ValueError("successful search cannot have an error")
        elif self.error is None or self.hasMore is not None or bool(self.items) != (self.status == "partial"):
            raise ValueError("inconsistent interrupted search")
        return self


class HotelResults(RequestModel):
    hotels: HotelBatch


class HotelResult(RequestModel):
    taskId: Identifier
    event: Literal["recommendations.finished"] = "recommendations.finished"
    results: HotelResults


class TaskStatus(BaseModel):
    taskId: str
    status: Literal["pending", "completed"]
    result: dict | HotelResult | None = Field(
        description="Saved task result. HotelResult documents Stage 2 hotel responses. "
                    "Historical results, attractions and budget use their existing formats."
    )
