import pytest

from src.guards import (
    SAFE_SENTENCE,
    citation_ids,
    extract_facts,
    forbidden_promises,
    remove_promises,
    strip_citations,
    strip_unknown_citations,
    ungrounded_facts,
    unknown_citations,
)


@pytest.mark.parametrize(
    "text",
    [
        "We will refund your stay in full.",
        "Your refund has been processed.",
        "You will receive a full refund.",
        "I have upgraded you to a suite.",
        "Enjoy a complimentary upgrade!",
        "We can waive the pet fee.",
        "We'll cancel your reservation at no charge.",
        "We’ve waived the fee.",
        "I've moved your booking to 4 December.",
        "We will match the lower rate.",
        "The fee is waived for this stay.",
        "Le reembolsaremos el importe.",
        "Breakfast is on us tomorrow.",
        "We comped your breakfast.",
        "I can confirm that we will refund the full amount.",
        "Enjoy a complimentary upgrade to our Suite!",
    ],
)
def test_promises_are_caught(text):
    assert forbidden_promises(text) == [text]


@pytest.mark.parametrize(
    "text",
    [
        "I've passed your cancellation request to our manager for approval.",
        "Free cancellation is available up to 48 hours before arrival [P1].",
        "Platinum members get a guaranteed one-category upgrade [P2].",
        "We have noted your request for an upgrade and a manager will review it.",
        "Cribs are free.",
        "I will ask our manager to review a refund.",
        "We have arranged an extra crib.",
        "We'll be happy to help.",
        "Non-refundable bookings can't be refunded unless the General Manager approves [P3].",
        # False positives found in the dev eval runs (docs/DECISIONS.md, "What the eval taught me"):
        "We have Suites available for those nights, but I'm not able to offer a free upgrade myself.",
        "We have received your request for a complimentary upgrade from your Standard Queen to a Suite.",
        "I have passed your request for a complimentary upgrade to a manager for review.",
        "I wasn't able to confirm whether we match outside rates, so please don't assume a match.",
        "Please send the link so we can compare like for like.",
        "I could not find a price-match policy in our documents, so I can't confirm that we can match the other "
        "website's price.",
        "We cannot guarantee that we can extend your stay until a manager reviews it.",
    ],
)
def test_describing_policy_or_passing_on_a_request_is_fine(text):
    assert forbidden_promises(text) == []


def test_remove_promises_replaces_once_and_keeps_layout():
    text = "Dear Ana,\n\nThe fee is $75 [P1]. We will refund the fee. We'll also upgrade you.\n\nGuest Services"
    cleaned, removed = remove_promises(text)
    assert len(removed) == 2 and cleaned.count(SAFE_SENTENCE) == 1
    assert cleaned.startswith("Dear Ana,\n\nThe fee is $75 [P1].") and cleaned.endswith("\n\nGuest Services")
    assert remove_promises("All good.") == ("All good.", [])


def test_extract_facts_normalizes_many_spellings():
    facts = extract_facts(
        "Check-out 11:00 AM; late until 2 PM on Fri 6 Nov 2026 (2026-11-06). $75 per stay, $1,047.00 total, "
        "40 lbs, Room 304, noon, 10% off, 3 nights, 6 de noviembre, a las 14:00, Cabin C2, two dogs, 24-hour notice"
    )
    for f in [
        "time 11:00",
        "time 14:00",
        "date 11-06",
        "$75",
        "$1047",
        "40 lb",
        "room 304",
        "time 12:00",
        "10%",
        "3 night",
        "room C2",
        "24 h",
    ]:
        assert f in facts, f
    assert extract_facts("Call 555-0100 or see 11/6") == set()  # phone-like and ambiguous dates aren't facts
    # A numbered list after a date is not a second date (found in the first app run).
    assert extract_facts("Confirm for Monday 9 Nov.\n\n3. MIA pickup") == {"date 11-09"}


def test_made_up_facts_fail_grounding():
    sources = ['{"text": "Pet fee is $75 per stay. Late check-out until 2:00 PM.", "check_in": "Fri 6 Nov 2026"}']
    assert ungrounded_facts("The fee is $75 and you can stay until 2 PM on 6 November.", sources) == []
    assert ungrounded_facts("The fee is $50 and you can stay until 4 PM.", sources) == ["$50", "time 16:00"]
    assert ungrounded_facts("Your room is 312.", sources) == []  # bare number: not a room fact
    assert ungrounded_facts("You're in Room 312.", sources) == ["room 312"]


def test_a_number_from_the_guest_email_may_be_repeated():
    sources = ['{"text": "Pet fee is $75 per stay."}']
    draft = "The pet fee isn't $40: it's $75 per stay."
    assert ungrounded_facts(draft, sources) == ["$40"]
    assert ungrounded_facts(draft, sources, email_text="Is the pet fee $40?") == []


def test_citations():
    text = "Fee $75 [P1][P2]. Pool 7 AM [P9]. Again [P1]."
    assert citation_ids(text) == ["P1", "P2", "P9"]
    assert unknown_citations(text, {"P1", "P2"}) == ["P9"]
    assert strip_unknown_citations(text, {"P1", "P2"}) == "Fee $75 [P1][P2]. Pool 7 AM . Again [P1]."
    assert strip_citations(text) == "Fee $75. Pool 7 AM. Again."
