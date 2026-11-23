import pandas as pd
import streamlit as st

from core import agentkit, db, flow, org, ui

u = st.session_state.user
if u["role"] != "admin":
    st.error("Only the admin can open this page.")
    st.stop()

ui.header("All plants", "Everything in one place, including how the system works")
names = ui.names()
cfg = org.config()
decs = org.decisions()
open_reviews = org.reviews()
ui.cards([
    {"label": "Plants", "value": len(cfg["plants"])},
    {"label": "Decisions recorded", "value": len(decs)},
    {"label": "Waiting for approval", "value": len(open_reviews), "tone": "warn" if open_reviews else "good"},
    {"label": "Blocked access attempts", "value": len(org.access_log()), "tone": "warn" if org.access_log() else "neutral"},
])

tabs = st.tabs(["Plants and decisions", "Approvals and history", "Access log", "Agent trace", "Rules"])

with tabs[0]:
    for code, p in cfg["plants"].items():
        st.markdown(f"**{p['name']}**: {p['makes']}. Buys on: {p['buys_on']}. RFx {p['rfx']}.")
    rows = [[ui.esc(org.plant_name(d["plant"])), f"<b>{ui.esc(d['material'])}</b>", ui.vendor_cell(d["vendor"]), f"Rs {d['price']:,.2f}", f"{d['annual_kg']:,.0f} kg",
             ui.esc(d["reason"]), ui.badge(d["status"], "good" if "Approved" in d["status"] else "warn")] for d in decs]
    ui.table(["Plant", "Line", "Vendor", "Price/kg", "Per year", "Reason", "Status"], rows)
    if flow.has_replies():
        q, _ = flow.scored()
        st.caption("Coimbatore's normalized quotes, as the rule engine sees them")
        cols = ["vendor", "material", "quoted_price", "quoted_unit", "cost_inr_per_spec_kg", "moq_kg", "otif", "otif_claim_pct", "claim_status", "cleared_questionnaire", "sku_score", "rank_in_sku"]
        st.dataframe(ui.readable(q[[c for c in cols if c in q.columns]]), hide_index=True)

with tabs[1]:
    for r in org.reviews(None):
        with st.container(border=True):
            st.html(f"<b>{ui.esc(r['title'])}</b> {ui.badge(r['status'])} <span class='muted'>for {ui.esc(r['for_role'].replace('_', ' '))}{' (' + org.plant_name(r['for_plant']) + ')' if r['for_plant'] else ''}</span>")
            for h in r["history"]:
                st.caption(f"{h['who']}: {h['note']}")
    if not org.reviews(None):
        st.caption("No approvals yet.")

with tabs[2]:
    log = org.access_log()
    if log:
        st.dataframe(pd.DataFrame(log).assign(at=lambda d: pd.to_datetime(d["at"], unit="s").dt.strftime("%d %b %H:%M"))[["at", "user", "reason", "text"]], hide_index=True)
    else:
        st.caption("No blocked attempts.")
    st.caption("Plant managers are blocked in code, before the agent runs, when they ask about another plant or claim a different role.")

with tabs[3]:
    runs = db.q("SELECT id, agent, vendor, model, turns, seconds, input_tokens, output_tokens, replayed, status FROM runs ORDER BY id DESC LIMIT 200")
    if runs:
        df = pd.DataFrame(runs)
        st.caption(f"{len(df)} agent runs. Replayed runs reuse a recorded answer and cost nothing. Spend today: Rs {agentkit.spend_today_usd() * agentkit.inr_rate():,.0f}.")
        st.dataframe(df, hide_index=True)
        rid = st.selectbox("Open a run", df["id"], format_func=lambda i: f"#{i} {df.set_index('id').loc[i, 'agent']} {df.set_index('id').loc[i, 'vendor'] or ''}")
        for s in db.q("SELECT n, kind, name, input, output FROM steps WHERE run_id=? ORDER BY id", int(rid)):
            st.html(f'<div class="bubble steps"><span class="by">Turn {s["n"]}: {ui.esc(s["kind"])} {ui.esc(s["name"] or "")}</span>{ui.esc((s["input"] or "")[:600])}<br>{ui.esc((s["output"] or "")[:900])}</div>')
    else:
        st.caption("No agent runs yet.")
    st.markdown("""**How it works.** Eight agents, each limited to its own tools: an intake router, a document extractor, an independent reviewer, a questionnaire analyst,
an evidence evaluator, a vendor liaison that drafts emails, an RFx co-pilot and an analyst. Code does every calculation: unit and currency conversion, discounts,
landed cost, holding cost, ranking, approval routing and access checks. Nothing goes to a vendor without a person's approval.""")

with tabs[4]:
    r = cfg["approval_rules"]
    st.markdown(f"- {r['plant_limit_note']}\n- {r['cross_plant_rule']}\n- {r['min_valid_quotes_note']}")
    for t in cfg["group_terms"]:
        st.markdown(f"- Group terms: {names[t['vendor']]} gives {t['discount_pct']}% off {t['material'].lower()} above {t['min_annual_kg']:,} kg a year, {t['scope'].lower()}.")
    st.markdown("- Priorities per line default from the item master and the RFx conversation. Plant managers can change a line's priority on the Compare page.")
    st.divider()
    st.subheader("Reset the demo")
    st.caption("Clears the RFx, mailboxes, decisions and approvals. Recorded answers stay.")
    if st.button("Reset", icon=":material/restart_alt:"):
        if sum(m["busy"] for m in db.mailboxes()) == 0:
            db.reset()
            org.reset()
            user = st.session_state.user
            st.session_state.clear()
            st.session_state.user = user
            st.rerun()
        else:
            st.warning("Agents are still working. Try again in a moment.")
