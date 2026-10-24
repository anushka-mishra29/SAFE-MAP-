from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    latitude: float
    longitude: float
    area_name: str
    lighting_score: Optional[float] = None
    crowd_level: Optional[float] = None
    calculated_safety_score: Optional[float] = None
    is_demo: bool


class SafetyRequest(BaseModel):
    lighting_quality: Optional[float] = Field(None, ge=0, le=100)
    incident_count: Optional[int] = Field(None, ge=0, le=10000)
    emergency_proximity: Optional[float] = Field(None, ge=0, le=100)
    crowd_activity: Optional[float] = Field(None, ge=0, le=100)
    safety_feedback: Optional[float] = Field(None, ge=0, le=100)
    # Existing dashboard/API clients may still send these names.
    lighting_score: Optional[float] = Field(None, ge=0, le=100)
    user_feedback: Optional[float] = Field(None, ge=0, le=100)


class ReportCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=120)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    incident_type: str = Field(..., min_length=2, max_length=80)
    description: str = Field(..., min_length=3, max_length=2000)
    severity: int = Field(3, ge=1, le=5)

    @field_validator("incident_type")
    @classmethod
    def valid_incident_type(cls, value):
        allowed = {"Poor Lighting", "Harassment", "Isolated Area", "Theft", "Road Hazard", "Other"}
        value = value.strip()
        if value not in allowed:
            raise ValueError("Choose a supported incident category")
        return value

    @field_validator("title")
    @classmethod
    def nonblank_title(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Title must contain at least 3 non-space characters")
        return value

    @field_validator("description")
    @classmethod
    def nonblank_description(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Description must contain at least 3 non-space characters")
        return value


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    latitude: float
    longitude: float
    incident_type: str
    description: str
    severity: int
    status: str
    is_demo: bool
    timestamp: datetime


class SafePlaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    place_type: str
    latitude: float
    longitude: float
    contact_number: Optional[str] = None
    is_demo: bool


class SOSRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    message: str = Field("Emergency assistance requested via SafeMap.", max_length=500)

