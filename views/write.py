"""Write your own email: type a guest email (or pick an example) and run the agent on it."""

import streamlit as st

from src import policy_search
from src.agent import Email
from src.config import MAX_EMAIL_CHARS, MAX_EMAILS_PER_SESSION
from src.service import process
from src.tools import PROPERTY_NAMES
from views import components as ui

VISITOR = ("visitor@example.com", "", "A new guest (no booking)")
# Sample guests from the synthetic bookings, so a visitor can try the booking lookup too.
AS_GUEST = {
    "beach-resort": [
        VISITOR,
        ("elena.marsh@example.com", "Elena Marsh", "Elena Marsh · booking BR-1042, arrives Fri 6 Nov"),
        ("ethan.park@example.com", "Ethan Park", "Ethan Park · Platinum, Suite, 13–16 Nov"),
    ],
    "mountain-lodge": [
        VISITOR,
        ("daniel.reyes@example.com", "Daniel Reyes", "Daniel Reyes · booking ML-2015, Cabin, 13–16 Nov"),
        ("owen.price@example.com", "Owen Price", "Owen Price · staying now in Cabin C5"),
    ],
}

b = ui.brand()
ui.header(
    "Write your own email",
    "Write the way a guest would. The agent drafts a reply for you to approve; nothing is sent.",
    "Try it",
)
ui.warm_up()
no_key = ui.secrets_missing()

c1, c2 = st.columns(2)
prop = c1.selectbox("Inbox", list(PROPERTY_NAMES), format_func=PROPERTY_NAMES.get, key="write_prop")
senders = AS_GUEST[prop]
sender = c2.selectbox(
    "Write as",
    senders,
    format_func=lambda s: s[2],
    key=f"write_as_{prop}",
    help="Pick a sample guest to see the booking lookup. All guests are fictional.",
)

examples = b.examples(prop)
if examples:
    choice = st.pills(
        "Examples",
        [f"Example {i}" for i in range(1, len(examples) + 1)],
        key=f"ex_{prop}",
        help="Fills the email box with a sample guest email",
    )
    if choice and st.session_state.get("last_example") != (prop, choice):
        st.session_state.last_example = (prop, choice)
        st.session_state.write_body = examples[int(choice.split()[-1]) - 1]

subject = st.text_input("Subject (optional)", key="write_subject", max_chars=120)
body = st.text_area(
    "Guest email",
    key="write_body",
    height=180,
    max_chars=MAX_EMAIL_CHARS,
    placeholder="Hi, we arrive Friday with our dog. Is there a pet fee, and can we check out late?",
)
go = st.button("Run the agent", type="primary", icon=":material/smart_toy:", disabled=no_key)
note = st.empty()  # filled after a run, so the count includes it (it showed the old count in the first live test)

if go:
    email = Email(sender=sender[0], subject=subject.strip(), body=body, sender_name=sender[1])
    with st.spinner("Reading the email, checking the booking and policy, drafting a reply…"):
        result, record = process(
            email,
            prop,
            source="write",
            session_id=ui.session_id(),
            first=ui.is_first(),
            session_count=ui.emails_sent_to_agent(),
            daily_counter=ui.daily_counter(),
            keyword_matches=lambda text: policy_search.keyword_matches(text, prop),
        )
    if result.api_calls:
        ui.count_email()
    st.session_state.write_result = (
        result,
        record["request_id"],
        {
            "from": email.sender,
            "subject": email.subject,
            "property": prop,
            "name": email.sender_name,
            "body": email.body,
        },
    )

left = MAX_EMAILS_PER_SESSION - ui.emails_sent_to_agent()
note.caption(
    f"Don't enter real personal details. {max(left, 0)} of {MAX_EMAILS_PER_SESSION} emails left in this "
    "session. Greetings and off-topic text get a quick reply without using the agent."
)

if "write_result" in st.session_state:
    result, request_id, email = st.session_state.write_result
    st.divider()
    ui.result_panel(result, request_id, email, key=f"write_{request_id}", page="Write your own email")
ui.footer()
