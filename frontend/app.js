/* =========================================================
   SafeMap Frontend
   Vanilla JS + Leaflet + MarkerCluster
   ========================================================= */

const API = "/api";

const state = {
    map: null,
    userMarker: null,
    accuracyCircle: null,
    currentLat: null,
    currentLon: null,
    selectingReportLocation: false,
    selectedReportLat: null,
    selectedReportLon: null,
    safetyLayer: null,
    reportLayer: null,
    facilityLayers: {
        police_station: null,
        hospital: null,
        shelter: null
    },
    locations: [],
    reports: [],
    safePlaces: []
};

// -------------------------
// DOM helpers
// -------------------------

const $ = (id) => document.getElementById(id);

function showToast(message, type = "info") {
    const container = $("toastContainer");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateY(-5px)";
        setTimeout(() => toast.remove(), 200);
    }, 3200);
}

function openModal(id) {
    $(id).classList.remove("hidden");
}

function closeModal(id) {
    $(id).classList.add("hidden");
}

function formatNumber(value, digits = 2) {
    return Number(value).toFixed(digits);
}

function categoryForScore(score) {
    if (score >= 75) return "Safe";
    if (score >= 50) return "Moderate";
    return "Requires Caution";
}

function categoryClass(category) {
    if (category === "Safe") return "safe";
    if (category === "Moderate") return "moderate";
    return "caution";
}

// -------------------------
// Map initialization
// -------------------------

function initializeMap() {
    state.map = L.map("map", {
        zoomControl: true
    }).setView([26.9124, 75.7873], 14);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(state.map);

    state.safetyLayer = L.layerGroup().addTo(state.map);
    state.reportLayer = L.markerClusterGroup().addTo(state.map);

    state.facilityLayers.police_station = L.markerClusterGroup().addTo(state.map);
    state.facilityLayers.hospital = L.markerClusterGroup().addTo(state.map);
    state.facilityLayers.shelter = L.markerClusterGroup().addTo(state.map);

    state.map.on("click", (event) => {
        if (!state.selectingReportLocation) return;

        state.selectingReportLocation = false;
        $("reportBtn").textContent = "📝 Report an Issue";
        $("reportBtn").setAttribute("aria-pressed", "false");
        openReportAt(event.latlng.lat, event.latlng.lng);
    });
}

// -------------------------
// API helper
// -------------------------

async function apiFetch(path, options = {}) {
    const response = await fetch(`${API}${path}`, {
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
        },
        ...options
    });

    if (!response.ok) {
        let detail = "Request failed";
        try {
            const body = await response.json();
            detail = body.detail || detail;
        } catch (_) {}
        throw new Error(detail);
    }

    return response.json();
}

// -------------------------
// Safety locations
// -------------------------

function createSafetyIcon(score) {
    const category = categoryForScore(score);
    const color = category === "Safe"
        ? "#16a34a"
        : category === "Moderate"
            ? "#f59e0b"
            : "#ef4444";

    return L.divIcon({
        className: "",
        html: `<div class="safety-marker" style="background:${color}"></div>`,
        iconSize: [22, 22],
        iconAnchor: [11, 11],
        popupAnchor: [0, -12]
    });
}

