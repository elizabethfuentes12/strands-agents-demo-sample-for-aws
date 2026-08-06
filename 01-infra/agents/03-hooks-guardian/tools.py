"""Demo 03 tools: simulated dangerous operations (nothing real happens)."""
from strands import tool


@tool
def delete_database(database_name: str) -> str:
    """Permanently delete a production database.

    Args:
        database_name: Name of the database to delete.
    """
    return f"SIMULATION: database '{database_name}' deleted."


@tool
def send_email_blast(subject: str, audience: str) -> str:
    """Send a marketing email to every customer.

    Args:
        subject: Email subject line.
        audience: Target audience segment.
    """
    return f"SIMULATION: email '{subject}' sent to {audience}."


@tool
def refund_payment(order_id: str, amount_usd: float) -> str:
    """Refund a customer payment.

    Args:
        order_id: The order to refund.
        amount_usd: Refund amount in US dollars.
    """
    return f"SIMULATION: refunded ${amount_usd:.2f} for order {order_id}."


@tool
def check_order_status(order_id: str) -> str:
    """Check the status of a customer order (safe, always allowed).

    Args:
        order_id: The order to check.
    """
    return f"Order {order_id}: shipped, arriving in 2 days. Total: $87.50."
