"""Demo 11 tools: REAL keyless public APIs (no token, no auth).

Three tools hit real endpoints via the Python stdlib (urllib), so the booth
demo works with live data and no secrets to manage:
- geocode_place       -> Open-Meteo Geocoding  (place name -> lat/lon)
- climate_summary     -> Open-Meteo Archive     (historical climate)
- wikipedia_summary   -> Wikipedia REST         (destination overview)

Booth resilience: every real response is cached the first time it succeeds, and
each tool has a small hardcoded fallback for a handful of well-known cities. If
the real API is slow/down at the event, the tool still returns real-or-cached
data instead of breaking the demo. The CHAOS in this demo is injected
deterministically by hooks (see hooks.py) -- it is NOT a real API failure.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

from strands import tool

_UA = {"User-Agent": "strands-demos-chaos-resilience/1.0"}
_TIMEOUT = 10

# In-process cache: once a real call succeeds, reuse it for the session.
_CACHE: dict = {}

# Offline fallback for a few well-known places, so the booth demo always has
# real-looking data even if every network path fails. Coordinates are the
# cities' actual coordinates; climate numbers are representative annual means.
_FALLBACK_GEO = {
    "lisbon": {"name": "Lisbon", "country": "Portugal", "latitude": 38.7167, "longitude": -9.1333},
    "kyoto": {"name": "Kyoto", "country": "Japan", "latitude": 35.0116, "longitude": 135.7681},
    "bogota": {"name": "Bogotá", "country": "Colombia", "latitude": 4.6097, "longitude": -74.0817},
}
_FALLBACK_CLIMATE = {
    (38.7167, -9.1333): {"avg_temp_c": 17.4, "total_precip_mm": 725.0},
    (35.0116, 135.7681): {"avg_temp_c": 15.9, "total_precip_mm": 1490.0},
    (4.6097, -74.0817): {"avg_temp_c": 14.3, "total_precip_mm": 840.0},
}


def _get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
        return json.load(response)


@tool
def geocode_place(place: str) -> str:
    """Resolve a place name to its country and coordinates.

    Args:
        place: A city or place name, e.g. "Lisbon".
    """
    key = f"geo:{place.strip().lower()}"
    if key in _CACHE:
        return _CACHE[key]
    try:
        url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
            {"name": place, "count": 1}
        )
        results = _get_json(url).get("results") or []
        if not results:
            raise ValueError("no results")
        r = results[0]
        out = json.dumps(
            {
                "name": r.get("name"),
                "country": r.get("country"),
                "latitude": r.get("latitude"),
                "longitude": r.get("longitude"),
                "source": "open-meteo-geocoding",
            }
        )
        _CACHE[key] = out
        return out
    except (urllib.error.URLError, ValueError, KeyError, TimeoutError):
        fb = _FALLBACK_GEO.get(place.strip().lower())
        if fb:
            return json.dumps({**fb, "source": "fallback-cache"})
        return json.dumps({"error": f"Could not geocode '{place}'.", "source": "none"})


@tool
def climate_summary(latitude: float, longitude: float) -> str:
    """Get a historical climate summary (avg temperature, total precipitation).

    Args:
        latitude: Latitude in decimal degrees.
        longitude: Longitude in decimal degrees.
    """
    key = f"clim:{round(latitude, 4)}:{round(longitude, 4)}"
    if key in _CACHE:
        return _CACHE[key]
    try:
        url = "https://archive-api.open-meteo.com/v1/archive?" + urllib.parse.urlencode(
            {
                "latitude": latitude,
                "longitude": longitude,
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
                "daily": "temperature_2m_mean,precipitation_sum",
                "timezone": "UTC",
            }
        )
        daily = _get_json(url)["daily"]
        temps = [t for t in daily.get("temperature_2m_mean", []) if t is not None]
        precip = [p for p in daily.get("precipitation_sum", []) if p is not None]
        avg_temp = round(sum(temps) / len(temps), 1) if temps else None
        total_precip = round(sum(precip), 1) if precip else None
        out = json.dumps(
            {
                "avg_temp_c": avg_temp,
                "total_precip_mm": total_precip,
                "source": "open-meteo-archive",
            }
        )
        _CACHE[key] = out
        return out
    except (urllib.error.URLError, KeyError, ValueError, TimeoutError, ZeroDivisionError):
        fb = _FALLBACK_CLIMATE.get((round(latitude, 4), round(longitude, 4)))
        if fb:
            return json.dumps({**fb, "source": "fallback-cache"})
        return json.dumps({"error": "Climate API unavailable.", "source": "none"})


@tool
def wikipedia_summary(topic: str) -> str:
    """Get a short encyclopedia overview of a place or topic.

    Args:
        topic: A place or topic, e.g. "Kyoto".
    """
    key = f"wiki:{topic.strip().lower()}"
    if key in _CACHE:
        return _CACHE[key]
    try:
        encoded = urllib.parse.quote(topic.strip().replace(" ", "_"))
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
        data = _get_json(url)
        extract = (data.get("extract") or "").strip()
        if not extract:
            raise ValueError("no extract")
        out = json.dumps(
            {"title": data.get("title", topic), "summary": extract[:600], "source": "wikipedia"}
        )
        _CACHE[key] = out
        return out
    except (urllib.error.URLError, ValueError, KeyError, TimeoutError):
        return json.dumps(
            {"title": topic, "summary": f"(Overview for {topic} is unavailable right now.)",
             "source": "none"}
        )
