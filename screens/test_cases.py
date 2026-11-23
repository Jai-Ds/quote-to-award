import json
from pathlib import Path

import streamlit as st

from core import ui

ui.header("Test cases", "Six hard situations, and how the system handled each one")
files = sorted((Path(__file__).resolve().parents[1] / "cases").glob("case_*.json"), key=lambda p: int(p.stem.split("_")[1]))
cases = [json.loads(f.read_text(encoding="utf-8")) for f in files]
if not cases:
    st.info("No recorded cases yet. Run tools/run_cases.py.")
    st.stop()
passed = sum(c["passed"] for c in cases)
checks = sum(len(c["checks"]) for c in cases)
ok = sum(x["passed"] for c in cases for x in c["checks"])
st.html(f'<div class="insight"><div><b>{passed} of {len(cases)} cases pass, and {ok} of {checks} checks.</b> Each case is a recorded run of the real agents and rules, '
        f'made by <code>tools/run_cases.py</code>. The checks are code, not opinions.</div></div>')

for c in cases:
    with st.expander(f"{'Pass' if c['passed'] else 'Fail'} · Case {c['id']}: {c['title']}", expanded=c["id"] == cases[0]["id"]):
        st.caption(f"Shown as: {c['role']}. {c['why']}")
        chat, res = st.columns([1.7, 1], gap="medium")
        with chat:
            for m in c["chat"]:
                extra = ""
                if m.get("detail"):
                    extra = "<ul>" + "".join(f"<li>{ui.esc(d)}</li>" for d in m["detail"][:14]) + "</ul>"
                kind = m["kind"]
                if kind == "agent" and m["who"] == "System" and ("don't have access" in m["text"] or "set by your login" in m["text"]):
                    kind = "blocked"
                st.html(f'<div class="bubble {kind}"><span class="by">{ui.esc(m["who"])}</span>{ui.esc(m["text"])}{extra}</div>')
        with res:
            st.html("<b>Checks</b>")
            for x in c["checks"]:
                detail = f"<small>{ui.esc(str(x['detail'])[:220])}</small>" if x.get("detail") else ""
                mark = "✓" if x["passed"] else "✗"
                st.html(f'<div class="check {"ok" if x["passed"] else "no"}"><i>{mark}</i><div>{ui.esc(x["rule"])}{detail}</div></div>')
