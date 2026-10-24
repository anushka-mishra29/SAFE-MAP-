from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt
from urllib.parse import quote, urlencode, quote_plus
from urllib.request import Request, urlopen
from urllib.error import URLError
from time import monotonic, sleep
import json
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .database import get_db
from .models import Location, Report, SafePlace, SOSEvent
from .schemas import LocationOut, ReportCreate, ReportOut, SafePlaceOut, SafetyRequest, SOSRequest
from .scoring import calculate_safety

router = APIRouter(prefix="/api")
_geocode_cache = {}
_last_geocode = 0.0
_facility_cache = {}
_last_overpass = 0.0


def distance_km(lat1, lon1, lat2, lon2):
    dlat, dlon = radians(lat2-lat1), radians(lon2-lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 6371.0 * 2 * asin(sqrt(a))


@router.get("/locations", response_model=list[LocationOut])
def locations(db: Session = Depends(get_db)):
    return db.query(Location).order_by(Location.id).all()


@router.get("/search")
def search_places(q: str = Query(..., min_length=2, max_length=160)):
    """Small cached Nominatim proxy; throttled to at most one uncached request/sec."""
    global _last_geocode
    query = q.strip()
    if not query:
        raise HTTPException(422, "Enter a place to search")
    key = query.casefold()
    now = monotonic()
    cached = _geocode_cache.get(key)
    if cached and now - cached[0] < 21600:
        return {"results": cached[1], "source": "Nominatim / OpenStreetMap", "cached": True}
    delay = 1.0 - (now - _last_geocode)
    if delay > 0:
        sleep(delay)
    params = urlencode({"q": query, "format": "jsonv2", "limit": 5})
    contact = os.getenv("OSM_CONTACT", "")
    endpoint = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search").rstrip("/")
    url = endpoint + "?" + params + ("&email=" + quote(contact) if contact else "")
    request = Request(url, headers={"User-Agent": "SafeMapLocalCollegeDemo/1.0", "Accept": "application/json"})
    _last_geocode = monotonic()
    try:
        with urlopen(request, timeout=8) as response:
            results = json.loads(response.read().decode("utf-8"))
        _geocode_cache[key] = (_last_geocode, results)
        return {"results": results, "source": "Nominatim / OpenStreetMap", "cached": False}
    except (URLError, TimeoutError, ValueError) as exc:
        raise HTTPException(503, "Location search is temporarily unavailable. Check your internet connection and try again.") from exc


@router.get("/locations/nearby")
def locations_nearby(latitude: float = Query(..., ge=-90, le=90), longitude: float = Query(..., ge=-180, le=180), radius_km: float = Query(5, gt=0, le=100), db: Session = Depends(get_db)):
    return [dict(item, distance_km=round(distance_km(latitude, longitude, item["latitude"], item["longitude"]), 2))
            for item in _nearby(db.query(Location).all(), latitude, longitude, radius_km)]


@router.get("/locations/{location_id}", response_model=LocationOut)
def location_detail(location_id: int, db: Session = Depends(get_db)):
    item = db.get(Location, location_id)
    if item is None:
        raise HTTPException(404, "Location not found")
    return item


@router.post("/safety/calculate")
@router.post("/calculate-safety", include_in_schema=False)
def safety_calculate(payload: SafetyRequest):
    return calculate_safety(payload.model_dump())


@router.get("/safety/{location_id}")
def safety_for_location(location_id: int, db: Session = Depends(get_db)):
    item = db.get(Location, location_id)
    if item is None:
        raise HTTPException(404, "Location not found")
    reports = db.query(Report).filter(Report.latitude.between(item.latitude-.01, item.latitude+.01), Report.longitude.between(item.longitude-.01, item.longitude+.01)).count()
    return {"location_id": item.id, "area_name": item.area_name,
            **calculate_safety({"lighting_quality": item.lighting_score, "incident_count": reports,
                                "crowd_activity": item.crowd_level}), "data_label": "sample/demo inputs" if item.is_demo else "community data"}


@router.get("/reports", response_model=list[ReportOut])
def reports(category: str | None = None, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=300), db: Session = Depends(get_db)):
    query = db.query(Report)
    if category:
        query = query.filter(Report.incident_type == category)
    return query.order_by(Report.timestamp.desc()).offset(skip).limit(limit).all()


