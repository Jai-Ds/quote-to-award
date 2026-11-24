import pandas as pd
import streamlit as st

from core import agentkit, db, flow, org, ui

u = st.session_state.user
names = ui.names()

# ------------------------------------------------------------------ Chennai: finished earlier, shown as records
if u["plant"] == "MAA":
    cfg = org.config()
    ui.header("Compare", "Chennai's quotes and what was chosen")
    qs = pd.DataFrame(cfg["chennai"]["quotes"])
    dec = {d["rm_code"]: d for d in org.decisions(["MAA"])}
    for code, g in qs.groupby("rm_code", sort=False):
        d = dec.get(code)
        low = g["landed_inr_per_kg"].min()
        rows = [[ui.vendor_cell(r["vendor"]), f"Rs {r['landed_inr_per_kg']:,.2f}" + (' <span class="l1">L1</span>' if r["landed_inr_per_kg"] == low else ""),
                 f"{r['moq_kg']:,.0f} kg", ui.esc(r["note"]), ui.badge("Chosen", "good") if d and d["vendor"] == r["vendor"] else ""] for _, r in g.iterrows()]
        with st.container(border=True):
            st.markdown(f"**{g['material'].iloc[0]}**")
            ui.table(["Vendor", "Landed price", "MOQ", "Note", ""], rows)
            if d:
                st.caption(f"Why: {d['reason']}")
    st.caption("Chennai's RFx finished earlier, so its quotes are shown as records.")
    st.stop()

# ------------------------------------------------------------------ Coimbatore, live
ui.header("Compare and ask", "Who gets each line, and why")
if not flow.has_replies():
    st.info("Quotes appear here once vendors reply.", icon=":material/hourglass_empty:")
    st.page_link("screens/inbox.py", label="Go to the inbox", icon=":material/inbox:")
    st.stop()

q, v = flow.scored()
opts = org.options(q)
if "option" not in st.session_state:
    st.session_state.option = "Recommended"
if "next_option" in st.session_state:      # set by the chat; applied before the option control is drawn
    st.session_state.option = st.session_state.pop("next_option")
st.session_state.setdefault("chat", [])

# One short chip per cell. Every reason sits in the tooltip, so the table stays readable.
FLAG = {"NEED_DENSITY": ("Needs density", "warn"), "NEED_NET_WEIGHT": ("Needs pack weight", "warn"), "NEED_STRENGTH": ("Needs strength", "warn"),
        "MARKER_MISMATCH": ("Different test", "warn"), "LATE": ("Late", "bad"), "SHELF_FAIL": ("Short shelf life", "bad"), "COA_EXPIRED": ("Certificate expired", "bad")}
RANK = {"bad": 0, "warn": 1, "info": 2}


def chips(r):
    out = [FLAG[i["code"]] for i in r["issues"] or [] if i["code"] in FLAG]
    if r.get("claim_status") == "Contradicts" and r.get("otif") == r.get("otif"):
        out.append((f"Claims {r['otif_claim_pct']:g}%, we saw {r['otif']:.0%}", "bad"))
    if r.get("knockouts"):
        out.append(("Failed quality check", "bad"))
    tips = [i["text"] for i in r["issues"] or [] if i["level"] in ("block", "warn")] + ([f"Failed: {', '.join(r['knockouts'])}"] if r.get("knockouts") else [])
    return sorted(dict.fromkeys(out), key=lambda x: RANK[x[1]]), tips


def cell(r, chosen, low):
    if r is None:
        return '<td class="dim">-</td>'
    if r.get("not_quoted") == True:  # noqa: E712
        return '<td class="dim">Declined</td>'
    cs, tips = chips(r)
    tip = ui.esc(" · ".join(tips)) if tips else ""
    chip = f'<span class="flag {cs[0][1]}">{ui.esc(cs[0][0])}{f" +{len(cs) - 1}" if len(cs) > 1 else ""}</span>' if cs else ""
    if not r["comparable"]:
        return f'<td title="{tip}"><span class="muted">No price yet</span>{chip}</td>'
    c = r["cost_inr_per_spec_kg"]
    price = f'<span class="p">{c:,.1f}</span>' if c < 1000 else f'<span class="p">{c:,.0f}</span>'
    price += ('<span class="l1">L1</span>' if abs(r["cost_inr_per_spec_kg"] - low) < 1e-6 else "")
    return f'<td class="{"sel" if chosen else ""}" title="{tip}">{price}{chip}</td>'


