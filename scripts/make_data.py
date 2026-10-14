"""Build the synthetic bookings database: data/bookings.sqlite (SYNTHETIC DATA, fictional guests).

    python scripts/make_data.py

Seeded and reproducible: the same seed always gives the same rows (tests check this). Two parts:
1. Story bookings: hand-written guests that the sample emails and eval cases refer to, including edge cases
   (cancelled, no-show, two guests with the same name, a guest writing to the wrong property, sold-out nights).
2. Seeded random fill up to about 80 reservations over 45 days, which never overbooks a room and never fills the
   nights the sample emails need to find free.

Names are invented; every email address is @example.com (reserved for documentation, never delivered).
The app builds this file on first start when it is missing (src/bookings.py).
"""

import random
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SEED = 42
WINDOW_START = date(2026, 10, 26)
WINDOW_DAYS = 45  # 26 Oct - 9 Dec 2026; the simulated "today" is Mon 2 Nov 2026 (src/config.py SIM_TODAY)
TODAY = date(2026, 11, 2)

# property -> room type -> (room numbers, flexible nightly rate in USD)
ROOMS = {
    "beach-resort": {
        "Standard King": ([f"{n}" for n in range(201, 211)], 289),
        "Ocean View King": ([f"{n}" for n in range(301, 307)], 349),
        "Suite": (["401", "402", "403"], 529),
    },
    "mountain-lodge": {
        "Standard Queen": ([f"{n}" for n in range(101, 109)], 189),
        "Cabin": (["C1", "C2", "C3", "C4", "C5"], 249),
        "Suite": (["201", "202"], 369),
    },
}
NON_REFUNDABLE_DISCOUNT = 0.10

