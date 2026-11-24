import streamlit as st

from core import org, ui

u = st.session_state.user
names = ui.names()
role = u["role"]
rules = org.config()["approval_rules"]


def rs(x):
    return f"Rs {x:,.0f}"


def short_why(text):
    import re
    m = re.search(r"MOQ is ([\d,]+) kg against ([\d,]+) kg", text or "")
    if m:
        return f"Slightly dearer, but a smaller minimum order ({m.group(1)} kg against {m.group(2)} kg), so less stock to hold."
    return text


def vname(v):
    return names[v].split()[0]


def steps(done, labels):
    """A small progress line: Sent > Review > Approved."""
    out = []
    for i, lab in enumerate(labels):
        state = "done" if i < done else "now" if i == done else ""
        out.append(f'<span class="step {state}"><i>{"✓" if i < done else i + 1}</i>{ui.esc(lab)}</span>')
    st.html('<div class="steps">' + '<span class="bar"></span>'.join(out) + "</div>")


# ------------------------------------------------------------------ plant manager
def my_award():
    plant = u["plant"]
    awards = org.awards(plant)
    decs = org.decisions([plant])
    if not awards:
        if decs:   # Chennai: decided earlier, locally
            with st.container(border=True):
                st.html(f"<b>{org.plant_name(plant)}'s decisions</b>")
                for d in decs:
                    st.html(f'{ui.vendor_cell(d["vendor"])} for {ui.esc(d["material"])} · {ui.badge(d["status"], "good" if "Approved" in d["status"] else "warn")}')
            return
        st.info("You haven't sent an award yet. Pick an option on Compare and ask, then send it.", icon=":material/info:")
        st.page_link("screens/compare.py", label="Go to Compare and ask", icon=":material/table_chart:")
        return
    a = awards[0]
    waiting = [d for d in decs if "Waiting" in d["status"]]
    approved = all("Approved" in d["status"] for d in decs) and "Approved" in a["status"]
    with st.container(border=True):
        st.html(f'<div class="rev-head"><b>Your award: {ui.esc(a["option"])}</b><span>{ui.lakh(a["total"])}</span></div>')
        steps(3 if approved else 1, ["Sent", "Category manager review", "Approved"])
        if not approved:
            reasons = []
            if a["total"] > rules["plant_limit_inr"]:
                reasons.append(f"The total is above your {ui.lakh(rules['plant_limit_inr'])} limit.")
            group = [d for d in waiting if any(r["kind"] == "cross_plant" and r["payload"]["rm_code"] == d["rm_code"] for r in org.reviews(None) if r["status"] != "approved")]
            for d in group:
                reasons.append(f"{d['material'].split(' (')[0]}: another plant buys it from a different vendor, so the category manager looks at both.")
            if reasons:
                st.html("<b>Why it needs the category manager</b><ul class='tight'>" + "".join(f"<li>{ui.esc(x)}</li>" for x in reasons) + "</ul>")
        for d in decs:
            if "re-quote" in d["status"]:
                st.html(f'<div class="bubble note">{ui.esc(d["material"].split(" (")[0])}: approved, with a re-quote planned at combined volume once you can switch.</div>')
        with st.expander(f"Lines ({len(decs)})"):
            ui.table(["Line", "Vendor", "Price/kg", "Status"], [[ui.esc(d["material"]), ui.vendor_cell(d["vendor"]), f"Rs {d['price']:,.2f}",
                     ui.badge("Approved" if "Approved" in d["status"] else "Waiting", "good" if "Approved" in d["status"] else "warn")] for d in decs])
        with st.expander("Approval note"):
            st.text(a["note"])


