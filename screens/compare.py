import pandas as pd
import streamlit as st

from core import agentkit, data, db, flow, org, ui

u = st.session_state.user
names = ui.names()

# ------------------------------------------------------------------ Chennai: finished earlier, shown as records
if u["plant"] == "MAA":
    cfg = org.config()
    ui.header("Compare", "Chennai's quotes and decisions")
    st.caption(f"Chennai's RFx ({cfg['plants']['MAA']['rfx']}). {cfg['plants']['MAA']['buys_on']}.")
    qs = pd.DataFrame(cfg["chennai"]["quotes"])
    dec = {d["rm_code"]: d for d in org.decisions(["MAA"])}
    rows = []
    for code, g in qs.groupby("rm_code", sort=False):
        low = g["landed_inr_per_kg"].min()
        for _, r in g.iterrows():
            chosen = dec.get(code, {}).get("vendor") == r["vendor"]
            rows.append([f"<b>{ui.esc(r['material'])}</b>", ui.vendor_cell(r["vendor"]), f"Rs {r['landed_inr_per_kg']:,.2f}" + (' <span class="badge good"><i></i>L1</span>' if r["landed_inr_per_kg"] == low else ""),
                         f"{r['moq_kg']:,.0f} kg", ui.esc(r["note"]), ui.badge("Chosen", "good") if chosen else ""])
    ui.table(["Line", "Vendor", "Landed price", "MOQ", "Note", ""], rows)
    st.subheader("Decisions")
    for d in org.decisions(["MAA"]):
        st.html(f'<div class="rev"><b>{ui.esc(d["material"])}: {ui.esc(names[d["vendor"]])}</b> at Rs {d["price"]:,.2f}/kg, {d["annual_kg"]:,.0f} kg a year<br>'
                f'<span class="muted">{ui.esc(d["reason"])}</span><br>{ui.badge(d["status"], "good" if "Approved" in d["status"] else "warn")}</div>')
    st.caption("Chat runs on the Coimbatore RFx in this demo. Chennai's quotes were processed earlier and are shown as finished records.")
    st.stop()

# ------------------------------------------------------------------ Coimbatore, live
ui.header("Compare and ask", "Which vendor gets each line, and why?")
if not flow.has_replies():
    st.info("This fills in as soon as the first vendor reply has been read.", icon=":material/hourglass_empty:")
    st.page_link("screens/inbox.py", label="Open the inbox", icon=":material/inbox:")
    st.stop()

q, v = flow.scored()
opts = org.options(q)
if "option" not in st.session_state:
    st.session_state.option = "Recommended"
if "next_option" in st.session_state:      # set by the chat; applied before the option control is drawn
    st.session_state.option = st.session_state.pop("next_option")
if "chat" not in st.session_state:
    st.session_state.chat = []

FLAG_TEXT = {"NEED_DENSITY": ("Waiting for density", "warn"), "NEED_NET_WEIGHT": ("Waiting for pack weight", "warn"), "NEED_STRENGTH": ("Waiting for strength", "warn"),
             "MARKER_MISMATCH": ("Different strength test", "warn"), "CONDITIONAL_OFFER": ("Conditional offer not counted", "info"), "LATE": ("Arrives late", "bad"),
             "SHELF_FAIL": ("Shelf life too short", "bad"), "COA_EXPIRED": ("Certificate expired", "bad"), "WITHHELD": ("Won't share records", "warn")}


def flags(r):
    out = []
    for i in r["issues"] or []:
        if i["code"] in FLAG_TEXT:
            out.append(FLAG_TEXT[i["code"]])
    if r.get("claim_status") == "Contradicts" and r.get("otif") == r.get("otif"):
        out.append((f"Says {r['otif_claim_pct']:g}% on time, we saw {r['otif']:.0%}", "bad"))
    if r.get("knockouts"):
        out.append(("Failed: " + ", ".join(r["knockouts"]), "bad"))
    return list(dict.fromkeys(out))


