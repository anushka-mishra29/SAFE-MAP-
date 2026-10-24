"""Indicative scoring only; each input is a normalized 0-100 positive indicator.

Incident history maps count to max(0, 100 - 12.5 * count). Missing factors are
excluded and the remaining configured weights are renormalized. Fewer than
three available factors (or no incident history) is insufficient evidence.
"""
WEIGHTS = {
    "lighting_quality": 0.20,
    "incident_history": 0.30,
    "emergency_proximity": 0.20,
    "crowd_activity": 0.20,
    "safety_feedback": 0.10,
}


def score_category(score):
    if score >= 75:
        return "Safe"
    if score >= 50:
        return "Moderate"
    return "Requires Caution"


def calculate_safety(data):
    lighting = data.get("lighting_quality", data.get("lighting_score"))
    feedback = data.get("safety_feedback", data.get("user_feedback"))
    raw = {
        "lighting_quality": lighting,
        "incident_history": (max(0.0, 100.0 - 12.5 * data["incident_count"])
                             if data.get("incident_count") is not None else None),
        "emergency_proximity": data.get("emergency_proximity"),
        "crowd_activity": data.get("crowd_activity"),
        "safety_feedback": feedback,
    }
    available = {k: float(v) for k, v in raw.items() if v is not None}
    if len(available) < 3 or "incident_history" not in available:
        return {"status": "insufficient_data", "safety_score": None,
                "category": "Insufficient data", "available_factors": list(available),
                "breakdown": available, "indicative_only": True}
    weight_sum = sum(WEIGHTS[k] for k in available)
    score = round(sum(available[k] * WEIGHTS[k] for k in available) / weight_sum, 2)
    category = score_category(score)
    return {"status": "provisional", "safety_score": score, "category": category,
            "available_factors": list(available), "breakdown": available,
            "indicative_only": True}
