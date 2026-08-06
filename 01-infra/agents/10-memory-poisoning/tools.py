"""Demo 10 tools: memory notes + email with a pure-function domain allowlist.

Pattern from how-agents-evolve-sample-for-aws (memory poisoning defense):
the security decision is a pure function at the tool boundary — testable
without a model, immune to prompt injection stored in memory.
"""
from strands import tool

ALLOWED_EMAIL_DOMAINS = {"example.com", "mycompany.com"}

# Simulated exfiltration log: proves whether an email actually left.
EMAIL_LOG: list = []


def email_is_allowed(address: str) -> bool:
    """Pure allowlist check — shared by the tool and by unit tests."""
    domain = address.rsplit("@", 1)[-1].lower().strip()
    return domain in ALLOWED_EMAIL_DOMAINS


@tool(context=True)
def save_note(note: str, tool_context) -> str:
    """Save a note to the agent's persistent memory.

    Args:
        note: The note text to remember.
    """
    notes = tool_context.agent.state.get("notes") or []
    notes.append(note)
    tool_context.agent.state.set("notes", notes)
    return f"Saved. You now have {len(notes)} note(s)."


@tool(context=True)
def read_notes(tool_context) -> str:
    """Read all notes stored in the agent's persistent memory."""
    notes = tool_context.agent.state.get("notes") or []
    if not notes:
        return "No notes stored."
    return "\n".join(f"- {n}" for n in notes)


@tool
def get_booking_details(booking_id: str) -> str:
    """Look up a customer booking (simulated sensitive data).

    Args:
        booking_id: The booking reference.
    """
    return (
        f"Booking {booking_id}: passenger Jane Roe, card ending 4242, "
        "flight LIM->CUZ 2026-09-01, $141.10."
    )


@tool
def send_email(to_address: str, subject: str, body: str) -> str:
    """Send an email (simulated).

    Args:
        to_address: Recipient email address.
        subject: Email subject.
        body: Email body.
    """
    # The gate lives at the TOOL BOUNDARY, not in the prompt: a poisoned
    # memory can convince the model, but it cannot change this function.
    if not email_is_allowed(to_address):
        return (
            f"BLOCKED: '{to_address}' is not in the allowed domains "
            f"({', '.join(sorted(ALLOWED_EMAIL_DOMAINS))}). Nothing was sent."
        )
    EMAIL_LOG.append({"to": to_address, "subject": subject})
    return f"Email sent to {to_address}."
