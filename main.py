from datetime import datetime, timezone
from math import radians, sin, cos, asin, sqrt
import os
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

# ============================================================
# Configuration
# ============================================================

# Default: instant zero-setup SQLite demo.
# For MySQL, set:
# DATABASE_URL=mysql+pymysql://root:password@localhost:3306/safemap
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./safemap.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

app = FastAPI(
    title="SafeMap API",
    description="Public Safety Mapping Web Application",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For a college prototype/demo. Restrict in production.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# Database models
# ============================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(160), unique=True, nullable=False)
    phone = Column(String(30), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    reports = relationship("Report", back_populates="user")


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    area_name = Column(String(180), nullable=False)
    lighting_score = Column(Float, default=70)
    crowd_level = Column(Float, default=70)
    calculated_safety_score = Column(Float, default=70)


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    incident_type = Column(String(80), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(Integer, nullable=False)
    status = Column(String(40), default="Open")
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="reports")


class SafePlace(Base):
    __tablename__ = "safe_places"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(180), nullable=False)
    place_type = Column(String(50), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    contact_number = Column(String(40), nullable=True)


Base.metadata.create_all(bind=engine)

# ============================================================
# Pydantic schemas
# ============================================================

class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    latitude: float
    longitude: float
    area_name: str
    lighting_score: float
    crowd_level: float
    calculated_safety_score: float


class SafetyRequest(BaseModel):
    lighting_score: float = Field(..., ge=0, le=100)
    incident_count: int = Field(0, ge=0)
    emergency_proximity: float = Field(70, ge=0, le=100)
    crowd_activity: float = Field(..., ge=0, le=100)
    user_feedback: float = Field(70, ge=0, le=100)


class SafetyResponse(BaseModel):
    safety_score: float
    category: str
    breakdown: dict


class ReportCreate(BaseModel):
    user_id: Optional[int] = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    incident_type: str
    description: str = Field(..., min_length=3, max_length=2000)
    severity: int = Field(..., ge=1, le=5)
    timestamp: Optional[datetime] = None


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int]
    latitude: float
    longitude: float
    incident_type: str
    description: str
    severity: int
    status: str
    timestamp: datetime


class SafePlaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    place_type: str
    latitude: float
    longitude: float
    contact_number: Optional[str]


class SOSRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    user_name: Optional[str] = "SafeMap User"
    user_phone: Optional[str] = None
    message: Optional[str] = "Emergency assistance requested via SafeMap."


class SOSResponse(BaseModel):
    status: str
    message: str
    latitude: float
    longitude: float
    maps_url: str
    sms_url: str
    whatsapp_url: str


# ============================================================
# Dependencies and helpers
# ============================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def haversine_km(lat1, lon1, lat2, lon2):
    """Distance between two latitude/longitude points in km."""
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def score_category(score: float) -> str:
    if score >= 75:
        return "Safe"
    if score >= 50:
        return "Moderate"
    return "Requires Caution"


def calculate_score(
    lighting_score: float,
    incident_count: int,
    emergency_proximity: float,
    crowd_activity: float,
    user_feedback: float,
):
    # Incident penalty is converted to a 0-100 positive indicator.
    # More reports => lower incident component.
    incident_indicator = max(0.0, 100.0 - min(100.0, incident_count * 12.5))

    score = (
        lighting_score * 0.20
        + incident_indicator * 0.30
        + emergency_proximity * 0.20
        + crowd_activity * 0.20
        + user_feedback * 0.10
    )
    score = round(max(0.0, min(100.0, score)), 2)

    return score, {
        "street_lighting": round(lighting_score, 2),
        "incident_reports": round(incident_indicator, 2),
        "emergency_proximity": round(emergency_proximity, 2),
        "crowd_activity": round(crowd_activity, 2),
        "user_feedback": round(user_feedback, 2),
    }


def nearest_emergency_score(db: Session, lat: float, lon: float) -> float:
    places = db.query(SafePlace).all()
    emergency_types = {"police_station", "hospital", "shelter"}
    distances = [
        haversine_km(lat, lon, p.latitude, p.longitude)
        for p in places if p.place_type in emergency_types
    ]
    if not distances:
        return 50.0

    nearest = min(distances)
    # 100 at 0 km, decreasing gradually; 5 km+ is treated as low proximity.
    return round(max(0.0, min(100.0, 100.0 - nearest * 20.0)), 2)


def seed_demo_data():
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            db.add(User(
                name="Demo User",
                email="demo@safemap.local",
                phone="+919999999999"
            ))

        if db.query(Location).count() == 0:
            # Demo coordinates around central Jaipur. They are sample/prototype
            # data and are not claims about actual safety conditions.
            locations = [
                Location(
                    latitude=26.9124, longitude=75.7873,
                    area_name="Central Demo Zone",
                    lighting_score=92, crowd_level=88,
                    calculated_safety_score=88
                ),
                Location(
                    latitude=26.9157, longitude=75.8000,
                    area_name="Moderate Demo Zone",
                    lighting_score=68, crowd_level=62,
                    calculated_safety_score=67
                ),
                Location(
                    latitude=26.9055, longitude=75.7950,
                    area_name="Caution Demo Zone",
                    lighting_score=42, crowd_level=35,
                    calculated_safety_score=43
                ),
                Location(
                    latitude=26.9200, longitude=75.8100,
                    area_name="Campus Demo Zone",
                    lighting_score=84, crowd_level=78,
                    calculated_safety_score=81
                ),
            ]
            db.add_all(locations)

        if db.query(SafePlace).count() == 0:
            places = [
                SafePlace(
                    name="Demo Police Station",
                    place_type="police_station",
                    latitude=26.9147, longitude=75.7922,
                    contact_number="100"
                ),
                SafePlace(
                    name="Demo City Hospital",
                    place_type="hospital",
                    latitude=26.9092, longitude=75.8014,
                    contact_number="108"
                ),
                SafePlace(
                    name="SafeMap Safe Booth",
                    place_type="shelter",
                    latitude=26.9185, longitude=75.8040,
                    contact_number="112"
                ),
                SafePlace(
                    name="24/7 Demo Pharmacy",
                    place_type="shelter",
                    latitude=26.9077, longitude=75.7895,
                    contact_number="102"
                ),
            ]
            db.add_all(places)

        db.commit()
    finally:
        db.close()


@app.on_event("startup")
def startup_event():
    seed_demo_data()


# ============================================================
# REST API routes
# ============================================================

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "SafeMap API"}