function safetyPopup(location) {
    const score = Number(location.calculated_safety_score);
    const category = categoryForScore(score);
    const cls = categoryClass(category);

    const lighting = Number(location.lighting_score);
    const crowd = Number(location.crowd_level);

    // Demo breakdown values. The scoring engine endpoint can be used
    // for arbitrary inputs from the API.
    const incidentIndicator = Math.max(0, 100 - Math.round(Math.abs(100 - score) * 0.7));
    const emergency = Math.min(100, Math.max(25, Math.round(score + 5)));
    const feedback = Math.min(100, Math.max(30, Math.round(score)));

    return `
        <div class="popup-title">${escapeHtml(location.area_name)}</div>
        <span class="score-pill ${cls}">${category} · ${score}/100</span>
        <div class="breakdown">
            <div class="breakdown-row"><span>Street Lighting</span><strong>${lighting}/100</strong></div>
            <div class="breakdown-row"><span>Crowd Activity</span><strong>${crowd}/100</strong></div>
            <div class="breakdown-row"><span>Incident Indicator</span><strong>${incidentIndicator}/100</strong></div>
            <div class="breakdown-row"><span>Emergency Proximity</span><strong>${emergency}/100</strong></div>
            <div class="breakdown-row"><span>User Feedback</span><strong>${feedback}/100</strong></div>
        </div>
        <hr>
        <div style="font-size:11px">
            <strong>Nearby emergency services:</strong>
            Use the facility layers to view nearby police, hospital and safe-booth markers.
        </div>
    `;
}

function renderSafetyLocations() {
    state.safetyLayer.clearLayers();

    state.locations.forEach((location) => {
        const marker = L.marker(
            [location.latitude, location.longitude],
            { icon: createSafetyIcon(location.calculated_safety_score) }
        );

        marker.bindPopup(safetyPopup(location));
        state.safetyLayer.addLayer(marker);
    });

    $("locationCount").textContent = state.locations.length;
}

// -------------------------
// Community reports
// -------------------------