# (booking_id, property, name, email, tier, member_number, room_type, room, check_in, check_out, adults, children,
#  rate_plan, status, notes)
STORY = [
    (
        "BR-1042",
        "beach-resort",
        "Elena Marsh",
        "elena.marsh@example.com",
        "Gold",
        "GR-55120",
        "Ocean View King",
        "304",
        "2026-11-06",
        "2026-11-09",
        2,
        0,
        "Flexible",
        "confirmed",
        "",
    ),
    (
        "BR-1043",
        "beach-resort",
        "James Okafor",
        "james.okafor@example.com",
        "Silver",
        "GR-31877",
        "Standard King",
        "205",
        "2026-11-13",
        "2026-11-15",
        1,
        0,
        "Flexible",
        "confirmed",
        "",
    ),
    (
        "BR-1047",
        "beach-resort",
        "Sarah Kim",
        "sarah.kim@example.com",
        "Silver",
        "GR-40263",
        "Standard King",
        "203",
        "2026-11-13",
        "2026-11-15",
        1,
        0,
        "Flexible",
        "confirmed",
        "",
    ),
    (
        "BR-1050",
        "beach-resort",
        "Priya Raman",
        "priya.raman@example.com",
        "none",
        None,
        "Suite",
        "402",
        "2026-11-20",
        "2026-11-23",
        2,
        0,
        "Non-refundable",
        "confirmed",
        "",
    ),
    (
        "BR-1055",
        "beach-resort",
        "Ben Turner",
        "ben.turner@example.com",
        "none",
        None,
        "Standard King",
        "209",
        "2026-11-27",
        "2026-11-29",
        2,
        1,
        "Flexible",
        "confirmed",
        "",
    ),
    (
        "BR-1061",
        "beach-resort",
        "Tom Becker",
        "tom.becker@example.com",
        "none",
        None,
        "Standard King",
        "207",
        "2026-10-27",
        "2026-10-30",
        1,
        0,
        "Flexible",
        "checked_out",
        "",
    ),
    (
        "BR-1065",
        "beach-resort",
        "Lily Chen",
        "lily.chen@example.com",
        "Gold",
        "GR-62019",
        "Ocean View King",
        "303",
        "2026-10-27",
        "2026-10-30",
        2,
        0,
        "Flexible",
        "checked_out",
        "",
    ),
    (
        "BR-1066",
        "beach-resort",
        "Grace Liu",
        "grace.liu@example.com",
        "Silver",
        "GR-27741",
        "Ocean View King",
        "302",
        "2026-11-01",
        "2026-11-04",
        2,
        1,
        "Flexible",
        "checked_in",
        "",
    ),
    (
        "BR-1070",
        "beach-resort",
        "Noah Fischer",
        "noah.fischer@example.com",
        "none",
        None,
        "Standard King",
        "208",
        "2026-10-31",
        "2026-11-05",
        2,
        1,
        "Flexible",
        "checked_in",
        "Travelling with an infant",
    ),
    (
        "BR-1075",
        "beach-resort",
        "Mia Rossi",
        "mia.rossi@example.com",
        "Gold",
        "GR-58830",
        "Ocean View King",
        "305",
        "2026-11-09",
        "2026-11-12",
        2,
        0,
        "Flexible",
        "confirmed",
        "",
    ),
    (
        "BR-1077",
        "beach-resort",
        "Liam Brooks",
        "liam.brooks@example.com",
        "none",
        None,
        "Ocean View King",
        "306",
        "2026-11-06",
        "2026-11-08",
        2,
        0,
        "Flexible",
        "confirmed",
        "",
    ),
    (
        "BR-1078",
        "beach-resort",
        "Ava Thompson",
        "ava.thompson@example.com",
        "none",
        None,
        "Standard King",
        "210",
        "2026-10-31",
        "2026-11-04",
        2,
        0,
        "Flexible",
        "checked_in",
        "",
    ),
    (
        "BR-1080",
        "beach-resort",
        "Chris Morgan",
        "chris.morgan@example.com",
        "none",
        None,
        "Standard King",
        "201",
        "2026-11-06",
        "2026-11-08",
        1,
        0,
        "Flexible",
        "confirmed",
        "",
    ),
    (
        "BR-1081",
        "beach-resort",
        "Chris Morgan",
        "c.morgan77@example.com",
        "Silver",
        "GR-33415",
        "Standard King",
        "202",
        "2026-11-20",
        "2026-11-22",
        2,
        0,
        "Flexible",
        "confirmed",
        "",
    ),
    (
        "BR-1084",
        "beach-resort",
        "Isabel Ortiz",
        "isabel.ortiz@example.com",
        "none",
        None,
        "Standard King",
        "204",
        "2026-11-20",
        "2026-11-23",
        2,
        0,
        "Flexible",
        "confirmed",
        "",
    ),
    (
        "BR-1088",
        "beach-resort",
        "Ethan Park",
        "ethan.park@example.com",
        "Platinum",
        "GR-91002",
        "Suite",
        "401",
        "2026-11-13",
        "2026-11-16",
        2,
        0,
        "Flexible",
        "confirmed",
        "",
    ),
    (
        "BR-1090",
        "beach-resort",
        "Aisha Khan",
        "aisha.khan@example.com",
        "Silver",
        "GR-36120",
        "Standard King",
        "206",
        "2026-11-06",
        "2026-11-08",
        1,
        0,
        "Flexible",
        "confirmed",
        "",
    ),
    (
        "BR-1091",
        "beach-resort",
        "Paul Simmons",
        "paul.simmons@example.com",
        "none",
        None,
        "Standard King",
        "205",
        "2026-10-29",
        "2026-11-01",
        1,
        0,
        "Flexible",
        "checked_out",
        "",
    ),
    (
        "BR-1093",
        "beach-resort",
        "Leah Novak",
        "leah.novak@example.com",
        "none",
        None,
        "Ocean View King",
        "301",
        "2026-11-01",
        "2026-11-03",
        1,
        0,
        "Flexible",
        "checked_in",
        "",
    ),
    (
        "BR-1095",
        "beach-resort",
        "Ruth Adams",
        "ruth.adams@example.com",
        "none",
        None,
        "Ocean View King",
        "301",
        "2026-11-13",
        "2026-11-15",
        2,
        0,
        "Flexible",
        "cancelled",
        "Cancelled by guest on 28 Oct",
    ),
    (
        "ML-2015",
        "mountain-lodge",
        "Daniel Reyes",
        "daniel.reyes@example.com",
        "Platinum",
        "GR-90211",
        "Cabin",
        "C2",
        "2026-11-13",
        "2026-11-16",
        3,
        0,
        "Flexible",
        "confirmed",
        "",
    ),
    (
        "ML-2021",
        "mountain-lodge",
        "Sofia Herrera",
        "sofia.herrera@example.com",
        "none",
        None,
        "Standard Queen",
        "104",
        "2026-11-20",
        "2026-11-22",
        2,
        0,
        "Flexible",
        "confirmed",
        "",
    ),
    (
        "ML-2025",
        "mountain-lodge",
        "Jack Wilson",
        "jack.wilson@example.com",
        "Silver",
        "GR-30554",
        "Standard Queen",
        "102",
        "2026-11-13",
        "2026-11-15",
        2,
        0,
        "Flexible",
        "confirmed",
        "",
    ),
    (
        "ML-2030",
        "mountain-lodge",
        "Mark Davies",
        "mark.davies@example.com",
        "none",
        None,
        "Standard Queen",
        "105",
        "2026-11-20",
        "2026-11-22",
        2,
        0,
        "Flexible",
        "confirmed",
        "",
    ),
    (
        "ML-2034",
        "mountain-lodge",
        "Hannah Cole",
        "hannah.cole@example.com",
        "Gold",
        "GR-57702",
        "Standard Queen",
        "103",
        "2026-11-27",
        "2026-11-29",
        2,
        0,
        "Flexible",
        "confirmed",
        "",
    ),
    (
        "ML-2040",
        "mountain-lodge",
        "Olivia Grant",
        "olivia.grant@example.com",
        "none",
        None,
        "Cabin",
        "C1",
        "2026-11-06",
        "2026-11-08",
        2,
        2,
        "Flexible",
        "confirmed",
        "",
    ),
    (
        "ML-2044",
        "mountain-lodge",
        "Ryan Patel",
        "ryan.patel@example.com",
        "none",
        None,
        "Cabin",
        "C3",
        "2026-11-13",
        "2026-11-15",
        2,
        0,
        "Flexible",
        "confirmed",
        "1 dog",
    ),
    (
        "ML-2048",
        "mountain-lodge",
        "Emma Walsh",
        "emma.walsh@example.com",
        "Silver",
        "GR-34519",
        "Cabin",
        "C4",
        "2026-11-01",
        "2026-11-04",
        2,
        0,
        "Flexible",
        "checked_in",
        "",
    ),
    (
        "ML-2050",
        "mountain-lodge",
        "Victor Hale",
        "victor.hale@example.com",
        "none",
        None,
        "Standard Queen",
        "101",
        "2026-10-30",
        "2026-11-01",
        2,
        0,
        "Flexible",
        "checked_out",
        "",
    ),
    (
        "ML-2052",
        "mountain-lodge",
        "Zoe Martin",
        "zoe.martin@example.com",
        "none",
        None,
        "Standard Queen",
        "106",
        "2026-11-01",
        "2026-11-04",
        2,
        0,
        "Flexible",
        "checked_in",
        "",
    ),
    (
        "ML-2056",
        "mountain-lodge",
        "Owen Price",
        "owen.price@example.com",
        "none",
        None,
        "Cabin",
        "C5",
        "2026-11-01",
        "2026-11-05",
        1,
        0,
        "Flexible",
        "checked_in",
        "",
    ),
    (
        "ML-2060",
        "mountain-lodge",
        "Kara Doyle",
        "kara.doyle@example.com",
        "none",
        None,
        "Standard Queen",
        "108",
        "2026-10-30",
        "2026-11-01",
        1,
        0,
        "Flexible",
        "no_show",
        "No-show; one night charged",
    ),
    (
        "ML-2062",
        "mountain-lodge",
        "Luis Romero",
        "luis.romero@example.com",
        "none",
        None,
        "Standard Queen",
        "108",
        "2026-11-06",
        "2026-11-08",
        2,
        1,
        "Flexible",
        "confirmed",
        "",
    ),
]