def cell(r, chosen, low):
    if r is None:
        return '<td class="dim">-</td>'
    if r.get("not_quoted") == True:  # noqa: E712
        return '<td class="dim">Declined</td>'
    fl = "".join(f'<span class="flag {t}">{ui.esc(x)}</span>' for x, t in flags(r))
    if not r["comparable"]:
        return f'<td><span class="muted">Not comparable yet</span>{fl}</td>'
    price = f'<span class="p">Rs {r["cost_inr_per_spec_kg"]:,.2f}</span>' + ('<span class="l1">L1</span>' if abs(r["cost_inr_per_spec_kg"] - low) < 1e-6 else "")
    return f'<td class="{"sel" if chosen else ""}">{price}{fl}</td>'


main, side = st.columns([2.15, 1], gap="medium")

with main:
    pick = st.segmented_control("Option", list(opts), key="option", label_visibility="collapsed")
    pick = pick or "Recommended"
    plan = opts[pick].set_index("rm_code")
    total = plan["spend"].sum()
    st.html(f'<div class="opt-total">{ui.esc(org.OPTION_HELP[pick])} Total for the 6-month need: <b>{ui.lakh(total)}</b>, {plan["vendor"].notna().sum()} of {len(plan)} lines awarded.</div>')
    vendors = [x for x in db.VENDORS if x in set(q["vendor"])]
    head = "<th>Line</th>" + "".join(f"<th>{ui.vendor_cell(x)}</th>" for x in vendors)
    body = []
    for code, g in q.groupby("rm_code"):
        comp = g[g["comparable"] == True]  # noqa: E712
        low = comp["cost_inr_per_spec_kg"].min() if len(comp) else None
        chosen = plan.loc[code, "vendor"] if code in plan.index else None
        mat = g["material"].iloc[0]
        why = plan.loc[code, "why"] if code in plan.index else ""
        tds = "".join(cell(g[g["vendor"] == x].iloc[0].to_dict() if (g["vendor"] == x).any() else None, x == chosen, low) for x in vendors)
        body.append(f'<tr><td class="mat">{ui.esc(mat)}<small>{ui.esc(why)}</small></td>{tds}</tr>')
    st.html(f'<div class="cmp-wrap"><table class="cmp"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')
    tags = db.item_tags()
    counts = pd.Series(tags).value_counts()
    st.html(f'<div class="prio">Landed rupees per kg at our spec strength. Priorities per line come from your RFx and plant policy: '
            f'{", ".join(f"{n} line(s) {t.lower()}" for t, n in counts.items())}. The peptides are reliability first because you flagged peptide supply.</div>')

    c1, c2 = st.columns(2)
    with c1.popover("Explain a price", icon=":material/help:", width="stretch"):
        valid = q[q["not_quoted"] != True]  # noqa: E712
        key = st.selectbox("Line and vendor", [f"{r['material']} | {ui.short(r['vendor'])}" for _, r in valid.iterrows()])
        mat, vs = key.split(" | ")
        r = valid[(valid["material"] == mat) & (valid["vendor"].map(ui.short) == vs)].iloc[0]
        if r.get("source_quote") == r.get("source_quote") and r.get("source_quote"):
            st.caption(f'{r["source_file"]}: "{r["source_quote"]}"')
        for t in r["trail"] or ["No conversion was possible yet."]:
            st.write(t)
        for i in r["issues"]:
            if i["level"] in ("block", "warn"):
                st.caption(i["text"])
    with c2.popover("Change priorities", icon=":material/tune:", width="stretch"):
        st.caption("Only change these if the defaults are wrong for a line.")
        choices = list(db.latest_templates())
        for code, mat in q.groupby("rm_code")["material"].first().items():
            new = st.selectbox(mat, choices, index=choices.index(tags[code]), key=f"tag{code}")
            if new != tags[code]:
                db.set_item_tag(code, new)
                st.rerun()

    st.divider()
    mine = org.awards("CBE")
    if mine:
        a = mine[0]
        st.html(f'<div class="rev"><b>Sent for approval: {ui.esc(a["option"])}</b>, {ui.lakh(a["total"])}. {ui.badge(a["status"], "good" if "Approved" in a["status"] else "warn")}<br>'
                f'<span class="muted">Track it on the Approvals page.</span></div>')
    if st.button(f"Send \"{pick}\" for approval", type="primary", icon=":material/task_alt:", disabled=u["role"] != "plant_manager"):
        res = org.submit_award(u, pick, opts[pick], q)
        st.session_state.last_submit = res
        st.rerun()
    if u["role"] != "plant_manager":
        st.caption("Only the plant manager can send an award.")
    res = st.session_state.get("last_submit")
    if res:
        msg = "Within your approval limit, so these lines are approved." if res["within_limit"] else "Above your limit, so it went to the category manager."
        if res["conflicts"]:
            msg += f" {len(res['conflicts'])} line(s) also involve another plant's decision, so those went to the category manager."
        st.success(msg, icon=":material/route:")
        with st.expander("Approval note, drafted for you"):
            st.text(res["note"])