def short_reason(why):
    if not isinstance(why, str):
        return ""
    if "MOQ" in why:
        return "Not the cheapest: smaller MOQ, less stock to hold"
    if "dearer" in why:
        return "Not the cheapest: better on your priorities"
    if "No vendor" in why:
        return "No vendor qualifies yet"
    return ""


ask_col, table_col = st.columns([1, 2.3], gap="medium")

# ------------------------------------------------------------------ the table
with table_col:
    labels = {k: f"{k} · {ui.lakh(df['spend'].sum())}" for k, df in opts.items()}
    pick = st.segmented_control("Option", list(opts), key="option", format_func=lambda k: labels[k], label_visibility="collapsed") or "Recommended"
    plan = opts[pick].set_index("rm_code")
    vendors = [x for x in db.VENDORS if x in set(q["vendor"])]
    head = "<th>Line</th>" + "".join(f"<th>{ui.vendor_cell(x)}</th>" for x in vendors)
    body = []
    for code, g in q.groupby("rm_code"):
        comp = g[g["comparable"] == True]  # noqa: E712
        low = comp["cost_inr_per_spec_kg"].min() if len(comp) else None
        chosen = plan.loc[code, "vendor"] if code in plan.index else None
        why = short_reason(plan.loc[code, "why"] if code in plan.index else None)
        if isinstance(chosen, str) and len(comp) and not why:
            l1 = comp.sort_values("cost_inr_per_spec_kg").iloc[0]
            if l1["vendor"] != chosen:
                why = "Not the cheapest: the cheaper vendor failed the quality check" if l1["knockouts"] else "Not the cheapest: better on your priorities"
        tds = "".join(cell(g[g["vendor"] == x].iloc[0].to_dict() if (g["vendor"] == x).any() else None, x == chosen, low) for x in vendors)
        body.append(f'<tr><td class="mat">{ui.esc(g["material"].iloc[0])}{f"<small>{ui.esc(why)}</small>" if why else ""}</td>{tds}</tr>')
    st.html(f'<div class="cmp-wrap"><table class="cmp"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')
    st.html('<div class="legend"><span class="sw sel"></span>Chosen in this option <span class="l1">L1</span> Lowest price · Rs per kg, landed · Hover a cell for details</div>')

    tools = st.container(horizontal=True)
    with tools.popover("How a price was built", icon=":material/calculate:"):
        valid = q[(q["not_quoted"] != True)]  # noqa: E712
        key = st.selectbox("Line and vendor", [f"{r['material']} · {ui.short(r['vendor'])}" for _, r in valid.iterrows()], label_visibility="collapsed")
        mat, vs = key.split(" · ")
        r = valid[(valid["material"] == mat) & (valid["vendor"].map(ui.short) == vs)].iloc[0]
        for t in r["trail"] or ["No price could be worked out yet."]:
            st.write(t)
        if r.get("source_quote") == r.get("source_quote") and r.get("source_quote"):
            st.caption(f'Source, {r["source_file"]}: "{r["source_quote"]}"')
    with tools.popover("Priorities", icon=":material/tune:"):
        st.caption("Set from your RFx. Change a line only if it's wrong.")
        tags = db.item_tags()
        choices = list(db.latest_templates())
        for code, mat in q.groupby("rm_code")["material"].first().items():
            new = st.selectbox(mat, choices, index=choices.index(tags[code]), key=f"tag{code}")
            if new != tags[code]:
                db.set_item_tag(code, new)
                st.rerun()

    st.write("")
    mine = org.awards("CBE")
    if mine:
        a = mine[0]
        with st.container(border=True):
            c1, c2 = st.columns([3, 1], vertical_alignment="center")
            c1.html(f'<b>Sent for approval:</b> {ui.esc(a["option"])}, {ui.lakh(a["total"])} · {ui.badge(a["status"], "good" if "Approved" in a["status"] else "warn")}')
            c2.page_link("screens/approvals.py", label="Track it", icon=":material/arrow_forward:")
    elif u["role"] == "plant_manager":
        if st.button(f"Send {pick} for approval · {ui.lakh(opts[pick]['spend'].sum())}", type="primary", icon=":material/send:", width="stretch"):
            org.submit_award(u, pick, opts[pick], q)
            st.switch_page("screens/approvals.py")

