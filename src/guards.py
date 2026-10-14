"""Checks on every draft before staff see it. Pure functions, unit-tested, each shown able to fail.

1. Forbidden promises: the draft must never say a refund, comp, upgrade, cancellation, rate or date change or fee
   waiver is done, approved or will happen. Describing a policy ("free cancellation up to 48 hours before arrival")
   is fine; committing to it ("we'll cancel your booking free of charge") is not. Offending sentences are replaced
   with a neutral sentence and the draft is flagged.
2. Fact grounding: every date, price, percentage, time, room number and quantity with a unit (40 lbs, 24 hours,
   3 nights) in the draft must appear in a tool result. A number the guest wrote may be repeated (to correct it, for
   example); anything else is flagged for staff to check. The same idea as Project 1's numeric grounding.
3. Citations: [P1]-style markers must point at a passage the agent actually retrieved.
"""

import re

# ---------- 1. Forbidden promises ----------
OBJECTS = (
    r"(refund\w*|reimburs\w*|compensat\w*|credit\w*|upgrad\w*|cancel\w*|waiv\w*|discount\w*|comp(ed|ing)?|"
    r"price[- ]match\w*|rate|charges?|fees?|reduc\w*|lower\w*|reembols\w*|cancela\w*|mejora\w*|exoner\w*)"
)
# "whether we match" and "if we upgrade" are questions, not commitments (dev eval, sample email E29).
COMMIT = (
    r"(?<!whether )(?<!if )\b(we|i)(['’](ll|ve|d|m))?(\s+(will|'ll|have|'ve|are|am|can|could|would|shall|just|"
    r"already|now|also|happily|gladly|be|been|going to|able to|happy to|pleased to|glad to))*\s+"
)
FORBIDDEN_PATTERNS = [
    # "we will refund you", "I've cancelled your booking", "we can waive the fee", "I have upgraded you".
    # "comp" only as the verb (comp, comped, comping): "compare" is not a promise (dev eval, sample email E29).
    COMMIT + r"(refund\w*|reimburs\w*|compensat\w*|credit\w*|upgrad\w*|cancel\w*|waiv\w*|discount\w*|"
    r"comp(s|ed|ing)?|price[- ]match\w*|reduc\w*|lower\w*|remov\w*|revers\w*|adjust\w*|chang\w*|match\w*|mov\w*|"
    r"switch\w*|rebook\w*|extend\w*)\b(?!.{0,40}\b(request|approval|review)\b)",
    # "your refund has been processed", "the upgrade is confirmed", "the fee is waived"
    r"\b(your|the|a|this)\s+(full\s+|partial\s+)?" + OBJECTS + r"\s+(has been|have been|is|was|will be)\s+"
    r"(processed|approved|confirmed|issued|applied|granted|waived|removed|reversed|completed|done|arranged|cancel\w*)",
    # "you will receive a full refund", "you'll get a free upgrade"
    r"\byou('ll| will| are going to| should)\s+(receive|get|be given|be getting)\s+(a\s+|an\s+|the\s+|your\s+)?"
    r"(full\s+|partial\s+|complimentary\s+|free\s+)?" + OBJECTS,
    # Spanish: "le reembolsaremos", "hemos cancelado su reserva"
    r"\b(le |les )?(reembolsaremos|cancelaremos|hemos cancelado|hemos reembolsado|le hemos mejorado|"
    r"le daremos (un|una) (reembolso|mejora))\b",
]
FORBIDDEN = re.compile("|".join(f"(?:{p})" for p in FORBIDDEN_PATTERNS), re.I)
# Offers without a verb ("enjoy a complimentary upgrade", "breakfast is on us") count unless the sentence negates them:
# "I'm not able to offer a free upgrade myself" is the safe answer (the dev eval flagged it on sample email E09).
OFFERS = re.compile(
    r"\b(complimentary|free(\s+of\s+charge)?)\s+(upgrade|night|stay|room|breakfast|dinner|spa|massage)\b"
    r"(?!.{0,60}\b(benefit|policy|includ|members?|tier)\b)|\b(on us|on the house|at no (extra )?cost to you)\b",
    re.I,
)
NEGATED = re.compile(r"\b(not|no|never|unable|cannot)\b|n['’]t\b", re.I)
# "your request for a complimentary upgrade" names what the guest asked for; it offers nothing (dev eval, E09 and X07).
REQUESTED = re.compile(r"\brequest(s|ed)?\s+(for\s+)?(a\s+|an\s+)?(complimentary|free)\b", re.I)
# "I can't confirm that we can match the lower price" refuses; it doesn't commit (final eval, sample email E29).
HEDGED = re.compile(
    r"\b(can['’]?t|cannot|can not|could not|couldn['’]t|unable to|not able to|won['’]t be able to)\s+(yet\s+)?"
    r"(confirm|promise|guarantee|say|tell you)\b",
    re.I,
)
SAFE_SENTENCE = "I've passed this request to our manager, who will review it and reply to you."
SENTENCE = re.compile(r"[^.!?\n]+[.!?]*\s*|\n")