@app.get("/api/locations", response_model=list[LocationOut])
def get_locations(db: Session = Depends(get_db)):
    return db.query(Location).order_by(Location.id).all()


@app.post("/api/calculate-safety", response_model=SafetyResponse)
def calculate_safety(payload: SafetyRequest):
    score, breakdown = calculate_score(
        payload.lighting_score,
        payload.incident_count,
        payload.emergency_proximity,
        payload.crowd_activity,
        payload.user_feedback,
    )
    return SafetyResponse(
        safety_score=score,
        category=score_category(score),
        breakdown=breakdown,
    )


@app.get("/api/reports", response_model=list[ReportOut])
def get_reports(db: Session = Depends(get_db)):
    return db.query(Report).order_by(Report.timestamp.desc()).limit(300).all()


@app.post("/api/reports", response_model=ReportOut, status_code=201)
def create_report(payload: ReportCreate, db: Session = Depends(get_db)):
    if payload.user_id is not None and not db.get(User, payload.user_id):
        raise HTTPException(status_code=404, detail="User not found")

    report = Report(
        user_id=payload.user_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        incident_type=payload.incident_type,
        description=payload.description,
        severity=payload.severity,
        status="Open",
        timestamp=payload.timestamp or datetime.now(timezone.utc),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@app.get("/api/safe-places", response_model=list[SafePlaceOut])
def get_safe_places(db: Session = Depends(get_db)):
    return db.query(SafePlace).order_by(SafePlace.place_type, SafePlace.name).all()


@app.post("/api/sos", response_model=SOSResponse)
def trigger_sos(payload: SOSRequest):
    # Prototype behavior: logs/accepts an alert and returns shareable links.
    # It does NOT silently contact emergency services.
    maps_url = f"https://www.google.com/maps?q={payload.latitude},{payload.longitude}"
    text = (
        f"{payload.message} "
        f"Location: {maps_url}"
    )
    sms_url = "sms:?body=" + text.replace(" ", "%20")
    whatsapp_url = "https://wa.me/?text=" + text.replace(" ", "%20")

    print(
        f"[SOS] user={payload.user_name!r} "
        f"phone={payload.user_phone!r} "
        f"lat={payload.latitude} lon={payload.longitude}"
    )

    return SOSResponse(
        status="accepted",
        message="SOS payload received by SafeMap prototype.",
        latitude=payload.latitude,
        longitude=payload.longitude,
        maps_url=maps_url,
        sms_url=sms_url,
        whatsapp_url=whatsapp_url,
    )


# ============================================================
# Serve frontend from the same FastAPI app
# ============================================================

@app.get("/", include_in_schema=False)
def serve_frontend():
    return FileResponse("frontend/index.html")


@app.get("/style.css", include_in_schema=False)
def serve_css():
    return FileResponse("frontend/style.css", media_type="text/css")


@app.get("/app.js", include_in_schema=False)
def serve_js():
    return FileResponse("frontend/app.js", media_type="application/javascript")

if __name__ == "__main__":
    # Run this file directly from VS Code's Run button.
    import threading
    import webbrowser
    import uvicorn

    app_url = "http://127.0.0.1:8000"
    threading.Timer(1.0, lambda: webbrowser.open(app_url)).start()
    uvicorn.run(app, host="127.0.0.1", port=8000)