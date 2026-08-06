"""Demo 05 tools: travel booking with a verifiable ground-truth ledger."""
import random

from strands import tool

_rng = random.Random()

# In-memory ledger: the "ground truth" the UI can compare against what the
# agent claims (pattern from observability-for-agents-sample-for-aws).
_BOOKINGS: list = []
_OFFERS: dict = {}


@tool
def search_flights(origin: str, destination: str, date: str) -> str:
    """Search for available flights (simulated).

    Args:
        origin: Departure city.
        destination: Arrival city.
        date: Travel date, e.g. 2026-09-01.
    """
    lines = []
    for i in range(3):
        offer_id = f"offer-{_rng.randint(1000, 9999)}"
        price = round(_rng.uniform(45, 320), 2)
        _OFFERS[offer_id] = price
        lines.append(f"{offer_id}: {origin}->{destination} {date} dep 0{6 + i * 4}:15, ${price}")
    return "\n".join(lines)


@tool
def get_weather(city: str) -> str:
    """Get the weather forecast for a city (simulated).

    Args:
        city: City name.
    """
    temp = _rng.randint(8, 34)
    sky = _rng.choice(["sunny", "partly cloudy", "rainy", "windy"])
    return f"{city}: {sky}, {temp}°C."


@tool
def book_flight(offer_id: str) -> str:
    """Book a flight offer found in a previous search.

    Args:
        offer_id: The offer id returned by search_flights.
    """
    # Anti-hallucination guard: only offers that actually exist can be booked.
    if offer_id not in _OFFERS:
        return f"error: unknown_offer '{offer_id}' — it was never returned by a search."
    price = _OFFERS[offer_id]
    booking = {"offer_id": offer_id, "price_usd": price, "id": f"BK-{_rng.randint(10000, 99999)}"}
    _BOOKINGS.append(booking)
    return f"Booked {offer_id} for ${price}. Confirmation: {booking['id']}."


def query_bookings() -> list:
    """Ground truth: what was ACTUALLY booked (read by the entrypoint)."""
    return list(_BOOKINGS)
