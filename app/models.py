from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class Location(Base):
    __tablename__ = "locations"
    id = Column(Integer, primary_key=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    area_name = Column(String(180), nullable=False)
    lighting_score = Column(Float)
    crowd_level = Column(Float)
    calculated_safety_score = Column(Float)
    is_demo = Column(Boolean, default=True, nullable=False)


class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True)
    title = Column(String(120), nullable=False, default="Community report")
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    incident_type = Column(String(80), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(Integer, nullable=False, default=3)
    status = Column(String(40), nullable=False, default="Community submitted")
    is_demo = Column(Boolean, nullable=False, default=False)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class SafePlace(Base):
    __tablename__ = "safe_places"
    id = Column(Integer, primary_key=True)
    name = Column(String(180), nullable=False)
    place_type = Column(String(50), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    contact_number = Column(String(40))
    is_demo = Column(Boolean, default=True, nullable=False)


class SOSEvent(Base):
    __tablename__ = "sos_events"
    id = Column(Integer, primary_key=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
