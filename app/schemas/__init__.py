from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.qrcodes import clean_slug, validate_destination


class QRFields(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    destination_url: str
    campaign: str | None = Field(None, max_length=180)
    source: str | None = Field(None, max_length=180)
    description: str | None = None
    active: bool = True
    utm_enabled: bool = False
    utm_source: str | None = Field(None, max_length=255)
    utm_medium: str | None = Field(None, max_length=255)
    utm_campaign: str | None = Field(None, max_length=255)
    utm_content: str | None = Field(None, max_length=255)
    utm_term: str | None = Field(None, max_length=255)

    @field_validator("name")
    @classmethod
    def name_has_slug(cls, value: str) -> str:
        value = value.strip()
        clean_slug(value)
        return value

    @field_validator("destination_url")
    @classmethod
    def url_is_safe(cls, value: str) -> str:
        return validate_destination(value)


class QRCreate(QRFields):
    slug: str | None = None

    @field_validator("slug")
    @classmethod
    def slug_is_valid(cls, value: str | None) -> str | None:
        return clean_slug(value) if value else None


class QRUpdate(QRFields):
    slug: str | None = None
    confirm_slug_change: bool = False

    @field_validator("slug")
    @classmethod
    def slug_is_valid(cls, value: str | None) -> str | None:
        return clean_slug(value) if value else None


class QROut(QRFields):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    short_url: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