# ------------------------------------------------------------------ chat that steers the table
with side, st.container(border=True):
    st.html('<b>Ask</b><br><span class="muted">Answers come from analysis of the quotes above.</span>')
    asked = None
    for i, s in enumerate(flow.SUGGESTED):
        if st.button(s, key=f"s{i}", width="stretch", type="tertiary", icon=":material/chat_bubble:"):
            asked = (s, True)
    typed = st.chat_input("Ask about these quotes")
    if typed:
        asked = (typed.strip(), False)
    if asked:
        text, suggested = asked
        st.session_state.chat.append({"role": "user", "text": text})
        g = org.guard(u, text)
        if g:
            st.session_state.chat.append({"role": "blocked", "text": g["text"], "forward": g["kind"] == "other_plant", "q": text})
        else:
            with st.spinner("Analysing"):
                try:
                    hist = [] if suggested else [{"q": m["q"], "a": m["text"]} for m in st.session_state.chat if m["role"] == "agent"][-3:]
                    out = flow.ask(text, hist)
                    st.session_state.chat.append({"role": "agent", "text": out["answer"], "q": text, "table": out.get("result"), "cards": out.get("cards"), "code": out.get("code")})
                    if text == flow.VP_QUESTION:
                        st.session_state.next_option = "Quality-cleared split"
                        st.session_state.chat.append({"role": "note", "text": "Saved as an option: Quality-cleared split. The table now shows it."})
                except agentkit.LiveOff as e:
                    st.session_state.chat.append({"role": "note", "text": str(e)})
                except Exception as e:
                    st.session_state.chat.append({"role": "note", "text": f"The analyst couldn't answer: {str(e)[:200]}"})
        st.rerun()
    for i, m in enumerate(st.session_state.chat):
        if m["role"] == "user":
            st.html(f'<div class="bubble user">{ui.esc(m["text"])}</div>')
        elif m["role"] == "blocked":
            st.html(f'<div class="bubble blocked"><span class="by">Access check</span>{ui.esc(m["text"])}</div>')
            if m.get("forward") and st.button("Send to the category manager", key=f"fw{i}", icon=":material/forward_to_inbox:"):
                org.forward_question(u, m["q"])
                m["forward"] = False
                st.toast("Sent to the category manager.")
        elif m["role"] == "note":
            st.caption(m["text"])
        else:
            st.html(f'<div class="bubble agent"><span class="by">Analyst</span>{ui.esc(m["text"])}</div>')
            if m.get("cards"):
                st.html("".join(f'<div class="mini"><span>{ui.esc(c["label"])}</span><b>{ui.esc(c["value"])}</b></div>' for c in m["cards"]))
            t = m.get("table")
            if isinstance(t, pd.DataFrame) and len(t):
                st.dataframe(ui.colored(ui.readable(t)), hide_index=True, height=min(38 * (len(t) + 1), 320))
            if m.get("code"):
                with st.expander("Code the agent ran"):
                    st.code(m["code"], language="python")
