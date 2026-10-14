"""Deterministic checks that run before the model: no API call, unit-tested, explainable to a manager.

- `classify_input`: empty, too long, greeting or off-topic text typed into "Write your own email" gets a friendly
  reply without spending an API call.
- `escalation_reasons`: injury, medical, safety, legal threats, harassment, discrimination, press, refund demands in a
  complaint and very angry tone. Any hit sends the email to a manager, whatever the model later decides.
- `injection_markers`: text that tries to instruct the assistant. The email is always treated as data; a hit is shown
  to staff and the model is told the email contains instructions to ignore.
"""

import re

GREETINGS = re.compile(
    r"^(hi|hello|hey|hiya|good (morning|afternoon|evening)|thanks?|thank you|hola|buenos d[ií]as|test|testing)"
    r"[\s!.,?]*(there|team|all)?[\s!.,?]*$",
    re.I,
)
# Words that mark hotel business. Text with none of them and no keyword match in the policy documents is off-topic.
HOTEL_WORDS = re.compile(
    r"\b(room|rooms|stay|stays|staying|book|booking|booked|reserv\w*|check[\s-]?(in|out)|checkout|checkin|hotel|"
    r"resort|lodge|night|nights|arriv\w*|depart\w*|pet|pets|dog|dogs|cat|parking|park|valet|pool|spa|massage|"
    r"breakfast|wifi|wi-fi|internet|refund|cancel\w*|upgrade|suite|cabin|towel\w*|housekeeping|shuttle|airport|"
    r"pickup|transfer|luggage|bags|late|early|fee|fees|rate|price|cost|charge\w*|bill|invoice|loyalty|points|member|"
    r"gold|silver|platinum|wedding|event|restaurant|dinner|lunch|room service|noise|quiet|crib|bed|beds|rollaway|"
    r"lost|left|forgot|key|guest|guests|trip|vacation|weekend|habitaci[oó]n|reserva|perro|mascota|desayuno|noche)\b",
    re.I,
)

ESCALATION_RULES: list[tuple[str, re.Pattern]] = [
    (
        "injury or medical",
        re.compile(
            r"\b(injur\w*|hurt (my|his|her|their|our)\w*|bleed\w*|stitches|hospital\w*|ambulance|emergency room|"
            r"paramedic\w*|allergic reaction|anaphyla\w*|epipen|food poisoning|concussion|broke (my|his|her) \w+|"
            r"slipped (and|on|in|by|near)|fell (down|over)|fell (on|in) the \w+|sick after|"
            r"medical|doctor|urgent care|herid\w*|m[eé]dico)\b",
            re.I,
        ),
    ),
    (
        "safety",
        re.compile(
            r"\b(gas (leak|smell)|smell(s|ed)? (of )?gas|carbon monoxide|smoke (alarm|coming|detector)|on fire|"
            r"fire alarm|unsafe|dangerous|break-?in|broken into|stolen|theft|robbed|assault\w*|weapon|threaten\w*|"
            r"bed ?bugs?)\b",
            re.I,
        ),
    ),
    (
        "legal threat",
        re.compile(
            r"\b(lawyer|attorney|lawsuit|sue (you|the hotel|them|your)|suing|legal action|"
            r"(see you|take you|go) (in|to) court|small claims|chargeback|abogad\w*|demanda)\b",
            re.I,
        ),
    ),
    (
        "harassment",
        re.compile(
            r"\b(harass\w*|inappropriate (comment|remark|touch|behaviou?r)\w*|"
            r"made me (feel )?(very |so |really )?(uncomfortable|unsafe)|(don'?t|do not) feel safe|"
            r"followed me|touched me|sexual\w*|stalk\w*|acoso)\b",
            re.I,
        ),
    ),
    (
        "discrimination",
        re.compile(
            r"\b(racis[mt]\w*|discriminat\w*|homophobic|transphobic|sexist|bigot\w*|slur\w*|discrimina\w*)\b", re.I
        ),
    ),
    (
        "press or media",
        re.compile(
            r"\b(reporter|journalist|newspaper|news (story|article)|press (inquiry|enquiry)|media (inquiry|enquiry)|"
            r"writing (a|an) (story|article|piece)|for (a|an|my) (story|article)|on the record|periodista)\b",
            re.I,
        ),
    ),
]
REFUND_DEMAND = re.compile(r"\b(refund|money back|compensat\w*|reimburs\w*|reembolso|devolu\w*)\b", re.I)
COMPLAINT = re.compile(
    r"\b(terrible|horrible|awful|unacceptable|disgust\w*|worst|ruined|never (again|coming back|stay)|"
    r"complain\w*|filthy|dirty|appalling|outrageous|nightmare|ridiculous|inaceptable)\b",
    re.I,
)
PROFANITY = re.compile(r"\b(damn|hell|crap|wtf|f\*+|s\*+t|bs|bullshit|pissed)\b", re.I)


