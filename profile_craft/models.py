"""Pydantic data contracts.

Every record entering the database (from the UI or the batch pipeline) is
validated against these models first, so bad data is rejected at the edge
instead of silently corrupting downstream tables.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
YEAR_RE = re.compile(r"(19|20)\d{2}")
CURRENT_WORDS = {"present", "current", "now", "ongoing"}


class _Base(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")


class Education(_Base):
    school: str = Field(min_length=1, max_length=200)
    degree: str = Field(min_length=1, max_length=200)
    graduation_year: int | None = Field(default=None, ge=1950, le=2100)

    @model_validator(mode="before")
    @classmethod
    def _legacy_year(cls, data):
        # Legacy JSON exports used "year" instead of "graduation_year".
        if isinstance(data, dict) and "graduation_year" not in data and "year" in data:
            data = {**data, "graduation_year": data["year"]}
        return data

    @field_validator("graduation_year", mode="before")
    @classmethod
    def _parse_year(cls, v):
        if v in (None, ""):
            return None
        if isinstance(v, int):
            return v
        match = YEAR_RE.search(str(v))
        if not match:
            raise ValueError(f"could not find a year in {v!r}")
        return int(match.group(0))


class Experience(_Base):
    company: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=200)
    start_year: int | None = Field(default=None, ge=1950, le=2100)
    end_year: int | None = Field(default=None, ge=1950, le=2100)
    description: str = Field(default="", max_length=5000)

    @model_validator(mode="before")
    @classmethod
    def _split_duration(cls, data):
        """Accept the legacy free-text ``duration`` field, e.g. '2022 - 2024' or '2025 - Present'."""
        if isinstance(data, dict) and "duration" in data and "start_year" not in data:
            text = str(data.get("duration") or "")
            years = [int(y.group(0)) for y in YEAR_RE.finditer(text)]
            data = {**data}
            data["start_year"] = years[0] if years else None
            is_current = any(w in text.lower() for w in CURRENT_WORDS)
            data["end_year"] = None if is_current else (years[1] if len(years) > 1 else None)
        return data

    @model_validator(mode="after")
    def _check_range(self):
        if self.start_year and self.end_year and self.end_year < self.start_year:
            raise ValueError("end_year cannot be before start_year")
        return self

    @property
    def duration(self) -> str:
        if not self.start_year:
            return ""
        return f"{self.start_year} - {self.end_year or 'Present'}"


class Certification(_Base):
    name: str = Field(min_length=1, max_length=200)


class Profile(_Base):
    full_name: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=254)
    phone: str = Field(default="", max_length=40)
    location: str = Field(default="", max_length=200)
    summary: str = Field(default="", max_length=3000)
    education: list[Education] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _legacy_name(cls, data):
        # Legacy JSON exports used "name" instead of "full_name".
        if isinstance(data, dict) and "full_name" not in data and "name" in data:
            data = {**data, "full_name": data["name"]}
        return data

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        if v and not EMAIL_RE.match(v):
            raise ValueError(f"invalid email address: {v!r}")
        return v.lower()

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, v: str) -> str:
        if not v:
            return v
        digits = re.sub(r"\D", "", v)
        if not 7 <= len(digits) <= 15:
            raise ValueError("phone number must contain 7-15 digits")
        return v

    def completeness(self) -> float:
        """Share of resume sections filled in, 0.0-1.0."""
        checks = [
            bool(self.full_name),
            bool(self.email),
            bool(self.phone),
            bool(self.location),
            bool(self.summary),
            bool(self.education),
            bool(self.experience),
            bool(self.certifications),
        ]
        return sum(checks) / len(checks)