def _commits(sentence: str) -> bool:
    """A promising phrase that isn't under a negated "confirm / promise / guarantee" earlier in the sentence."""
    return any(not HEDGED.search(sentence[: m.start()]) for m in FORBIDDEN.finditer(sentence))


def forbidden_promises(text: str) -> list[str]:
    """The sentences in `text` that promise a refund, comp, upgrade, cancellation, rate/date change or waiver."""
    hits = []
    for sentence in SENTENCE.findall(text or ""):
        offer = OFFERS.search(REQUESTED.sub("request", sentence)) and not NEGATED.search(sentence)
        if _commits(sentence) or offer:
            hits.append(sentence.strip())
    return hits


def remove_promises(text: str) -> tuple[str, list[str]]:
    """Replace each promising sentence with one neutral sentence (once). Returns (new text, removed sentences)."""
    removed = forbidden_promises(text)
    if not removed:
        return text, []
    out, replaced = [], False
    for sentence in SENTENCE.findall(text):
        if sentence.strip() in removed:
            trail = sentence[len(sentence.rstrip()) :]
            if not replaced:
                out.append(SAFE_SENTENCE + (trail or " "))
                replaced = True
            elif "\n" in trail:  # keep the paragraph break that followed a removed sentence
                out[-1] = out[-1].rstrip(" ") + trail
            continue
        out.append(sentence)
    return "".join(out).strip(), removed


# ---------- 2. Fact grounding ----------
MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
MONTH_WORD = (
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|"
    r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|setiembre|octubre|noviembre|diciembre)"
)
UNITS = {
    "lb": "lb",
    "lbs": "lb",
    "pound": "lb",
    "pounds": "lb",
    "libras": "lb",
    "hour": "h",
    "hours": "h",
    "hrs": "h",
    "hr": "h",
    "horas": "h",
    "hora": "h",
    "night": "night",
    "nights": "night",
    "noche": "night",
    "noches": "night",
    "day": "day",
    "days": "day",
    "día": "day",
    "días": "day",
    "dias": "day",
    "mile": "mile",
    "miles": "mile",
    "millas": "mile",
    "minute": "min",
    "minutes": "min",
    "min": "min",
    "minutos": "min",
    "point": "point",
    "points": "point",
    "puntos": "point",
}
WORD_NUMBERS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "twelve": 12,
    "fifteen": 15,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
}

MONEY = re.compile(
    r"(?:US)?\$\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?|(\d+(?:\.\d{1,2})?)\s?(?:USD|dólares|dolares)", re.I
)
PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s?(%|percent|por ciento)", re.I)
TIME_12 = re.compile(r"\b(\d{1,2})(?:[:.](\d{2}))?\s?(a\.?\s?m\.?|p\.?\s?m\.?)(?![a-z])", re.I)
TIME_24 = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b(?!\s?(?:a\.?\s?m|p\.?\s?m))", re.I)
NOON = re.compile(r"\b(noon|midday|mediod[ií]a|midnight|medianoche)\b", re.I)
ISO_DATE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
# Spaces only, never a line break: "9 Nov.\n\n3. MIA pickup" (a numbered list) read as "Nov 3" in the first app run.
DATE_MD = re.compile(r"\b" + MONTH_WORD + r"\.?[ \t]+(\d{1,2})(?:st|nd|rd|th)?\b(?!\.\d)", re.I)
DATE_DM = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?[ \t]+(?:of[ \t]+|de[ \t]+)?" + MONTH_WORD + r"\b", re.I)
ROOM = re.compile(r"\b(?:room|habitaci[oó]n|cabin|caba[ñn]a|suite)\s+(?:number\s+|no\.?\s+|#)?([A-Z]?\d{1,4})\b", re.I)
QUANTITY = re.compile(
    r"\b(\d+|" + "|".join(WORD_NUMBERS) + r")(?:-|\s)?(" + "|".join(sorted(UNITS, key=len, reverse=True)) + r")\b", re.I
)


