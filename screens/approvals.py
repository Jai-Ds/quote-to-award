import streamlit as st

from core import org, ui

u = st.session_state.user
names = ui.names()
role = u["role"]
ui.header("Approvals", "What is waiting for my decision?")


def rs(x):
    return f"Rs {x:,.0f}"


def history(r):
    if r["history"]:
        st.html('<div class="hist">' + "<br>".join(f"{ui.esc(h['who'])}: {ui.esc(h['note'])}" for h in r["history"]) + "</div>")


def cross_plant(r):
    p = r["payload"]
    a, b, s = p["a"], p["b"], p["saving"]
    st.html(f'<h3>{ui.esc(r["title"])}</h3><span class="muted">Both plants chose for their own reasons. Neither could see the other\'s decision.</span>')
    c1, c2 = st.columns(2)
    for col, d in ((c1, a), (c2, b)):
        col.html(f'<div class="side"><span class="muted">{ui.esc(org.plant_name(d["plant"]))} chose</span><b>{ui.esc(names[d["vendor"]])}</b>'
                 f'Rs {d["price"]:,.2f}/kg, {d["annual_kg"]:,.0f} kg a year<br><span class="muted">{ui.esc(d["reason"])}</span></div>')
    if s:
        st.html(f'<div class="save-box"><b>What neither plant could see.</b> {ui.esc(names[b["vendor"]].split()[0])} gives {s["term"]["discount_pct"]}% off above '
                f'{s["term"]["min_annual_kg"]:,} kg a year across all plants ({ui.esc(s["term"]["source"])}). Together the plants buy {s["combined_kg"]:,.0f} kg. '
                f'If {org.plant_name(a["plant"])} also moved: {org.plant_name(b["plant"])} saves {rs(s["plant_b_gain"])} a year, {org.plant_name(a["plant"])} saves {rs(s["plant_a_price_gain"])} on price '
                f'but holds more stock (MOQ {s["moq_alt"]:,.0f} kg against {s["moq_now"]:,.0f} kg, about {rs(s["plant_a_extra_holding"])} a year). '
                f'<b>Net for the group: about {rs(s["net"])} a year.</b></div>')
    else:
        st.caption("No group price terms apply to these two vendors, so this is a visibility check only.")
    history(r)
    rep = p.get("plant_reply")
    if role not in ("category_manager", "admin"):
        return
    if r["status"] == "waiting_plant":
        st.caption(f"Waiting for {org.plant_name(a['plant'])}'s answer.")
        return
    if rep:
        st.html(f'<div class="bubble {"agent" if rep["accept"] else "vendor"}"><span class="by">{ui.esc(rep["by"])}</span>{"Agreed to move." if rep["accept"] else ui.esc(rep["reason"])}</div>')
        st.html(f'<div class="bubble agent"><span class="by">Suggested</span>{ui.esc(p["suggestion"])}</div>')
        row = st.container(horizontal=True)
        if row.button("Approve as suggested", key=f"sug{r['id']}", type="primary", icon=":material/check:"):
            org.resolve_with_suggestion(r["id"], u)
            st.rerun()
        if row.button("Approve both as decided", key=f"both{r['id']}"):
            org.approve_both(r["id"], u)
            st.rerun()
        return
    row = st.container(horizontal=True)
    if row.button("Approve both as decided", key=f"both{r['id']}", type="primary", icon=":material/check:"):
        org.approve_both(r["id"], u)
        st.rerun()
    if s:
        with row.popover(f"Ask {org.plant_name(a['plant'])} to move", icon=":material/forward_to_inbox:"):
            note = st.text_area("Note", f"Can you move {p['material'].split(' (')[0].lower()} to {names[b['vendor']].split()[0]}? The group discount needs both plants.", key=f"n{r['id']}")
            if st.button("Send", key=f"ask{r['id']}", type="primary"):
                org.ask_plant(r["id"], u, note)
                st.rerun()