# Sold-out nights the sample emails rely on: Ocean View King over Thanksgiving, every Beach Resort suite on Sat 21 Nov.
BLOCKERS = [
    ("beach-resort", "Ocean View King", room, "2026-11-26", "2026-11-28")
    for room in ROOMS["beach-resort"]["Ocean View King"][0]
]
BLOCKERS += [
    ("beach-resort", "Suite", "401", "2026-11-20", "2026-11-22"),
    ("beach-resort", "Suite", "403", "2026-11-21", "2026-11-22"),
]

# Nights that must keep at least one room free (the emails ask for them).
KEEP_FREE = {
    ("beach-resort", "Standard King", "2026-11-15"),
    ("beach-resort", "Standard King", "2026-11-26"),
    ("beach-resort", "Standard King", "2026-11-27"),
    ("mountain-lodge", "Suite", "2026-11-20"),
    ("mountain-lodge", "Suite", "2026-11-21"),
    ("mountain-lodge", "Standard Queen", "2026-12-04"),
    ("mountain-lodge", "Standard Queen", "2026-12-05"),
}

FIRST = "Alex Jordan Taylor Morgan Casey Riley Avery Quinn Harper Rowan Sam Jamie Drew Reese Parker Logan Hayden Elliot Skyler Kendall".split()
LAST = "Bennett Carver Dalton Ellison Fairley Garrison Holloway Ingram Jarvis Kessler Lambert Mercer Norwood Osborne Prescott Quill Radford Sawyer Thornton Underwood Vance Whitaker".split()
TARGET_TOTAL = 80