def group_request(r):
    p = r["payload"]
    with st.container(border=True):
        st.html(f'<b>The category manager asks: can you move {ui.esc(p["material"].split(" (")[0].lower())} from {vname(p["from_vendor"])} to {vname(p["to_vendor"])}?</b>')
        if p.get("group_saving"):
            st.html(f'<div class="save-box">Saves the company about <b>{rs(p["group_saving"])} a year</b>. {"Your plant also saves" if p["own_effect"] >= 0 else "Your plant pays"} {rs(abs(p["own_effect"]))} a year{" more" if p["own_effect"] < 0 else ""}, '
                    f'but the minimum order rises from {p["moq_now"]:,.0f} kg to {p["moq_alt"]:,.0f} kg.</div>')
        row = st.container(horizontal=True)
        if row.button("Yes, move", key=f"y{r['id']}", type="primary", icon=":material/check:"):
            org.plant_reply(r["id"], u, True, "")
            st.toast("Sent to the category manager.")
            st.rerun()
        with row.popover("No, and here's why", icon=":material/close:"):
            why = st.text_area("Reason", key=f"why{r['id']}", placeholder="For example: we don't want to switch during the launch", label_visibility="collapsed")
            if st.button("Send", key=f"no{r['id']}", type="primary"):
                if why.strip():
                    org.plant_reply(r["id"], u, False, why.strip())
                    st.toast("Sent to the category manager.")
                    st.rerun()
                else:
                    st.warning("Add a reason first.")


# ------------------------------------------------------------------ category manager
def cross_plant(r):
    p = r["payload"]
    a, b, s = p["a"], p["b"], p["saving"]
    mat = p["material"].split(" (")[0]
    with st.container(border=True):
        st.html(f"<b>{ui.esc(mat)}: the two plants chose different vendors</b>")
        c1, c2 = st.columns(2)
        for col, d in ((c1, a), (c2, b)):
            col.html(f'<div class="side"><span class="muted">{ui.esc(org.plant_name(d["plant"]))}</span><b>{ui.esc(vname(d["vendor"]))} · Rs {d["price"]:,.2f}/kg</b>'
                     f'<small>{ui.esc(short_why(d["reason"]))}</small></div>')
        if s:
            st.html(f'<div class="save-box">Together they buy {s["combined_kg"]:,.0f} kg a year, enough for {vname(b["vendor"])}\'s {s["term"]["discount_pct"]}% group discount. '
                    f'If {org.plant_name(a["plant"])} moved too, the company saves about <b>{rs(s["net"])} a year</b>.</div>')
            with st.expander("How the saving is worked out"):
                st.write(f"- {org.plant_name(b['plant'])}: {s['term']['discount_pct']}% off {s['plant_b_kg']:,.0f} kg = {rs(s['plant_b_gain'])} a year")
                st.write(f"- {org.plant_name(a['plant'])}: pays {rs(s['plant_a_price_gain'])} less a year, but holds more stock "
                         f"(MOQ {s['moq_alt']:,.0f} kg against {s['moq_now']:,.0f} kg), costing {rs(s['plant_a_extra_holding'])} a year")
                st.write(f"- Source: {s['term']['source']}")
        rep = p.get("plant_reply")
        if r["status"] == "waiting_plant":
            st.html(f'<div class="bubble note">Waiting for {ui.esc(org.plant_name(a["plant"]))} to answer.</div>')
            return
        if rep:
            who = org.plant_name(a["plant"])
            st.html(f'<div class="bubble {"agent" if rep["accept"] else "vendor"}"><b>{ui.esc(who)}:</b> {"Agreed to move." if rep["accept"] else ui.esc(rep["reason"])}</div>')
            st.html(f'<div class="bubble agent"><b>Suggested:</b> {ui.esc(p["suggestion"])}</div>')
            row = st.container(horizontal=True)
            if row.button("Approve as suggested", key=f"sug{r['id']}", type="primary", icon=":material/check:"):
                org.resolve_with_suggestion(r["id"], u)
                st.rerun()
            return
        if role not in ("category_manager", "admin"):
            return
        row = st.container(horizontal=True)
        if row.button("Approve both", key=f"both{r['id']}", type="primary", icon=":material/check:"):
            org.approve_both(r["id"], u)
            st.rerun()
        if s:
            with row.popover(f"Ask {org.plant_name(a['plant'])} to move", icon=":material/forward_to_inbox:"):
                note = st.text_area("Note", f"Can you move {mat.lower()} to {vname(b['vendor'])}? The group discount needs both plants.", key=f"n{r['id']}", label_visibility="collapsed")
                if st.button("Send", key=f"ask{r['id']}", type="primary"):
                    org.ask_plant(r["id"], u, note)
                    st.toast(f"Sent to {org.plant_name(a['plant'])}.")
                    st.rerun()