# ------------------------------------------------------------------ chat that steers the table
CHIPS = {"Cheapest per line, quality-cleared only": flow.SUGGESTED[0], "Lines with no safe option": flow.SUGGESTED[1], "Claims that don't match our records": flow.SUGGESTED[2]}

with ask_col, st.container(border=True):
    st.html('<b>Ask about these quotes</b>')
    asked = None
    if not st.session_state.chat:
        st.caption("Try one:")
        for label, full in CHIPS.items():
            if st.button(label, key=f"chip{label}", width="stretch"):
                asked = (full, True)
    for i, m in enumerate(st.session_state.chat):
        if m["role"] == "user":
            st.html(f'<div class="bubble user">{ui.esc(m["text"])}</div>')
        elif m["role"] == "blocked":
            st.html(f'<div class="bubble blocked">{ui.esc(m["text"])}</div>')
            if m.get("forward") and st.button("Send to the category manager", key=f"fw{i}", icon=":material/forward_to_inbox:"):
                org.forward_question(u, m["q"])
                m["forward"] = False
                st.toast("Sent to the category manager.")
        elif m["role"] == "note":
            st.html(f'<div class="bubble note">{ui.esc(m["text"])}</div>')
        else:
            st.html(f'<div class="bubble agent">{ui.esc(m["text"])}</div>')
            t = m.get("table")
            if isinstance(t, pd.DataFrame) and len(t):
                with st.expander("See the numbers"):
                    st.dataframe(ui.readable(t), hide_index=True)
    left = [(lab, full) for lab, full in CHIPS.items() if not any(m.get("q") == full or m.get("text") == full for m in st.session_state.chat)]
    if st.session_state.chat and left:
        st.caption("More questions:")
        for label, full in left:
            if st.button(label, key=f"more{label}", width="stretch", icon=":material/chat_bubble:"):
                asked = (full, True)
    typed = st.chat_input("Ask a question")
    if typed:
        asked = (typed.strip(), False)
    if asked:
        text, suggested = asked
        st.session_state.chat.append({"role": "user", "text": text})
        g = org.guard(u, text)
        if g:
            st.session_state.chat.append({"role": "blocked", "text": g["text"], "forward": g["kind"] == "other_plant", "q": text})
        else:
            with st.spinner("Working it out"):
                try:
                    hist = [] if suggested else [{"q": m["q"], "a": m["text"]} for m in st.session_state.chat if m["role"] == "agent"][-3:]
                    out = flow.ask(text, hist)
                    st.session_state.chat.append({"role": "agent", "text": out["answer"], "q": text, "table": out.get("result")})
                    if text == flow.VP_QUESTION:
                        st.session_state.next_option = "Quality-cleared split"
                        st.session_state.chat.append({"role": "note", "text": "The table now shows this option."})
                except agentkit.LiveOff:
                    st.session_state.chat.append({"role": "note", "text": "No recorded answer for this, and live AI is off here. Try one of the suggested questions."})
                except Exception as e:
                    st.session_state.chat.append({"role": "note", "text": f"Couldn't answer that: {str(e)[:160]}"})
        st.rerun()