SCHEMA = """
CREATE TABLE bookings (
  booking_id TEXT PRIMARY KEY, property TEXT NOT NULL, guest_name TEXT NOT NULL, email TEXT NOT NULL,
  loyalty_tier TEXT NOT NULL, member_number TEXT, room_type TEXT NOT NULL, room_number TEXT NOT NULL,
  check_in TEXT NOT NULL, check_out TEXT NOT NULL, adults INTEGER NOT NULL, children INTEGER NOT NULL,
  rate_plan TEXT NOT NULL, nightly_rate INTEGER NOT NULL, status TEXT NOT NULL, notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE rooms (property TEXT NOT NULL, room_type TEXT NOT NULL, room_number TEXT NOT NULL, flexible_rate INTEGER NOT NULL,
  PRIMARY KEY (property, room_number));
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def nights(check_in: str, check_out: str) -> list[str]:
    start, end = date.fromisoformat(check_in), date.fromisoformat(check_out)
    return [(start + timedelta(days=i)).isoformat() for i in range((end - start).days)]


def rate(prop: str, room_type: str, plan: str) -> int:
    base = ROOMS[prop][room_type][1]
    return round(base * (1 - NON_REFUNDABLE_DISCOUNT)) if plan == "Non-refundable" else base


def build_rows(seed: int = SEED) -> list[tuple]:
    """Every booking row, story first, then the seeded fill. Pure: no file access."""
    occupied: set[tuple[str, str, str]] = set()  # (property, room, night) for rooms that are taken
    rows = []

    def take(prop, room, check_in, check_out):
        for night in nights(check_in, check_out):
            key = (prop, room, night)
            assert key not in occupied, f"double-booked {key}"
            occupied.add(key)

    for bid, prop, name, email, tier, member, rtype, room, cin, cout, adults, kids, plan, status, notes in STORY:
        if status not in ("cancelled", "no_show"):
            take(prop, room, cin, cout)
        rows.append(
            (
                bid,
                prop,
                name,
                email,
                tier,
                member,
                rtype,
                room,
                cin,
                cout,
                adults,
                kids,
                plan,
                rate(prop, rtype, plan),
                status,
                notes,
            )
        )

    rng = random.Random(seed)
    counters = {"beach-resort": 1100, "mountain-lodge": 2100}

    def guest():
        first, last = rng.choice(FIRST), rng.choice(LAST)
        return f"{first} {last}", f"{first.lower()}.{last.lower()}{rng.randint(1, 99)}@example.com"

    def next_id(prop):
        counters[prop] += 1
        return ("BR-" if prop == "beach-resort" else "ML-") + str(counters[prop])

    for prop, rtype, room, cin, cout in BLOCKERS:
        take(prop, room, cin, cout)
        name, email = guest()
        rows.append(
            (
                next_id(prop),
                prop,
                name,
                email,
                "none",
                None,
                rtype,
                room,
                cin,
                cout,
                2,
                0,
                "Flexible",
                rate(prop, rtype, "Flexible"),
                "confirmed",
                "",
            )
        )

    def free_for_stay(prop, rtype, room, cin, cout):
        stay = nights(cin, cout)
        if any((prop, room, n) in occupied for n in stay):
            return False
        for n in stay:  # never take the last free room on a night an email needs
            if (prop, rtype, n) in KEEP_FREE:
                rooms = ROOMS[prop][rtype][0]
                free = sum(1 for r in rooms if (prop, r, n) not in occupied)
                if free <= 1:
                    return False
        return True

    attempts = 0
    while len(rows) < TARGET_TOTAL and attempts < 5000:
        attempts += 1
        prop = rng.choice(list(ROOMS))
        rtype = rng.choices(list(ROOMS[prop]), weights=[5, 3, 1])[0]
        start = WINDOW_START + timedelta(days=rng.randrange(WINDOW_DAYS - 4))
        cin, cout = start.isoformat(), (start + timedelta(days=rng.randint(1, 4))).isoformat()
        rooms = [r for r in ROOMS[prop][rtype][0] if free_for_stay(prop, rtype, r, cin, cout)]
        if not rooms:
            continue
        room = rng.choice(rooms)
        if date.fromisoformat(cout) <= TODAY:
            status = rng.choices(["checked_out", "no_show"], weights=[12, 1])[0]
        elif date.fromisoformat(cin) <= TODAY:
            status = "checked_in"
        else:
            status = rng.choices(["confirmed", "cancelled"], weights=[15, 1])[0]
        if status not in ("cancelled", "no_show"):
            take(prop, room, cin, cout)
        tier = rng.choices(["none", "Silver", "Gold", "Platinum"], weights=[10, 4, 3, 1])[0]
        member = None if tier == "none" else f"GR-{rng.randint(20000, 99999)}"
        plan = rng.choices(["Flexible", "Non-refundable"], weights=[4, 1])[0]
        name, email = guest()
        rows.append(
            (
                next_id(prop),
                prop,
                name,
                email,
                tier,
                member,
                rtype,
                room,
                cin,
                cout,
                rng.randint(1, 2),
                rng.choice([0, 0, 0, 1, 2]),
                plan,
                rate(prop, rtype, plan),
                status,
                "",
            )
        )
    return rows


def write_db(path: Path, seed: int = SEED) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    rows = build_rows(seed)
    with sqlite3.connect(tmp) as con:
        con.executescript(SCHEMA)
        con.executemany("INSERT INTO bookings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        con.executemany(
            "INSERT INTO rooms VALUES (?,?,?,?)",
            [(p, t, r, rate_) for p, types in ROOMS.items() for t, (rooms, rate_) in types.items() for r in rooms],
        )
        con.executemany(
            "INSERT INTO meta VALUES (?,?)",
            [
                ("synthetic", "true"),
                ("seed", str(seed)),
                ("generator", "scripts/make_data.py"),
                ("window", f"{WINDOW_START.isoformat()} + {WINDOW_DAYS} days"),
            ],
        )
    con.close()
    tmp.replace(path)  # atomic: a running app never reads a half-written database
    return len(rows)


if __name__ == "__main__":
    from src.config import BOOKINGS_DB

    count = write_db(BOOKINGS_DB)
    print(f"Wrote {count} synthetic reservations to {BOOKINGS_DB.relative_to(ROOT)} (seed {SEED}).")