def over_limit(r):
    p = r["payload"]
    with st.container(border=True):
        st.html(f'<div class="rev-head"><b>Coimbatore award, above the plant limit</b><span>{ui.lakh(p["total"])}</span></div>')
        lines = [d for d in org.decisions() if d["award_id"] == p["award_id"]]
        by = {}
        for d in lines:
            by[vname(d["vendor"])] = by.get(vname(d["vendor"]), 0) + 1
        st.html(f'{len(lines)} lines to {len(by)} vendors: ' + ", ".join(f"{k} ({n})" for k, n in sorted(by.items(), key=lambda x: -x[1])) +
                f'<br><span class="muted">Plant managers approve up to {ui.lakh(rules["plant_limit_inr"])}.</span>')
        with st.expander("Approval note"):
            st.text(p["note"])
        if role in ("category_manager", "admin") and st.button("Approve", key=f"ol{r['id']}", type="primary", icon=":material/check:"):
            org.approve_review(r["id"], u, "Approved above the plant limit.")
            st.rerun()


def question(r):
    p = r["payload"]
    with st.container(border=True):
        st.html(f'<b>Question from the {ui.esc(p["from"])}</b><div class="bubble user">{ui.esc(p["text"])}</div>')
        ans = st.text_input("Reply", key=f"q{r['id']}", placeholder="Your reply")
        if st.button("Send reply", key=f"qs{r['id']}"):
            org.answer_question(r["id"], u, ans)
            st.rerun()


# ------------------------------------------------------------------ page
if role == "plant_manager":
    ui.header("Approvals", "Where your award stands")
    requests = [r for r in org.reviews_for(u) if r["kind"] == "group_request"]
    if requests:
        st.subheader("Needs your answer")
        for r in requests:
            group_request(r)
    my_award()
else:
    ui.header("Approvals", "Decisions waiting for you")
    waiting = sorted(org.reviews_for(u), key=lambda r: {"cross_plant": 0, "question": 1, "over_limit": 2}.get(r["kind"], 3))
    if not waiting and not org.reviews("waiting_plant"):
        st.success("Nothing is waiting for you.", icon=":material/done_all:")
    for r in waiting:
        {"cross_plant": cross_plant, "over_limit": over_limit, "question": question, "group_request": group_request}[r["kind"]](r)
    parked = org.reviews("waiting_plant")
    if parked:
        st.subheader("Waiting for a plant")
        for r in parked:
            cross_plant(r)

st.write("")
plants = org.visible_plants(u)
decs = org.decisions(plants)
if decs and role != "plant_manager":
    with st.expander(f"All decisions ({len(decs)})"):
        ui.table(["Plant", "Line", "Vendor", "Price/kg", "Status"], [[ui.esc(org.plant_name(d["plant"])), ui.esc(d["material"]), ui.vendor_cell(d["vendor"]), f"Rs {d['price']:,.2f}",
                 ui.badge("Approved" if "Approved" in d["status"] else "Waiting", "good" if "Approved" in d["status"] else "warn")] for d in decs])
done = [r for r in org.reviews("approved") + org.reviews("answered") if role != "plant_manager" or (r["for_role"] == "plant_manager" and r["for_plant"] == u["plant"])]
if done:
    with st.expander(f"History ({len(done)})"):
        for r in done:
            st.html(f"<b>{ui.esc(r['title'])}</b>" + "".join(f"<div class='hist'>{ui.esc(h['who'])}: {ui.esc(h['note'])}</div>" for h in r["history"]))
