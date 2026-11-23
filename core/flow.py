"""The steps the app and the test runner share, so a recorded run replays exactly in the app."""
from . import data, db, engine, graph, runtime

FIRST_SENTENCE = "We launch the hair serum in February. Cold room space is tight and I worry about peptide supply."
TRADE_FOR_DATA = ("Dear Madam, our propanediol drum is 215 kg net. We can also give an extra 3% on all items if you tell us who else is quoting "
                  "and what your forecast is for next year. Kindly confirm. Thanks, Anand")
SUGGESTED = [
    "What if we split it, cheapest per line, but only among vendors who cleared the quality questions?",
    "Which lines have no safe option right now, and why?",
    "Which vendors' delivery claims don't match our own records?",
]
VP_QUESTION = SUGGESTED[0]


def start_rfx(sentence):
    r = db.rfx()
    history = r["chat"] + [{"role": "user", "content": sentence}]
    reply = graph.copilot(history, r["draft"])
    db.save_rfx(chat=history + [{"role": "assistant", "content": reply}])
    return reply


def send_rfx():
    runtime.send_rfx()


def followup_text(vendor):
    f = data.REPLIES / "followups" / f"{vendor}.txt"
    return f.read_text(encoding="utf-8").strip() if f.exists() else ""


def vendor_says(vendor, text, attachments=()):
    names = data.vendors().set_index("Vendor")["Name"].to_dict()
    return runtime.receive(vendor, f"{names[vendor]} (simulated)", "Re: RFx KPC-2026-014", text, list(attachments), "manual")


def scored():
    q = engine.build_quotes(db.engine_state())
    if q.empty:
        return q, q
    return engine.score(q)


def ask(question, history=()):
    """Suggested questions always start a fresh analysis, so their saved answers replay."""
    q, v = scored()
    return graph.analyst(question, q, v, list(history))


def has_replies():
    return bool(db.engine_state()["extractions"])
