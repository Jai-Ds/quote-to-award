import hmac
import os
import shutil
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Quote to award", page_icon=":material/handshake:", layout="wide", initial_sidebar_state="auto")


def secret(name, default=None):
    try:
        return st.secrets.get(name) or os.environ.get(name) or default
    except Exception:   # no secrets file on a local machine
        return os.environ.get(name) or default


# The hosted copy reads its key from the app's secrets. Locally it comes from a file outside the repo.
if secret("ANTHROPIC_API_KEY"):
    os.environ.setdefault("ANTHROPIC_API_KEY", secret("ANTHROPIC_API_KEY"))

from core import agentkit, data, db, org, ui  # noqa: E402

@st.cache_resource
def load_recorded_answers():
    """Copies recorded model answers into the runtime once per server start, adding any new ones."""
    replay = data.RUNTIME / "replay"
    replay.mkdir(parents=True, exist_ok=True)
    seed = Path(__file__).parent / "replay_seed"
    for f in seed.glob("*.json"):
        if not (replay / f.name).exists():
            shutil.copy2(f, replay / f.name)
    return True


load_recorded_answers()
ui.load_style()
st.html("<style>" + (Path(__file__).parent / "core" / "extra.css").read_text(encoding="utf-8") + "</style>")

DEMO_PASSWORD = str(secret("DEMO_PASSWORD", "123456789"))
ROLE_HELP = {
    "cbe_pm": "Runs Coimbatore's RFx: quotes, comparison, award.",
    "maa_pm": "Sees Chennai's quotes and decisions.",
    "cat_mgr": "Approves decisions that affect both plants.",
    "admin": "Sees everything, including how the system works.",
}


def sign_in():
    st.html("<style>[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl']{display:none}</style>")
    st.html('<div class="signin-head"><div class="brand-mark">QA</div><div><h1>Quote to award</h1><p>From messy vendor quotes to an approved award, across two plants.</p></div></div>')
    left, right = st.columns([1.1, 1])
    with left, st.form("sign_in"):
        users = org.users()
        uid = st.radio("Sign in as", list(users), format_func=lambda u: users[u]["name"], captions=[ROLE_HELP[u] for u in users])
        typed = st.text_input("Password", type="password", help="Every demo account uses the password shown on the right.")
        if st.form_submit_button("Sign in", type="primary", icon=":material/login:"):
            if hmac.compare_digest(typed.encode(), DEMO_PASSWORD.encode()):
                st.session_state.user = org.user(uid)
                st.rerun()
            st.error("That password isn't right.")
    with right:
        st.html(f"""<div class="signin-note"><b>Demo accounts</b><p>All four accounts use the password <code>{ui.esc(DEMO_PASSWORD)}</code>.</p>
        <p>Each person sees only what their role allows. The rule is enforced in code, so typing a different role in chat changes nothing.</p>
        <p>Company, vendors and plants are fictional.</p></div>""")
    st.stop()


if "user" not in st.session_state:
    sign_in()

u = st.session_state.user
role, plant = u["role"], u["plant"]
P = {
    "inbox": st.Page("screens/inbox.py", title="Inbox", icon=":material/inbox:"),
    "compare": st.Page("screens/compare.py", title="Compare and ask", icon=":material/table_chart:"),
    "approvals": st.Page("screens/approvals.py", title="Approvals", icon=":material/task_alt:"),
    "plants": st.Page("screens/all_plants.py", title="All plants", icon=":material/factory:"),
    "cases": st.Page("screens/test_cases.py", title="Test cases", icon=":material/fact_check:"),
}
MENU = {
    ("plant_manager", "CBE"): ["inbox", "compare", "approvals"],
    ("plant_manager", "MAA"): ["compare", "approvals"],
    ("category_manager", None): ["approvals"],
    ("admin", None): ["plants", "approvals", "inbox", "compare"],
}[(role, plant)] + ["cases"]
if plant == "MAA":
    P["compare"] = st.Page("screens/compare.py", title="Compare", icon=":material/table_chart:")
pages = [P[k] for k in MENU]
nav = st.navigation(pages, position="hidden")

with st.sidebar:
    st.html(f'<div class="brand"><div class="brand-mark">QA</div><div><b>Quote to award</b><small>Kesavi Personal Care</small></div></div>')
    st.html(f'<div class="who"><span>Signed in as</span><b>{ui.esc(u["name"])}</b><small>{ui.esc(org.plant_name(plant))}</small></div>')
    waiting = len(org.reviews_for(u)) + (len({a["vendor"] for a in db.approvals()}) if role in ("plant_manager", "admin") and plant in ("CBE", None) else 0)
    for p in pages:
        label = p.title
        if p.title == "Approvals" and org.reviews_for(u):
            label += f" ({len(org.reviews_for(u))})"
        if p.title == "Inbox" and db.approvals():
            label += f" ({len({a['vendor'] for a in db.approvals()})})"
        st.page_link(p, label=label, icon=p.icon)
    if plant in ("CBE", None) and role in ("plant_manager", "admin"):
        ui.live()
    with st.expander("Live AI", icon=":material/bolt:"):
        if agentkit.LIVE["on"]:
            st.caption("Live AI is on. New questions call the model, up to the daily limit.")
        else:
            st.caption("Off. Recorded answers replay for the demo path and the suggested questions. Typed questions need live AI.")
            live_pw = secret("LIVE_PASSWORD")
            if live_pw and os.environ.get("ANTHROPIC_API_KEY"):
                pw = st.text_input("Live AI password", type="password", key="live_pw")
                if pw and hmac.compare_digest(pw.encode(), str(live_pw).encode()):
                    agentkit.LIVE["on"] = True
                    st.rerun()
            else:
                st.caption("Not set up on this copy.")
    if st.button("Sign out", icon=":material/logout:", type="tertiary"):
        st.session_state.clear()
        st.rerun()
    st.caption("All company and vendor data is fictional.")
nav.run()
