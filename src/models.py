"""Typed inputs and outputs for the agent's tools and its final answer (Pydantic).

Tool inputs are validated here before any tool runs, so a malformed call from the model becomes an error result the
model can correct, never an exception in the app.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RoomType = Literal["Standard King", "Ocean View King", "Suite", "Standard Queen", "Cabin"]
Department = Literal["front_desk", "housekeeping", "maintenance", "concierge", "reservations", "spa", "food_beverage"]
ActionType = Literal["refund", "comp", "upgrade", "cancellation", "rate_change", "date_change", "fee_waiver", "other"]
RequestKind = Literal["booking", "availability", "policy", "service", "change", "complaint", "other"]
RequestStatus = Literal["answered", "task_proposed", "needs_manager_approval", "cannot_do", "needs_info", "escalated"]

DEPARTMENTS: tuple[str, ...] = Department.__args__
ACTION_TYPES: tuple[str, ...] = ActionType.__args__
REQUEST_KINDS: tuple[str, ...] = RequestKind.__args__
REQUEST_STATUSES: tuple[str, ...] = RequestStatus.__args__


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------- Tool inputs (what the model may send) ----------
class FindBookingInput(Strict):
    booking_ref: str | None = Field(None, max_length=20, description="Booking reference the guest gave, e.g. BR-1042")
    guest_name: str | None = Field(None, max_length=80, description="Name the guest signed with")


class CheckAvailabilityInput(Strict):
    property: Literal["beach-resort", "mountain-lodge"]
    check_in: date
    check_out: date
    room_type: RoomType | None = None

    @field_validator("check_out")
    @classmethod
    def after_check_in(cls, v: date, info):
        start = info.data.get("check_in")
        if start and v <= start:
            raise ValueError("check_out must be after check_in")
        if start and (v - start).days > 14:
            raise ValueError("stays longer than 14 nights can't be checked here")
        return v


class SearchPolicyInput(Strict):
    question: str = Field(min_length=2, max_length=300)
    property: Literal["beach-resort", "mountain-lodge"] | None = None


class ProposeTaskInput(Strict):
    department: Department
    title: str = Field(min_length=3, max_length=120)
    details: str = Field("", max_length=600)
    booking_id: str | None = Field(None, max_length=20)


class ProposeActionInput(Strict):
    action_type: ActionType
    reason: str = Field(min_length=3, max_length=600)
    booking_id: str | None = Field(None, max_length=20)
    amount_usd: float | None = Field(None, ge=0, le=100_000)


class RequestItem(Strict):
    summary: str = Field(min_length=2, max_length=200)
    kind: RequestKind
    status: RequestStatus


class DraftReplyInput(Strict):
    requests: list[RequestItem] = Field(min_length=1, max_length=12)
    reply: str = Field(min_length=10, max_length=4000)
    escalate: bool = False
    escalation_reason: str = Field("", max_length=300)
    language: str = Field("en", max_length=10)


# ---------- What the app keeps ----------
class Booking(BaseModel):
    booking_id: str
    property: str
    guest_name: str
    email: str
    loyalty_tier: str  # "none" | "Silver" | "Gold" | "Platinum"
    member_number: str | None
    room_type: str
    room_number: str
    check_in: date
    check_out: date
    adults: int
    children: int
    rate_plan: str  # "Flexible" | "Non-refundable"
    nightly_rate: int
    status: str  # confirmed | checked_in | checked_out | cancelled | no_show
    notes: str = ""

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days

    @property
    def total(self) -> int:
        return self.nightly_rate * self.nights


class Task(BaseModel):
    id: str
    department: str
    title: str
    details: str = ""
    booking_id: str | None = None
    status: str = "proposed"  # proposed -> open (after approval) | discarded


class Action(BaseModel):
    id: str
    action_type: str
    reason: str
    booking_id: str | None = None
    amount_usd: float | None = None
    status: str = "needs manager approval"  # never anything else: the agent can't approve


class Step(BaseModel):
    """One line in the step timeline: a triage check, a tool call, a model turn or a guard."""

    n: int
    kind: Literal["triage", "tool", "model", "guard", "fallback"]
    name: str
    summary: str
    ok: bool = True
    args: dict = Field(default_factory=dict)
    result: dict | list | str | None = None
    ms: int | None = None


class AgentResult(BaseModel):
    outcome: Literal["drafted", "escalated", "fallback", "greeting", "off_topic", "error", "cap"]
    reply: str = ""  # the draft staff see (after the guard), with [P1]-style citation markers
    raw_reply: str = ""  # exactly what the model wrote, before the guard
    requests: list[RequestItem] = Field(default_factory=list)
    escalate: bool = False
    escalation_reasons: list[str] = Field(default_factory=list)
    language: str = "en"
    citations: list[dict] = Field(default_factory=list)  # cited policy passages
    bookings: list[dict] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)
    flags: dict = Field(default_factory=dict)
    model: str | None = None
    api_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    latency_s: float = 0.0
    fallback_reason: str | None = None
    message: str = ""  # friendly text for greeting / off-topic / cap outcomes
    sources: list[str] = Field(default_factory=list)  # every tool result as text (kept in eval records for re-scoring)
