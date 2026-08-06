"""Shared input guardrails for the public demo booth.

These demos run on a public kiosk, so before a prompt ever reaches the model we
apply lightweight, deterministic checks (no extra model call, no cost) for the
things a booth visitor might try that have nothing to do with the demo:

- off-topic / "write me code", essays, homework, translation, "act as X"
- system-prompt extraction ("repeat your instructions", "what are your rules")
- jailbreak / instruction-override ("ignore your instructions", "you are DAN")
- abuse control: an input length cap and a per-session request rate limit

This is intentionally a keyword/regex layer, NOT a content moderator. Hard
content safety (violence, hate, sexual, self-harm) is left to the model
provider's native content filter. The goal here is to keep casual off-topic and
prompt-attack traffic from wandering off the demo's rails, with a low false
positive rate — anything not clearly matched is allowed through.

Attack demos (memory-poisoning, hooks-guardian) intentionally accept adversarial
prompts, so their Policy disables the scope / jailbreak / extraction rules and
keeps only the abuse limits. See ``Policy`` and the per-demo presets below.

Same patterns are general agent-safety concepts and carry over to other agent
frameworks; this implementation is framework-agnostic Python.
"""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field

import demo_events as ev

# --- abuse limits ------------------------------------------------------------
# NOTE: state is per-process (per runtime instance), so the rate limit is
# per-instance, not global across a multi-instance runtime. It is a booth abuse
# brake, not a distributed quota.
MAX_PROMPT_CHARS = 2000
MAX_REQUESTS_PER_WINDOW = 20
RATE_WINDOW_SECONDS = 60

# --- refusal message (trilingual; the payload carries no UI language) --------
_REFUSAL = {
    "offtopic": (
        "This demo can only answer questions about {topic}. / "
        "Este demo solo responde preguntas sobre {topic}. / "
        "Esta demonstração só responde perguntas sobre {topic}."
    ),
    "extraction": (
        "I can't share my internal instructions — but ask me about {topic}! / "
        "No puedo compartir mis instrucciones internas, pero pregúntame sobre {topic}. / "
        "Não posso compartilhar minhas instruções internas, mas pergunte sobre {topic}."
    ),
    "jailbreak": (
        "I'll stay in my demo role. Ask me about {topic}! / "
        "Me quedo en mi rol de demo. Pregúntame sobre {topic}. / "
        "Vou ficar no meu papel de demonstração. Pergunte sobre {topic}."
    ),
    "too_long": (
        "That message is too long for this demo. Please keep it short. / "
        "Ese mensaje es demasiado largo para este demo. Por favor, sé breve. / "
        "Essa mensagem é muito longa para esta demonstração. Seja breve."
    ),
    "rate_limited": (
        "You're sending messages very quickly — please wait a moment. / "
        "Estás enviando mensajes muy rápido, espera un momento. / "
        "Você está enviando mensagens muito rápido — aguarde um momento."
    ),
}

# --- deterministic patterns --------------------------------------------------
# Case-insensitive. Kept deliberately explicit to minimize false positives:
# these match overt phrasing, not every possible rewording.

# \w+\s+ up to a few times allows adjectives/articles between the verb and the
# noun ("write me a python script", "genera un pequeño código").
_CODE_REQUEST = re.compile(
    r"("
    r"(write|generate|create|build)\b(\s+\w+){0,3}\s+(code|program|script|function|class)\b|"
    r"(escribe|escr[ií]beme|genera|dame|crea)\b(\s+\w+){0,3}\s+(c[oó]digo|programa|script|funci[oó]n)\b|"
    r"(escreva|gere|crie|me d[eê])\b(\s+\w+){0,3}\s+(c[oó]digo|programa|script|fun[cç][aã]o)\b|"
    r"code (this|that|it)\b|implement (a|the|this)\b|debug (this|my)\b|"
    r"regex for\b|sql query\b|(write|code)\b(\s+\w+){0,4}\s+in (python|javascript|java|c\+\+|go|rust|typescript)\b"
    r")",
    re.IGNORECASE,
)

_OFFTOPIC_TASK = re.compile(
    r"\b("
    r"write (me )?(a |an |the )?(essay|poem|story|song|email|letter|blog|article|tweet|resume|cover letter)|"
    r"(escribe|escríbeme|redacta) (un |una )?(ensayo|poema|historia|canci[oó]n|correo|carta|art[ií]culo)|"
    r"(escreva|redija) (um |uma )?(reda[cç][aã]o|poema|hist[oó]ria|m[uú]sica|email|carta|artigo)|"
    r"do my homework|solve my|translate (this|the following)|traduce|traduza|"
    r"recipe for|tell me a joke|write a haiku"
    r")\b",
    re.IGNORECASE,
)