function createReportIcon() {
    return L.divIcon({
        className: "",
        html: `<div class="report-marker">!</div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
        popupAnchor: [0, -14]
    });
}

function renderReports() {
    state.reportLayer.clearLayers();

    state.reports.forEach((report) => {
        const marker = L.marker(
            [report.latitude, report.longitude],
            { icon: createReportIcon() }
        );

        marker.bindPopup(`
            <div class="popup-title">Community Report</div>
            <div class="breakdown">
                <div class="breakdown-row"><span>Type</span><strong>${escapeHtml(report.incident_type)}</strong></div>
                <div class="breakdown-row"><span>Severity</span><strong>${report.severity}/5</strong></div>
                <div class="breakdown-row"><span>Status</span><strong>${escapeHtml(report.status)}</strong></div>
                <div class="breakdown-row"><span>Time</span><strong>${new Date(report.timestamp).toLocaleString()}</strong></div>
            </div>
            <p style="font-size:11px;margin-bottom:0">${escapeHtml(report.description)}</p>
        `);

        state.reportLayer.addLayer(marker);
    });

    $("reportCount").textContent = state.reports.length;
}

// -------------------------
// Safe places / facilities
// -------------------------

function facilityIcon(type) {
    const emoji = {
        police_station: "🚓",
        hospital: "🏥",
        shelter: "🛟"
    }[type] || "📍";

    return L.divIcon({
        className: "",
        html: `<div class="facility-marker">${emoji}</div>`,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
        popupAnchor: [0, -16]
    });
}

function facilityLabel(type) {
    return {
        police_station: "Police Station",
        hospital: "Hospital",
        shelter: "Safe Booth / Pharmacy"
    }[type] || "Facility";
}

function renderSafePlaces() {
    Object.values(state.facilityLayers).forEach(layer => layer.clearLayers());

    state.safePlaces.forEach((place) => {
        const marker = L.marker(
            [place.latitude, place.longitude],
            { icon: facilityIcon(place.place_type) }
        );

        let distanceText = "Distance unavailable";
        if (state.currentLat !== null && state.currentLon !== null) {
            const km = haversineKm(
                state.currentLat,
                state.currentLon,
                place.latitude,
                place.longitude
            );
            distanceText = `${km.toFixed(2)} km from you`;
        }

        const phone = place.contact_number || "112";

        marker.bindPopup(`
            <div class="popup-title">${escapeHtml(place.name)}</div>
            <span class="score-pill safe">${facilityLabel(place.place_type)}</span>
            <div class="breakdown">
                <div class="breakdown-row"><span>Distance</span><strong>${distanceText}</strong></div>
                <div class="breakdown-row"><span>Contact</span><strong>${escapeHtml(phone)}</strong></div>
            </div>
            <div style="display:flex;gap:6px;margin-top:9px">
                <a href="tel:${encodeURIComponent(phone)}"
                   style="font-size:11px;font-weight:800;text-decoration:none">
                   📞 Call
                </a>
                <a target="_blank" rel="noopener"
                   href="https://www.google.com/maps/dir/?api=1&destination=${place.latitude},${place.longitude}"
                   style="font-size:11px;font-weight:800;text-decoration:none">
                   🗺️ Directions
                </a>
            </div>
        `);

        const layer = state.facilityLayers[place.place_type] || state.facilityLayers.shelter;
        layer.addLayer(marker);
    });

    $("placeCount").textContent = state.safePlaces.length;
}

// -------------------------
// Geolocation
// -------------------------

function locateUser(showMessage = true) {
    if (!navigator.geolocation) {
        showToast("Browser geolocation is not supported.", "error");
        return;
    }

    navigator.geolocation.getCurrentPosition(
        (position) => {
            const { latitude, longitude, accuracy } = position.coords;
            state.currentLat = latitude;
            state.currentLon = longitude;

            if (state.userMarker) {
                state.userMarker.setLatLng([latitude, longitude]);
                state.accuracyCircle.setLatLng([latitude, longitude]);
                state.accuracyCircle.setRadius(accuracy);
            } else {
                state.userMarker = L.marker([latitude, longitude])
                    .addTo(state.map)
                    .bindPopup("<strong>📍 You are here</strong>")
                    .openPopup();

                state.accuracyCircle = L.circle([latitude, longitude], {
                    radius: accuracy,
                    color: "#2563eb",
                    fillOpacity: 0.08,
                    weight: 1
                }).addTo(state.map);
            }

            state.map.setView([latitude, longitude], 16);
            renderSafePlaces();

            if (showMessage) {
                showToast("Your current location is shown on the map.", "success");
            }
        },
        (error) => {
            const message = {
                1: "Location permission was denied.",
                2: "Your location could not be determined.",
                3: "Location request timed out."
            }[error.code] || "Unable to get your location.";

            showToast(message, "error");
        },
        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 30000
        }
    );
}

// -------------------------
// Nominatim geocoding
// -------------------------

async function searchLocation() {
    const query = $("searchInput").value.trim();
    const resultBox = $("searchResults");

    if (!query) {
        showToast("Enter a place to search.", "error");
        return;
    }

    resultBox.innerHTML = "<div class='search-result'>Searching...</div>";

    try {
        const url = new URL("https://nominatim.openstreetmap.org/search");
        url.searchParams.set("q", query);
        url.searchParams.set("format", "json");
        url.searchParams.set("limit", "5");

        const response = await fetch(url.toString(), {
            headers: {
                "Accept": "application/json"
            }
        });

        if (!response.ok) {
            throw new Error("Geocoding service unavailable");
        }

        const results = await response.json();

        if (!results.length) {
            resultBox.innerHTML = "<div class='search-result'>No locations found.</div>";
            return;
        }

        resultBox.innerHTML = "";

        results.forEach((result) => {
            const item = document.createElement("div");
            item.className = "search-result";
            item.textContent = result.display_name;

            item.addEventListener("click", () => {
                const lat = Number(result.lat);
                const lon = Number(result.lon);

                state.map.setView([lat, lon], 16);
                openReportAt(lat, lon, false);
                closeModal("reportModal");
                resultBox.innerHTML = "";
            });

            resultBox.appendChild(item);
        });
    } catch (error) {
        resultBox.innerHTML = "";
        showToast("Could not search Nominatim right now.", "error");
    }
}

// -------------------------
// Reporting
// -------------------------

function openReportAt(lat, lon, showModal = true) {
    state.selectedReportLat = lat;
    state.selectedReportLon = lon;

    $("reportLat").value = lat;
    $("reportLon").value = lon;
    $("reportCoordinates").textContent =
        `${formatNumber(lat, 5)}, ${formatNumber(lon, 5)}`;

    if (showModal) {
        openModal("reportModal");
    }
}

async function submitReport(event) {
    event.preventDefault();

    const lat = Number($("reportLat").value);
    const lon = Number($("reportLon").value);

    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
        showToast("Please select a location on the map first.", "error");
        return;
    }

    const payload = {
        latitude: lat,
        longitude: lon,
        incident_type: $("incidentType").value,
        description: $("description").value.trim(),
        severity: Number($("severity").value)
    };

    if (!payload.incident_type || !payload.description) {
        showToast("Please complete all report fields.", "error");
        return;
    }

    try {
        const report = await apiFetch("/reports", {
            method: "POST",
            body: JSON.stringify(payload)
        });

        // Immediate marker update without refreshing the page.
        state.reports.unshift(report);
        renderReports();

        closeModal("reportModal");
        $("reportForm").reset();
        $("severity").value = 3;
        $("severityValue").textContent = "3";

        showToast("Report submitted and added to the map.", "success");
    } catch (error) {
        showToast(error.message, "error");
    }
}

// -------------------------
// SOS
// -------------------------

function playAlertSound() {
    try {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (!AudioContextClass) return;

        const ctx = new AudioContextClass();
        const oscillator = ctx.createOscillator();
        const gain = ctx.createGain();

        oscillator.type = "sine";
        oscillator.frequency.value = 880;
        gain.gain.value = 0.04;

        oscillator.connect(gain);
        gain.connect(ctx.destination);

        oscillator.start();
        setTimeout(() => {
            oscillator.stop();
            ctx.close();
        }, 500);
    } catch (_) {
        // Audio may be blocked by browser policy; UI still works.
    }
}

async function triggerSOS() {
    openModal("sosModal");
    $("sosStatus").textContent = "Getting your current location...";
    $("sosCoordinates").textContent = "Locating...";
    playAlertSound();

    if (!navigator.geolocation) {
        $("sosStatus").textContent = "Geolocation is not supported by this browser.";
        return;
    }

    navigator.geolocation.getCurrentPosition(
        async (position) => {
            const { latitude, longitude } = position.coords;

            state.currentLat = latitude;
            state.currentLon = longitude;

            const mapsUrl = `https://www.google.com/maps?q=${latitude},${longitude}`;
            $("sosCoordinates").textContent =
                `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`;

            $("mapsLink").href = mapsUrl;

            try {
                const result = await apiFetch("/sos", {
                    method: "POST",
                    body: JSON.stringify({
                        latitude,
                        longitude,
                        user_name: "SafeMap User",
                        message: "Emergency assistance requested via SafeMap."
                    })
                });

                $("smsLink").href = result.sms_url;
                $("whatsappLink").href = result.whatsapp_url;
                $("mapsLink").href = result.maps_url;
                $("sosStatus").textContent =
                    "SOS payload prepared. Choose how you want to share your location.";

                showToast("SOS location captured successfully.", "success");
            } catch (error) {
                $("sosStatus").textContent =
                    "Location captured, but the SafeMap API could not be reached.";

                const fallbackText =
                    `Emergency assistance requested. Location: ${mapsUrl}`;

                $("smsLink").href = `sms:?body=${encodeURIComponent(fallbackText)}`;
                $("whatsappLink").href =
                    `https://wa.me/?text=${encodeURIComponent(fallbackText)}`;
                $("mapsLink").href = mapsUrl;
            }
        },
        (error) => {
            $("sosStatus").textContent =
                error.code === 1
                    ? "Location permission was denied."
                    : "Unable to get your current location.";
        },
        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0
        }
    );
}

