"""Project 4 fixes, with a scripted fake model (no API):
- E12: the sender's booking is looked up before the model runs and pins the hotel when the guest wrote to the other
  property's inbox; search_policy then defaults to the booking's property.
- X05: a Spanish email gets a Spanish reply. A reply in the wrong language is sent back once for a rewrite, and a
  Spanish email never gets an English holding reply.
Both failed before the change (eval-harness reports/p2-harness-2026-10-14.md, runs/p2-p4before-2026-10-15)."""

import json

from fakes import FakeClient, api_error, draft, tool

from src.agent import (
    ESCALATION_HOLDING_REPLY_ES,
    HOLDING_REPLY,
    HOLDING_REPLY_ES,
    Email,
    build_system,
    holding_template,
    run_agent,
)

OLIVIA = Email(  # E12: Mountain Lodge booking, email sent to the Beach Resort inbox
    "olivia.grant@example.com",
    "Pool hours for the kids",
    "Hi! We're arriving this Friday with our two kids. What time does the pool open?",
    "Olivia Grant",
)
ISABEL = Email(  # b08: Spanish email, Beach Resort booking
    "isabel.ortiz@example.com",
    "Salida tarde",
    "Hola,\n\nTenemos una reserva del 20 al 23 de noviembre. ¿A qué hora es la salida y podemos quedarnos un poco "
    "más tarde el último día?\n\nGracias,\nIsabel",
    "Isabel Ortiz",
)
SPANISH_REPLY = (
    "Hola Isabel,\n\nGracias por escribirnos. La hora de salida es a las 11:00 y el equipo le confirmará si puede "
    "quedarse más tarde.\n\nGuest Services, Beach Resort"
)
ENGLISH_REPLY = "Hi Isabel,\n\nThanks for writing. The team will confirm your check-out time.\n\nGuest Services"


def run(turns, email, prop, store):
    client = FakeClient(turns)
    return run_agent(email, prop, client=client, store=store), client


def test_wrong_inbox_booking_pins_the_property_before_the_model(store):
    result, client = run(
        [[tool("search_policy", {"question": "pool hours"})], [draft("Dear Olivia,\n\nThe team will confirm.")]],
        OLIVIA,
        "beach-resort",
        store,
    )
    first = client.requests[0]
    assert "Mountain Lodge, not Beach Resort" in first["system"]
    assert "<booking_lookup>" in first["messages"][0]["content"] and "ML-2040" in first["messages"][0]["content"]
    pin = [s for s in result.steps if s.name == "property_pin"]
    assert pin and pin[0].result == "mountain-lodge" and result.flags["pinned_property"] == "mountain-lodge"
    # The model searched without naming a property: the search used Mountain Lodge's documents, not the inbox's.
    search = next(s for s in result.steps if s.name == "search_policy")
    assert search.ok
    sources = json.dumps(result.sources)
    assert "does not have an on-site pool" in sources and "rooftop pool is open" not in sources


def test_same_property_or_no_booking_pins_nothing(store):
    nobody = Email("nobody@example.com", "Hi", "Is there parking?", "")
    for email, reply in [(ISABEL, SPANISH_REPLY), (nobody, "Dear Guest,\n\nThe team will confirm.")]:
        result, client = run([[draft(reply)]], email, "beach-resort", store)
        assert result.flags["pinned_property"] is None
        assert "not Beach Resort" not in client.requests[0]["system"]


def test_spanish_email_asks_for_a_spanish_reply(store):
    result, client = run([[draft(SPANISH_REPLY)]], ISABEL, "beach-resort", store)
    assert "The guest wrote in Spanish" in client.requests[0]["system"]
    assert result.language == "es" and result.flags["language_mismatch"] is False
    assert not any(s.name == "language" for s in result.steps)


def test_english_reply_to_a_spanish_email_is_sent_back_once_for_a_rewrite(store):
    result, client = run([[draft(ENGLISH_REPLY)], [draft(SPANISH_REPLY)]], ISABEL, "beach-resort", store)
    assert len(client.requests) == 2
    retry = client.requests[1]["messages"][2]["content"][0]
    assert retry["is_error"] is True and "Spanish" in retry["content"]
    assert [s.name for s in result.steps if s.kind == "guard"][0] == "language"
    assert result.reply.startswith("Hola Isabel") and result.flags["language_mismatch"] is False


def test_only_one_rewrite_then_the_mismatch_is_flagged_for_staff(store):
    result, client = run([[draft(ENGLISH_REPLY)], [draft(ENGLISH_REPLY)]], ISABEL, "beach-resort", store)
    assert len(client.requests) == 2 and result.outcome == "drafted"
    assert result.flags["language_mismatch"] is True  # the check can fail: staff see it


def test_english_email_is_never_sent_back_for_language(store):
    email = Email("elena.marsh@example.com", "Dog", "Can we bring our dog? What is the pet fee?", "Elena Marsh")
    result, client = run([[draft("Dear Elena,\n\nThe team will confirm the pet fee.")]], email, "beach-resort", store)
    assert len(client.requests) == 1 and "The guest wrote in" not in client.requests[0]["system"]


def test_spanish_email_falls_back_to_a_spanish_holding_reply(store):
    result, _ = run([api_error(500)], ISABEL, "beach-resort", store)
    assert result.outcome == "fallback" and result.reply.startswith("Estimado/a Isabel")


def test_holding_templates_by_language():
    assert holding_template("es", False) is HOLDING_REPLY_ES
    assert holding_template("es", True) is ESCALATION_HOLDING_REPLY_ES
    assert holding_template("en", False) is HOLDING_REPLY
    assert "{name}" in HOLDING_REPLY_ES and "{property_name}" in ESCALATION_HOLDING_REPLY_ES


def test_build_system_notes_are_optional():
    plain = build_system("beach-resort", [], [])
    assert "booking was looked up" not in plain and "The guest wrote in" not in plain
    both = build_system("beach-resort", [], [], pinned="mountain-lodge", language="es")
    assert "Mountain Lodge, not Beach Resort" in both and "The guest wrote in Spanish" in both
    assert "booking was looked up" not in build_system("beach-resort", [], [], pinned="beach-resort")