_EXTRACTION = re.compile(
    r"("
    r"(repeat|print|show|reveal|tell me|what (is|are)|give me)\b(\s+\w+){0,4}\s+"
    r"(system )?(prompt|instructions?|rules?|guidelines?|configuration)\b|"
    r"(repite|imprime|mu[eé]strame|dime|cu[aá]les son)\b(\s+\w+){0,4}\s+"
    r"(instrucciones|reglas|prompt|directrices)\b|"
    r"(repita|mostre|diga|quais s[aã]o)\b(\s+\w+){0,4}\s+(instru[cç][oõ]es|regras|prompt)\b|"
    r"ignore (the )?(above|previous) and (repeat|print|show)\b|"
    r"what were you told\b|initial prompt\b|verbatim(\s+\w+){0,4}\s+(prompt|instructions)\b"
    r")",
    re.IGNORECASE,
)

_JAILBREAK = re.compile(
    r"("
    r"ignore (all |any |your )?(previous |above |prior )?(instructions?|rules?|prompt)|"
    r"disregard (your |the |all )?(instructions?|rules?|guidelines?)|"
    r"(olvida|ignora) (tus |las )?(instrucciones|reglas)|"
    r"(ignore|esque[cç]a) (as |suas )?(instru[cç][oõ]es|regras)|"
    r"you are (now )?(dan|a|an)\b.*\b(no (rules|restrictions|limits)|unrestricted|jailbroken)|"
    r"developer mode|do anything now|pretend (you are|to be)|act as (if )?(a|an|you)|"
    r"act[uú]a como|finge (que|ser)|no tienes (reglas|restricciones)|"
    r"bypass (your )?(restrictions?|filters?|safety)"
    r")",
    re.IGNORECASE,
)


@dataclass
class Policy:
    """Which guardrails apply for a given demo, plus the demo's topic string."""

    topic: str
    block_offtopic: bool = True
    block_extraction: bool = True
    block_jailbreak: bool = True
    limit_length: bool = True
    rate_limit: bool = True


@dataclass
class Verdict:
    blocked: bool
    kind: str = ""
    message: str = ""
    reason: str = ""


# --- per-session rate limiter (per process) ----------------------------------
_lock = threading.Lock()
_hits: dict[str, list[float]] = {}


def _rate_limited(session_id: str, now: float) -> bool:
    with _lock:
        window = [t for t in _hits.get(session_id, []) if now - t < RATE_WINDOW_SECONDS]
        window.append(now)
        _hits[session_id] = window
        return len(window) > MAX_REQUESTS_PER_WINDOW


def check(prompt: str, policy: Policy, session_id: str = "local", now: float | None = None) -> Verdict:
    """Evaluate a prompt against a policy. Returns a Verdict; never raises."""
    text = prompt.strip()

    if policy.limit_length and len(prompt) > MAX_PROMPT_CHARS:
        return _block("too_long", policy, "prompt exceeds length cap")

    if policy.rate_limit:
        stamp = time.time() if now is None else now
        if _rate_limited(session_id, stamp):
            return _block("rate_limited", policy, "per-session rate limit exceeded")

    if policy.block_jailbreak and _JAILBREAK.search(text):
        return _block("jailbreak", policy, "instruction-override attempt")

    if policy.block_extraction and _EXTRACTION.search(text):
        return _block("extraction", policy, "system-prompt extraction attempt")

    if policy.block_offtopic and (_CODE_REQUEST.search(text) or _OFFTOPIC_TASK.search(text)):
        return _block("offtopic", policy, "off-topic / out-of-scope request")

    return Verdict(blocked=False)


def _block(kind: str, policy: Policy, reason: str) -> Verdict:
    message = _REFUSAL[kind].format(topic=policy.topic)
    return Verdict(blocked=True, kind=kind, message=message, reason=reason)


def blocked_events(verdict: Verdict):
    """Yield the demo-protocol events for a blocked prompt: a chat refusal, an
    Insights card, and the terminal done. The caller returns after yielding."""
    yield ev.token(verdict.message)
    yield ev.guardrail_blocked(verdict.kind, verdict.reason)
    yield ev.done()