// -------------------------
// Theme
// -------------------------

function loadTheme() {
    const saved = localStorage.getItem("safemap-theme") || "light";
    document.documentElement.setAttribute("data-theme", saved);
    $("themeToggle").textContent = saved === "dark" ? "🌙" : "☀️";
}

function toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    const next = current === "dark" ? "light" : "dark";

    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("safemap-theme", next);
    $("themeToggle").textContent = next === "dark" ? "🌙" : "☀️";
}

// -------------------------
// Layer toggles
// -------------------------

function setupLayerToggles() {
    $("policeToggle").addEventListener("change", (event) => {
        toggleLayer("police_station", event.target.checked);
    });

    $("hospitalToggle").addEventListener("change", (event) => {
        toggleLayer("hospital", event.target.checked);
    });

    $("shelterToggle").addEventListener("change", (event) => {
        toggleLayer("shelter", event.target.checked);
    });

    $("reportsToggle").addEventListener("change", (event) => {
        if (event.target.checked) {
            state.reportLayer.addTo(state.map);
        } else {
            state.map.removeLayer(state.reportLayer);
        }
    });
}

function toggleLayer(type, visible) {
    const layer = state.facilityLayers[type];
    if (!layer) return;

    if (visible) {
        layer.addTo(state.map);
    } else {
        state.map.removeLayer(layer);
    }
}

