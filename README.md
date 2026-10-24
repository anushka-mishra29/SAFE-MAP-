# SafeMap: Public Safety Mapping Web Application

A presentation-ready college mini-project prototype built with:

- Python 3.10+
- FastAPI
- Pydantic v2
- SQLAlchemy ORM
- SQLite by default / MySQL-ready
- HTML5 + modern CSS3
- Vanilla JavaScript ES6+
- Leaflet.js
- OpenStreetMap tiles
- Nominatim geocoding
- Leaflet MarkerCluster

## 1. Project structure

```text
SafeMap/
├── main.py
├── requirements.txt
├── README.md
├── .env.example
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
└── safemap.db              # created automatically after first run
```

## 2. Run instantly with SQLite

Open a terminal in the SafeMap folder.

### Windows

```powershell
py -3.10 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open:

```text
http://127.0.0.1:8000
```

The FastAPI Swagger API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

The SQLite database `safemap.db` is created automatically.

## 3. MySQL configuration

Create a MySQL database:

```sql
CREATE DATABASE safemap CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Set the environment variable.

### Windows PowerShell

```powershell
$env:DATABASE_URL="mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/safemap"
uvicorn main:app --reload
```

### Windows CMD

```cmd
set DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/safemap
uvicorn main:app --reload
```

The SQLAlchemy models automatically create the required tables when the application starts.

## 4. API routes

### Health

```http
GET /api/health
```

### Safety locations

```http
GET /api/locations
```

### Safety score engine

```http
POST /api/calculate-safety
Content-Type: application/json
```

Example:

```json
{
  "lighting_score": 80,
  "incident_count": 2,
  "emergency_proximity": 90,
  "crowd_activity": 75,
  "user_feedback": 85
}
```

Formula:

```text
Safety Score =
    Lighting × 0.20
  + Incident Indicator × 0.30
  + Emergency Proximity × 0.20
  + Crowd Activity × 0.20
  + User Feedback × 0.10
```

The incident count is converted into a positive 0–100 indicator:

```text
incident_indicator = max(0, 100 - incident_count × 12.5)
```

Categories:

```text
75–100  -> Safe
50–74   -> Moderate
0–49    -> Requires Caution
```

### Community reports

```http
GET /api/reports
POST /api/reports
```

### Safe places

```http
GET /api/safe-places
```

### SOS

```http
POST /api/sos
```

The SOS endpoint accepts the live coordinates and returns Google Maps, SMS and WhatsApp share links. It does not silently contact emergency services.

## 5. Important demo notes

- Seed markers are explicitly sample/demo data around Jaipur; they are not claims about actual local safety conditions.
- Geolocation requires browser permission.
- For browser geolocation, using the FastAPI URL `http://127.0.0.1:8000` is preferable to opening `index.html` directly.
- Nominatim is used for place search. Respect OpenStreetMap/Nominatim usage policies for production-scale traffic.
- OpenStreetMap data/tile attribution is shown in the map.
- The SOS feature is intentionally a user-controlled location-sharing prototype rather than an automatic emergency dispatch system.
