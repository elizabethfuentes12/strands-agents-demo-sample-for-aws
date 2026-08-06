"""Demo 04 tools: travel booking with human approval on book_flight."""
import random

from strands import tool

_rng = random.Random()


@tool
def search_flights(origin: str, destination: str, date: str) -> str:
    """Search for available flights (simulated).

    Args:
        origin: Departure city.
        destination: Arrival city.
        date: Travel date, e.g. 2026-09-01.
    """
    flights = []
    for i in range(3):
        price = _rng.randint(80, 450)
        flights.append(
            f"offer-{_rng.randint(1000, 9999)}: {origin}->{destination} {date} "
            f"dep 0{6 + i * 4}:30, ${price}"
        )
    return "\n".join(flights)


@tool(context=True)
def book_flight(offer_id: str, price_usd: float, tool_context) -> str:
    """Book a flight. REQUIRES human approval before executing.

    Args:
        offer_id: The flight offer to book.
        price_usd: Price of the offer in US dollars.
    """
    # Pause the whole agent loop and wait for a human decision. The response
    # arrives on a later invocation of the same session.
    approval = tool_context.interrupt(
        "booking-approval", reason={"offer_id": offer_id, "price_usd": price_usd}
    )
    if str(approval).lower() not in ("y", "yes", "approve", "approved"):
        return f"Booking of {offer_id} was REJECTED by the human reviewer."
    confirmation = f"BK-{_rng.randint(10000, 99999)}"
    return f"Booked {offer_id} for ${price_usd:.2f}. Confirmation: {confirmation}."