// -------------------------
// Load initial data
// -------------------------

async function loadData() {
    try {
        const [locations, reports, safePlaces] = await Promise.all([
            apiFetch("/locations"),
            apiFetch("/reports"),
            apiFetch("/safe-places")
        ]);

        state.locations = locations;
        state.reports = reports;
        state.safePlaces = safePlaces;

        renderSafetyLocations();
        renderReports();
        renderSafePlaces();

        $("apiStatus").classList.add("online");
        $("apiStatus").title = "SafeMap API connected";
    } catch (error) {
        $("apiStatus").title = "SafeMap API unavailable";
        showToast("Could not load SafeMap data. Is the FastAPI server running?", "error");
    }
}

// -------------------------
// Utility
// -------------------------

function haversineKm(lat1, lon1, lat2, lon2) {
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;

    const a =
        Math.sin(dLat / 2) ** 2 +
        Math.cos(lat1 * Math.PI / 180) *
        Math.cos(lat2 * Math.PI / 180) *
        Math.sin(dLon / 2) ** 2;

    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

// -------------------------
// Event wiring
// -------------------------

function setupEvents() {
    $("themeToggle").addEventListener("click", toggleTheme);
    $("locateBtn").addEventListener("click", () => locateUser(true));

    $("searchBtn").addEventListener("click", searchLocation);
    $("searchInput").addEventListener("keydown", (event) => {
        if (event.key === "Enter") searchLocation();
    });

    $("reportBtn").addEventListener("click", () => {
        state.selectingReportLocation = !state.selectingReportLocation;
        const button = $("reportBtn");
        button.textContent = state.selectingReportLocation
            ? "📍 Click map to choose location"
            : "📝 Report an Issue";
        button.setAttribute("aria-pressed", String(state.selectingReportLocation));
        showToast(
            state.selectingReportLocation
                ? "Click the map once to place your report."
                : "Report location selection cancelled."
        );
    });

    $("reportForm").addEventListener("submit", submitReport);

    $("severity").addEventListener("input", (event) => {
        $("severityValue").textContent = event.target.value;
    });

    $("sosBtn").addEventListener("click", triggerSOS);

    document.querySelectorAll("[data-close]").forEach((button) => {
        button.addEventListener("click", () => closeModal(button.dataset.close));
    });

    document.querySelectorAll(".modal").forEach((modal) => {
        modal.addEventListener("click", (event) => {
            if (event.target === modal) {
                modal.classList.add("hidden");
            }
        });
    });

    setupLayerToggles();
}

// -------------------------
// Boot
// -------------------------

document.addEventListener("DOMContentLoaded", () => {
    loadTheme();
    initializeMap();
    setupEvents();
    loadData();
});
