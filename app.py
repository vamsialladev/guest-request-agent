"""Staff-facing web app:  streamlit run app.py

Pages live in views/ and stay thin; the logic is in src/ and unit-tested.
"""

from pathlib import Path

import codeguard

updated = codeguard.refresh(Path(__file__).parent)  # after an in-place update, never mix old and new modules

import streamlit as st  # noqa: E402

if updated:
    st.cache_resource.clear()  # cached objects were built by the old code

from src.config import admin_password  # noqa: E402
from views import components as ui  # noqa: E402

b = ui.brand()
st.set_page_config(page_title=b.name, page_icon=ui.asset(b.icon), layout="wide", initial_sidebar_state="auto")
ui.inject_css()
st.logo(ui.asset(b.logo), icon_image=ui.asset("assets/logo-icon.svg"), size="large")

pages = [
    st.Page("views/inbox.py", title="Inbox", icon=":material/inbox:", default=True),
    st.Page("views/write.py", title="Write your own email", icon=":material/edit_note:", url_path="write"),
    st.Page("views/outbox.py", title="Outbox and tasks", icon=":material/outbox:", url_path="outbox"),
    st.Page("views/how_it_works.py", title="How it works", icon=":material/schema:", url_path="how-it-works"),
    st.Page("views/about.py", title="Disclaimer and privacy", icon=":material/policy:", url_path="privacy"),
]
# Owner-only page: doesn't exist unless ADMIN_PASSWORD is set, and stays out of the menu until unlocked.
if admin_password():
    gate = st.session_state.get("admin_gate")
    unlocked = bool(gate and gate.unlocked)
    pages.append(
        st.Page(
            "views/admin.py",
            title="Admin",
            icon=":material/admin_panel_settings:",
            url_path="admin",
            visibility="visible" if unlocked else "hidden",
        )
    )
    pages.append(  # Final stage: the shared ops traces (hotel-ai-platform), behind the same sign-in as Admin
        st.Page(
            "views/traces.py",
            title="Traces",
            icon=":material/account_tree:",
            url_path="traces",
            visibility="visible" if unlocked else "hidden",
        )
    )
    pages.append(  # Project 4: owner-only, behind the same sign-in as Admin
        st.Page(
            "views/operations.py",
            title="Operations",
            icon=":material/monitoring:",
            url_path="operations",
            visibility="visible" if unlocked else "hidden",
        )
    )

page = st.navigation(pages)
ui.app_started()
ui.startup_checks()
ui.structured_startup_log()  # one JSON line each: app start + version, config set/missing, dependencies
with ui.error_boundary("Staff panel"):
    ui.staff_panel(ui.recent_drafts)
with ui.error_boundary(page.title):  # no page ever shows Streamlit's crash screen or a traceback
    page.run()