def _month(word: str) -> int:
    word = word.lower()
    return MONTHS.get(word, MONTHS.get(word[:3], 0))


def extract_facts(text: str) -> set[str]:
    """Normalized facts in a text: '$75', '10%', 'time 14:00', 'date 11-06', 'room 304', '40 lb'.
    Dates drop the year (the synthetic world is 2026); ambiguous numeric dates like 11/6 are not checked."""
    text = text or ""
    facts: set[str] = set()
    for m in MONEY.finditer(text):
        if m.group(3):
            whole, cents = m.group(3).split(".") if "." in m.group(3) else (m.group(3), None)
        else:
            whole, cents = m.group(1).replace(",", ""), m.group(2)
        cents = cents if cents and int(cents) else None
        facts.add(f"${int(whole)}" + (f".{int(cents):02d}" if cents else ""))
    for m in PERCENT.finditer(text):
        facts.add(f"{float(m.group(1)):g}%")
    for m in TIME_12.finditer(text):
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        if not 1 <= hour <= 12:
            continue
        pm = m.group(3).lower().startswith("p")
        facts.add(f"time {(hour % 12) + (12 if pm else 0):02d}:{minute:02d}")
    for m in TIME_24.finditer(text):
        facts.add(f"time {int(m.group(1)):02d}:{m.group(2)}")
    for m in NOON.finditer(text):
        facts.add("time 00:00" if m.group(1).lower().startswith(("midn", "medianoche")) else "time 12:00")
    for m in ISO_DATE.finditer(text):
        facts.add(f"date {int(m.group(2)):02d}-{int(m.group(3)):02d}")
    for m in DATE_MD.finditer(text):
        month, day = _month(m.group(1)), int(m.group(2))
        if month and 1 <= day <= 31:
            facts.add(f"date {month:02d}-{day:02d}")
    for m in DATE_DM.finditer(text):
        day, month = int(m.group(1)), _month(m.group(2))
        if month and 1 <= day <= 31:
            facts.add(f"date {month:02d}-{day:02d}")
    for m in ROOM.finditer(text):
        facts.add(f"room {m.group(1).upper()}")
    for m in QUANTITY.finditer(text):
        raw = m.group(1).lower()
        n = int(raw) if raw.isdigit() else WORD_NUMBERS[raw]
        facts.add(f"{n} {UNITS[m.group(2).lower()]}")
    return facts


def ungrounded_facts(draft: str, sources: list[str], email_text: str = "") -> list[str]:
    """Facts in the draft that appear in no tool result (and not in the guest's own email). Sorted for stable output."""
    allowed = set()
    for text in [*sources, email_text]:
        allowed |= extract_facts(text)
    return sorted(extract_facts(draft) - allowed)


# ---------- 3. Citations ----------
CITATION = re.compile(r"\[(P\d+)\]")


def citation_ids(text: str) -> list[str]:
    seen = []
    for pid in CITATION.findall(text or ""):
        if pid not in seen:
            seen.append(pid)
    return seen


def unknown_citations(text: str, known: set[str]) -> list[str]:
    return [pid for pid in citation_ids(text) if pid not in known]


def strip_unknown_citations(text: str, known: set[str]) -> str:
    return CITATION.sub(lambda m: m.group(0) if m.group(1) in known else "", text)


def strip_citations(text: str) -> str:
    """What the guest receives: the draft without [P1] markers (and without the space before them)."""
    return re.sub(r"\s?\[P\d+\]", "", text or "")