@router.get("/reports/{report_id}", response_model=ReportOut)
def report_detail(report_id: int, db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(404, "Report not found")
    return report


@router.post("/reports", response_model=ReportOut, status_code=201)
def create_report(payload: ReportCreate, db: Session = Depends(get_db)):
    report = Report(**payload.model_dump(), status="Community submitted", is_demo=False,
                    timestamp=datetime.now(timezone.utc))
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("/safe-places", response_model=list[SafePlaceOut])
def safe_places(db: Session = Depends(get_db)):
    return db.query(SafePlace).order_by(SafePlace.place_type, SafePlace.name).all()


@router.get("/facilities/nearby")
def facilities_nearby(latitude: float = Query(..., ge=-90, le=90), longitude: float = Query(..., ge=-180, le=180), radius_km: float = Query(10, gt=0, le=100), db: Session = Depends(get_db)):
    sample = _nearby(db.query(SafePlace).all(), latitude, longitude, radius_km)
    # Request nearby OSM data for small-radius queries; cached and throttled.
    # On service failure, return clearly labelled local demo records.
    if radius_km <= 5:
        try:
            results = _osm_facilities(latitude, longitude, radius_km)
            return results
        except (URLError, TimeoutError, ValueError):
            pass
    return sample


def _osm_facilities(lat, lon, radius_km):
    global _last_overpass
    key = (round(lat, 3), round(lon, 3), int(radius_km))
    now = monotonic()
    cached = _facility_cache.get(key)
    if cached and now - cached[0] < 1800:
        return cached[1]
    wait = 10 - (now - _last_overpass)
    if wait > 0:
        sleep(wait)
    meters = int(min(radius_km, 5) * 1000)
    query = f'[out:json][timeout:8];(node[amenity~"^(police|hospital|pharmacy|shelter)$"](around:{meters},{lat},{lon});way[amenity~"^(police|hospital|pharmacy|shelter)$"](around:{meters},{lat},{lon}););out center tags 60;'
    endpoint = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
    request = Request(endpoint, data=("data=" + quote_plus(query)).encode(), headers={"User-Agent": "SafeMapLocalCollegeDemo/1.0", "Content-Type": "application/x-www-form-urlencoded"})
    _last_overpass = monotonic()
    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    kinds = {"police": "police_station", "hospital": "hospital", "pharmacy": "pharmacy", "shelter": "shelter"}
    results = []
    for element in payload.get("elements", []):
        tags = element.get("tags", {})
        center = element.get("center", element)
        kind = kinds.get(tags.get("amenity"))
        if not kind or "lat" not in center or "lon" not in center:
            continue
        results.append({"id": -int(element.get("id", 0)), "name": tags.get("name", "Unnamed " + kind.replace("_", " ").title()), "place_type": kind, "latitude": center["lat"], "longitude": center["lon"], "contact_number": tags.get("phone"), "is_demo": False, "distance_km": round(distance_km(lat, lon, center["lat"], center["lon"]), 2)})
    results.sort(key=lambda place: place["distance_km"])
    _facility_cache[key] = (monotonic(), results)
    return results


def _nearby(rows, lat, lon, radius):
    result = []
    for row in rows:
        distance = distance_km(lat, lon, row.latitude, row.longitude)
        if distance <= radius:
            item = {k: getattr(row, k) for k in row.__table__.columns.keys()}
            item["distance_km"] = round(distance, 2)
            result.append(item)
    return sorted(result, key=lambda x: x["distance_km"])


@router.post("/sos", status_code=201)
def record_sos(payload: SOSRequest, db: Session = Depends(get_db)):
    event = SOSEvent(latitude=payload.latitude, longitude=payload.longitude)
    db.add(event)
    db.commit()
    maps_url = f"https://www.google.com/maps?q={payload.latitude},{payload.longitude}"
    message = f"{payload.message} Location: {maps_url}"
    return {"status": "recorded_locally", "message": "SOS event recorded by this SafeMap demo only. No emergency service was contacted.",
            "latitude": payload.latitude, "longitude": payload.longitude, "maps_url": maps_url,
            "sms_url": "sms:?body=" + quote(message), "whatsapp_url": "https://wa.me/?text=" + quote(message),
            "event_id": event.id}
