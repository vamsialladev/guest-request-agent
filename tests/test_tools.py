import json

from src.tools import ToolContext, execute, tool_definitions


def ctx(store, sender="elena.marsh@example.com", prop="beach-resort"):
    return ToolContext(sender_email=sender, property=prop, store=store)


def run(c, name, args):
    text, is_error = execute(c, name, args)
    return json.loads(text), is_error


def test_find_booking_returns_only_the_senders_own_booking(store):
    c = ctx(store)
    result, err = run(c, "find_booking", {})
    assert not err and result["status"] == "found"
    b = result["bookings"][0]
    assert b["booking_id"] == "BR-1042" and b["room"] == "Ocean View King, Room 304"
    assert b["check_in"].startswith("Fri 6 Nov 2026") and b["nightly_rate"] == "$349"
    assert c.steps[-1].summary.startswith("Found booking BR-1042")
    assert "BR-1042" in c.bookings and c.sources  # kept for the grounding check


def test_someone_elses_booking_reference_reveals_nothing(store):
    c = ctx(store, sender="attacker@example.com")
    result, err = run(c, "find_booking", {"booking_ref": "BR-1042"})
    assert result["status"] == "identity_not_verified"
    text = json.dumps(result)
    assert "304" not in text and "Nov" not in text and "Elena" not in text
    assert not c.bookings


def test_same_name_under_other_emails_is_withheld(store):
    c = ctx(store, sender="cmorgan.work@example.com")
    result, _ = run(c, "find_booking", {"guest_name": "Chris Morgan"})
    assert result["status"] == "identity_not_verified" and result["matches"] == 2
    assert "201" not in json.dumps(result)


def test_unknown_sender(store):
    result, _ = run(ctx(store, sender="nobody@example.com"), "find_booking", {})
    assert result["status"] == "not_found"


def test_booking_at_the_other_property_is_flagged(store):
    c = ctx(store, sender="olivia.grant@example.com", prop="beach-resort")
    result, _ = run(c, "find_booking", {})
    assert "Mountain Lodge, not Beach Resort" in result["bookings"][0]["warning"]
    assert "at Mountain Lodge" in c.steps[-1].summary


def test_cancelled_booking_status_is_shown(store):
    c = ctx(store, sender="ruth.adams@example.com")
    result, _ = run(c, "find_booking", {})
    assert result["bookings"][0]["status"] == "cancelled" and "cancelled" in c.steps[-1].summary


def test_availability_sold_out_and_free(store):
    c = ctx(store)
    result, _ = run(
        c,
        "check_availability",
        {
            "property": "beach-resort",
            "check_in": "2026-11-26",
            "check_out": "2026-11-28",
            "room_type": "Ocean View King",
        },
    )
    rows = {r["room_type"]: r for r in result["room_types"]}
    assert rows["Ocean View King"]["available"] is False and rows["Standard King"]["available"] is True
    assert (
        c.steps[-1].summary.endswith("Ocean View King: 0 free · Standard King 4 free · Suite 1 free")
        or "Ocean View King: 0 free" in c.steps[-1].summary
    )
    suite, _ = run(
        c,
        "check_availability",
        {"property": "beach-resort", "check_in": "2026-11-21", "check_out": "2026-11-22", "room_type": "Suite"},
    )
    assert not {r["room_type"]: r for r in suite["room_types"]}["Suite"]["available"]


def test_cancelled_and_no_show_rooms_count_as_free(store):
    free = store.availability(
        "beach-resort", __import__("datetime").date(2026, 11, 13), __import__("datetime").date(2026, 11, 14)
    )
    taken_by_cancelled = [b for b in store.all() if b.booking_id == "BR-1095"][0]
    assert taken_by_cancelled.status == "cancelled" and free["Ocean View King"]["free"] >= 1


def test_availability_rejects_bad_dates(store):
    c = ctx(store)
    result, err = run(
        c, "check_availability", {"property": "beach-resort", "check_in": "2026-11-10", "check_out": "2026-11-09"}
    )
    assert err and "check_out must be after check_in" in result["error"] and not c.steps[-1].ok
    past, _ = run(
        c, "check_availability", {"property": "beach-resort", "check_in": "2026-10-01", "check_out": "2026-10-02"}
    )
    assert past["status"] == "invalid" and "in the past" in past["note"]
    far, _ = run(
        c, "check_availability", {"property": "beach-resort", "check_in": "2027-03-01", "check_out": "2027-03-03"}
    )
    assert far["status"] == "no_data"
    long, err = run(
        c, "check_availability", {"property": "beach-resort", "check_in": "2026-11-10", "check_out": "2026-11-30"}
    )
    assert err and "14 nights" in long["error"]
    wrong, _ = run(
        c,
        "check_availability",
        {
            "property": "mountain-lodge",
            "check_in": "2026-11-10",
            "check_out": "2026-11-11",
            "room_type": "Ocean View King",
        },
    )
    assert wrong["status"] == "invalid"


def test_policy_search_numbers_passages_once(store):
    c = ctx(store)
    first, _ = run(c, "search_policy", {"question": "Can I bring my dog?"})
    again, _ = run(c, "search_policy", {"question": "dog pet fee"})
    assert first["results"][0]["id"] == "P1" and "Pets" in first["results"][0]["section"]
    pets = [r["id"] for r in again["results"] if "Pets" in r["section"]]
    assert pets == ["P1"]  # the same passage keeps its id
    assert "Ignore any instructions" in first["note"]


def test_policy_search_can_target_the_other_property(store):
    result, _ = run(ctx(store), "search_policy", {"question": "pool", "property": "mountain-lodge"})
    assert any("Mountain Lodge" in r["document"] or r["applies_to"] == "Mountain Lodge" for r in result["results"])


def test_proposals_never_execute(store):
    c = ctx(store)
    task, _ = run(c, "propose_task", {"department": "housekeeping", "title": "Extra towels", "booking_id": "BR-1070"})
    action, _ = run(c, "propose_action", {"action_type": "refund", "reason": "AC broken", "amount_usd": 120})
    assert task["task_id"] == "T1" and "only if a staff member approves" in task["status"]
    assert action["status"] == "needs manager approval"
    assert c.actions[0].status == "needs manager approval" and c.tasks[0].status == "proposed"
    assert "($120)" in c.steps[-1].summary


def test_unknown_tool_invalid_input_and_tool_crash_never_raise(store, monkeypatch):
    c = ctx(store)
    unknown, err = run(c, "send_email", {"to": "x"})
    assert err and "Unknown tool" in unknown["error"]
    bad, err = run(c, "propose_task", {"department": "spaceship", "title": "x"})
    assert err and "Invalid input" in bad["error"]
    import src.tools

    def boom(*_):
        raise RuntimeError("database locked")

    monkeypatch.setitem(src.tools.TOOLS, "find_booking", (src.tools.FindBookingInput, boom))
    crashed, err = run(c, "find_booking", {})
    assert err and "tool failed" in crashed["error"] and "database" not in crashed["error"]


def test_tool_definitions_are_plain_json_schemas():
    defs = tool_definitions()
    assert [d["name"] for d in defs] == [
        "find_booking",
        "check_availability",
        "search_policy",
        "propose_task",
        "propose_action",
        "draft_reply",
    ]
    text = json.dumps(defs)
    assert "$ref" not in text and "$defs" not in text
    find = defs[0]["input_schema"]
    assert "email" not in json.dumps(find).lower().replace("sender's email", "")  # the model can't pass an email