def group_request(r):
    p = r["payload"]
    st.html(f'<h3>{ui.esc(r["title"])}</h3><div class="bubble agent"><span class="by">Category manager</span>{ui.esc(p["note"])}</div>')
    if p.get("group_saving"):
        st.html(f'<div class="save-box">Moving to {ui.esc(names[p["to_vendor"]].split()[0])} at about Rs {p["alt_price"]:,.2f}/kg after the group discount would save the group about {rs(p["group_saving"])} a year. '
                f'For your plant: {rs(p["own_effect"])} a year after the extra holding cost, and the MOQ goes from {p["moq_now"]:,.0f} kg to {p["moq_alt"]:,.0f} kg.</div>')
    st.caption("You see the request and the saving. Other plants' prices and volumes stay with the category manager.")
    if role != "plant_manager":
        return
    row = st.container(horizontal=True)
    if row.button("Agree to move", key=f"y{r['id']}", type="primary", icon=":material/check:"):
        org.plant_reply(r["id"], u, True, "")
        st.rerun()
    with row.popover("Decline, with a reason", icon=":material/close:"):
        why = st.text_area("Reason", key=f"why{r['id']}", placeholder="Why this doesn't work for your plant right now")
        if st.button("Send", key=f"no{r['id']}"):
            if why.strip():
                org.plant_reply(r["id"], u, False, why.strip())
                st.rerun()
            else:
                st.warning("Add a reason first.")


def question(r):
    p = r["payload"]
    st.html(f'<h3>{ui.esc(r["title"])}</h3><div class="bubble user">{ui.esc(p["text"])}</div>')
    st.caption("Forwarded from chat, because the plant manager can't see this data.")
    if role in ("category_manager", "admin"):
        ans = st.text_input("Reply", key=f"q{r['id']}")
        if st.button("Send reply", key=f"qs{r['id']}"):
            org.answer_question(r["id"], u, ans)
            st.rerun()


def over_limit(r):
    p = r["payload"]
    st.html(f'<h3>{ui.esc(r["title"])}</h3>Total {ui.lakh(p["total"])}, above the plant limit of {ui.lakh(org.config()["approval_rules"]["plant_limit_inr"])}.')
    with st.expander("Approval note"):
        st.text(p["note"])
    if role in ("category_manager", "admin") and st.button("Approve", key=f"ol{r['id']}", type="primary"):
        org.approve_review(r["id"], u, "Approved above the plant limit.")
        st.rerun()


SHOW = {"cross_plant": cross_plant, "group_request": group_request, "question": question, "over_limit": over_limit}
mine = org.reviews_for(u)
waiting = [r for r in mine if r["kind"] != "cross_plant" or role != "plant_manager"]
if not waiting:
    st.info("Nothing is waiting for you.", icon=":material/done_all:")
for r in waiting:
    with st.container(border=True):
        SHOW[r["kind"]](r)

# ------------------------------------------------------------------ the decisions this person may see
st.divider()
plants = org.visible_plants(u)
st.subheader("Decisions" if role == "plant_manager" else "Decisions across plants")
rows = [[ui.esc(org.plant_name(d["plant"])), f"<b>{ui.esc(d['material'])}</b>", ui.vendor_cell(d["vendor"]), f"Rs {d['price']:,.2f}", f"{d['annual_kg']:,.0f} kg",
         ui.badge(d["status"], "good" if "Approved" in d["status"] else "warn")] for d in org.decisions(plants)]
if rows:
    ui.table(["Plant", "Line", "Vendor", "Price/kg", "Per year", "Status"], rows)
else:
    st.caption("No decisions yet.")
for a in [x for x in org.awards() if x["plant"] in plants]:
    with st.expander(f"{org.plant_name(a['plant'])} award: {a['option']}, Rs {a['total']:,.0f} ({a['status']})"):
        st.text(a["note"])
done = [r for r in org.reviews("approved") + org.reviews("answered") if role != "plant_manager" or (r["for_role"] == "plant_manager" and r["for_plant"] == u["plant"])]
if done:
    with st.expander(f"Closed items ({len(done)})"):
        for r in done:
            st.html(f"<b>{ui.esc(r['title'])}</b>")
            history(r)
