"""Public request/response contracts; validation applies before database writes."""

from datetime import date as DateValue, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.config import get_settings

Status = Literal["Pending", "In Progress", "Completed", "Blocked", "Cancelled"]
Priority = Literal["Low", "Medium", "High", "Critical"]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RegisterRequest(RequestModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=10, max_length=72)
    timezone: str = "Asia/Kolkata"

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("Use at least one letter and one number")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Unknown IANA timezone") from None
        return value


class LoginRequest(RequestModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class ProfileUpdate(RequestModel):
    name: str = Field(min_length=2, max_length=120)
    timezone: str
    notifications_enabled: bool
    _valid_timezone = field_validator("timezone")(RegisterRequest.validate_timezone.__func__)


class PasswordUpdate(RequestModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=10, max_length=72)
    _valid_password = field_validator("new_password")(RegisterRequest.validate_password.__func__)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: EmailStr
    name: str
    timezone: str
    notifications_enabled: bool
    is_demo: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class MeetingCreate(RequestModel):
    title: str = Field(min_length=2, max_length=200)
    date: DateValue
    participants: list[str] = Field(default_factory=list, max_length=100)
    meeting_type: str = Field(default="Team sync", min_length=2, max_length=80)
    project: str = Field(default="", max_length=150)
    transcript: Annotated[str, StringConstraints(strip_whitespace=False)] = Field(
        default="", max_length=get_settings().max_transcript_chars
    )

    @field_validator("participants")
    @classmethod
    def clean_participants(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for name in values:
            name = name.strip()
            if not name or len(name) > 120:
                raise ValueError("Participant names must be between 1 and 120 characters")
            if name.casefold() not in [item.casefold() for item in result]:
                result.append(name)
        return result

    @field_validator("transcript")
    @classmethod
    def text_without_nulls(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("Transcript cannot contain null bytes")
        return value


class MeetingUpdate(RequestModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    date: DateValue | None = None
    participants: list[str] | None = Field(default=None, max_length=100)
    meeting_type: str | None = Field(default=None, min_length=2, max_length=80)
    project: str | None = Field(default=None, max_length=150)
    transcript: Annotated[str, StringConstraints(strip_whitespace=False)] | None = Field(
        default=None, max_length=get_settings().max_transcript_chars
    )

    @field_validator("participants")
    @classmethod
    def clean_participants(cls, value):
        return MeetingCreate.clean_participants(value) if value is not None else value

    @field_validator("transcript")
    @classmethod
    def validate_text(cls, value):
        return MeetingCreate.text_without_nulls(value) if value is not None else value

    @model_validator(mode="after")
    def reject_nulls(self):
        if any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Meeting fields cannot be null; use an empty string where supported")
        return self


class ActionCreate(RequestModel):
    meeting_id: str = Field(min_length=36, max_length=36)
    task: str = Field(min_length=3, max_length=3000)
    owner: str = Field(default="Unassigned", min_length=1, max_length=120)
    due_date: DateValue | None = None
    priority: Priority = "Medium"
    status: Status = "Pending"
    notes: str = Field(default="", max_length=10000)
    dependencies: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("dependencies")
    @classmethod
    def valid_dependencies(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 500 for value in values):
            raise ValueError("Dependencies must be nonempty and at most 500 characters")
        return [v.strip() for v in values]


class ActionUpdate(RequestModel):
    task: str | None = Field(default=None, min_length=3, max_length=3000)
    owner: str | None = Field(default=None, min_length=1, max_length=120)
    due_date: DateValue | None = None
    priority: Priority | None = None
    status: Status | None = None
    notes: str | None = Field(default=None, max_length=10000)
    dependencies: list[str] | None = Field(default=None, max_length=30)

    @field_validator("dependencies")
    @classmethod
    def valid_dependencies(cls, values):
        return ActionCreate.valid_dependencies(values) if values is not None else values

    @model_validator(mode="after")
    def reject_nulls(self):
        if any(getattr(self, key) is None for key in self.model_fields_set if key != "due_date"):
            raise ValueError("Only due_date can be cleared with null")
        return self


class SearchRequest(RequestModel):
    query: str = Field(min_length=2, max_length=2000)
    limit: int = Field(default=8, ge=1, le=20)
    meeting_id: str | None = None


class AskRequest(SearchRequest):
    history: list[dict[str, str]] = Field(default_factory=list, max_length=12)

    @field_validator("history")
    @classmethod
    def validate_history(cls, items):
        for item in items:
            if set(item) != {"role", "content"} or item["role"] not in {"user", "assistant"}:
                raise ValueError("History needs role and content, with a user or assistant role")
            if len(item["content"]) > 4000:
                raise ValueError("History entry is too long")
        return items


class RiskUpdate(RequestModel):
    status: Literal["Open", "Resolved"]


class QuestionUpdate(RequestModel):
    status: Literal["Unanswered", "Answered"]
    answer: str = Field(default="", max_length=5000)

    @model_validator(mode="after")
    def answer_required(self):
        if self.status == "Answered" and not self.answer:
            raise ValueError("Provide an answer when resolving a question")
        if self.status == "Unanswered":
            self.answer = ""
        return self


class DocumentAttach(RequestModel):
    meeting_id: str