def angry_tone(text: str) -> str | None:
    """Very angry tone: shouting (several all-caps words), a run of exclamation marks, or profanity."""
    shouted = [
        w
        for w in re.findall(r"\b[A-Z]{3,}\b", text)
        if w not in {"MIA", "AVL", "FLL", "USD", "PMS", "AM", "PM", "ASAP", "TV", "AC", "OK", "VIP"}
    ]
    if len(shouted) >= 3:
        return "very angry tone (shouting)"
    if re.search(r"!{3,}", text):
        return "very angry tone (!!!)"
    if PROFANITY.search(text):
        return "very angry tone (profanity)"
    return None


def escalation_reasons(text: str) -> list[str]:
    """Plain-language reasons this email needs a manager, each with the words that triggered it."""
    reasons = []
    for label, pattern in ESCALATION_RULES:
        match = pattern.search(text)
        if match:
            reasons.append(f"{label} (“{match.group(0)}”)")
    refund = REFUND_DEMAND.search(text)
    complaint = COMPLAINT.search(text)
    # An injected "SYSTEM NOTICE TO THE AI ASSISTANT" is capitals but not shouting (found on sample email E16).
    tone = angry_tone(INJECTION.sub(" ", text))
    if refund and (complaint or tone):
        reasons.append(f"refund demand in a complaint (“{refund.group(0)}”)")
    if tone:
        reasons.append(tone)
    return reasons


INJECTION_PATTERNS = [
    r"ignore (all |any |the |your )?(previous |prior |above |earlier )?(instructions|rules|prompts?)",
    r"disregard (all |any |the |your )?(previous |prior |above )?(instructions|rules)",
    r"system (prompt|notice|message|override|instruction)",
    r"you are now",
    r"(admin|developer|debug|god) mode",
    r"(ai|virtual) assistant[:,]",
    r"(print|reveal|show|repeat|output) (me )?(your|the) (system )?(prompt|instructions|rules|tools?)",
    r"approve (a |the )?(full |partial )?(refund|upgrade|comp|credit|waiver|discount)",
    r"(forward|send|give) (me )?(the )?(reservation|booking|guest) (details|information|info) (for|of)",
    r"this is the (general )?manager",
    r"ignora (las |todas |tus )?(instrucciones|reglas)",
    r"<\s*/?\s*(system|instructions?)\s*>",
]
INJECTION = re.compile("|".join(f"(?:{p})" for p in INJECTION_PATTERNS), re.I)


def injection_markers(text: str) -> list[str]:
    return [m.group(0) for m in INJECTION.finditer(text)][:5]


def classify_input(text: str, max_chars: int, keyword_matches=None) -> str:
    """For "Write your own email": 'empty' | 'too_long' | 'greeting' | 'off_topic' | 'email'.
    `keyword_matches(text)` counts policy passages sharing a keyword (optional, used for off-topic)."""
    stripped = " ".join((text or "").split())
    if not stripped:
        return "empty"
    if len(text) > max_chars:
        return "too_long"
    if GREETINGS.match(stripped):
        return "greeting"
    if HOTEL_WORDS.search(stripped) or escalation_reasons(stripped):
        return "email"
    if keyword_matches is not None and keyword_matches(stripped) > 0 and len(stripped.split()) >= 4:
        return "email"
    return "off_topic"


SPANISH_WORDS = re.compile(
    r"\b(el|la|los|las|de|del|que|por|para|con|una|un|su|sus|usted|gracias|hola|reserva|habitaci[oó]n|est[aá]|"
    r"podemos|puede|nuestro|nuestra|desayuno|también|muy|saludos)\b",
    re.I,
)


def detect_language(text: str) -> str:
    """'es' or 'en'. The model's own language label was wrong once (a Spanish reply labelled 'en', dev eval X05), so
    the log and the eval use the text itself."""
    words = re.findall(r"\w+", text or "")
    hits = len(SPANISH_WORDS.findall(text or ""))
    return "es" if words and hits >= max(3, len(words) * 0.08) else "en"


GREETING_REPLY = (
    "Hi! This demo drafts replies to guest emails. Write an email the way a guest would, for example: "
    "“Hi, we arrive Friday with our dog. Is there a pet fee, and can we check out late on Monday?”"
)
OFF_TOPIC_REPLY = (
    "This demo only handles guest emails to the hotel: bookings, availability, policies and requests during a stay. "
    "Try writing as a guest, for example: “Can I add a night to my stay?”"
)
EMPTY_REPLY = "Write a guest email first, or pick an example below."
