"""Unit test for the memory-poisoning defense.

The whole point of this demo: the security decision is a PURE FUNCTION at the
tool boundary, so it is testable without a model and immune to any instruction
a poisoned memory might contain. Run it with:

    python -m pytest test_gate.py      # or: python test_gate.py
"""
from tools import ALLOWED_EMAIL_DOMAINS, email_is_allowed


def test_allowed_domains_pass():
    assert email_is_allowed("ops@example.com")
    assert email_is_allowed("Team@MyCompany.com")  # case-insensitive


def test_exfiltration_domain_blocked():
    assert not email_is_allowed("attacker@evil.com")
    assert not email_is_allowed("data@evil.com ")  # trailing space stripped


def test_lookalike_domains_blocked():
    # A poisoned note cannot smuggle data via a look-alike domain.
    assert not email_is_allowed("x@example.com.evil.com")
    assert not email_is_allowed("x@notexample.com")


def test_allowlist_is_the_only_source_of_truth():
    for addr in ("a@example.com", "b@mycompany.com"):
        domain = addr.rsplit("@", 1)[-1].lower()
        assert domain in ALLOWED_EMAIL_DOMAINS


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  PASS {name}")
    print("All gate tests passed.")
