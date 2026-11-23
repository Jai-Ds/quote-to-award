"""Two plants, four roles, award options, approval routing and the cross-plant review.

Everything here is rules, not a model: who may see what, who must approve, and every rupee figure.
"""
import json
import re
import time
from functools import lru_cache
from pathlib import Path

import pandas as pd

from . import data, db

CONFIG = Path(__file__).resolve().parents[1] / "config" / "org.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY AUTOINCREMENT, plant TEXT, rm_code TEXT, material TEXT, vendor TEXT, price REAL, annual_kg REAL,
    reason TEXT, status TEXT, award_id INTEGER, at REAL);
CREATE TABLE IF NOT EXISTS awards(id INTEGER PRIMARY KEY AUTOINCREMENT, plant TEXT, option TEXT, total REAL, note TEXT, status TEXT, by_user TEXT, at REAL);
CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, title TEXT, payload TEXT, status TEXT, for_role TEXT, for_plant TEXT,
    history TEXT DEFAULT '[]', at REAL, decided_at REAL);
CREATE TABLE IF NOT EXISTS access_log(id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL, user TEXT, text TEXT, reason TEXT);
"""


@lru_cache(maxsize=1)
def config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def init():
    with db._write, db.conn() as c:
        c.executescript(SCHEMA)
    if not db.q("SELECT 1 FROM decisions WHERE plant='MAA'"):
        for d in config()["chennai"]["decisions"]:   # Chennai finished its RFx earlier and approved it locally
            db.x("INSERT INTO decisions(plant,rm_code,material,vendor,price,annual_kg,reason,status,award_id,at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                 "MAA", d["rm_code"], d["material"], d["vendor"], d["price_inr_per_kg"], d["annual_kg"], d["reason"], "Approved by Chennai plant manager", None, time.time())


init()


# ------------------------------------------------------------------ people
def users():
    return config()["users"]


def user(uid):
    return {"id": uid, **users()[uid]}


def plant_name(code):
    return config()["plants"][code]["name"] if code else "All plants"


def visible_plants(u):
    return [u["plant"]] if u["role"] == "plant_manager" else list(config()["plants"])


def vendor_names():
    return data.vendors().set_index("Vendor")["Name"].to_dict()


def short(v):
    return vendor_names().get(v, v).split()[0]


# ------------------------------------------------------------------ access, enforced in code
ROLE_CLAIM = re.compile(r"\b(i am|i'm|im|i’m|as)\s+(the\s+|a\s+|an\s+)?(category manager|admin|administrator|chennai|coimbatore|plant manager)\b|\b(grant|give|switch)\b.{0,30}\b(access|role|permission)", re.I)


def guard(u, text, last_blocked=False):
    """Returns None when the question may go to the agent, or a refusal written by code."""
    if u["role"] != "plant_manager":
        return None
    own = u["plant"]
    others = [c for c in config()["plants"] if c != own]
    low = text.lower()
    for c in others:
        name = plant_name(c)
        if re.search(rf"\b({re.escape(name.lower())}|{c.lower()})\b", low):
            log(u, text, f"Asked about {name}'s data")
            return {"kind": "other_plant", "plant": c,
                    "text": f"You don't have access to {name}'s decisions. You can ask about {plant_name(own)}'s quotes and decisions, or send this question to the category manager."}
    if ROLE_CLAIM.search(text):
        log(u, text, "Claimed a different role in chat")
        return {"kind": "role_claim", "text": "Access is set by your login, not by what's typed in chat, so I still can't show it. If you need wider access, ask an admin."}
    return None


def log(u, text, reason):
    db.x("INSERT INTO access_log(at,user,text,reason) VALUES(?,?,?,?)", time.time(), u["name"], text[:500], reason)


def access_log():
    return db.q("SELECT * FROM access_log ORDER BY id DESC")


def forward_question(u, text):
    return add_review("question", f"Question from the {u['name']}", {"from": u["name"], "text": text}, "category_manager", None)


# ------------------------------------------------------------------ award options for the live plant
LINE_COLS = ["rm_code", "material", "vendor", "price", "spend", "comparable_quotes", "why"]


def _pick(q, mask_fn, rank_col, label):
    rows = []
    for code, g in q.groupby("rm_code"):
        valid = g[(g["comparable"] == True)]  # noqa: E712
        pool = valid[mask_fn(valid)] if len(valid) else valid
        mat = g["material"].iloc[0]
        if pool.empty:
            rows.append({"rm_code": code, "material": mat, "vendor": None, "price": None, "spend": None, "comparable_quotes": len(valid), "why": "No vendor qualifies yet"})
            continue
        best = pool.sort_values(rank_col, ascending=rank_col != "sku_score").iloc[0]
        rows.append({"rm_code": code, "material": mat, "vendor": best["vendor"], "price": best["cost_inr_per_spec_kg"], "spend": best["spend_inr"],
                     "comparable_quotes": len(valid), "why": label(best, pool)})
    return pd.DataFrame(rows, columns=LINE_COLS)


def _why_recommended(best, pool):
    cheapest = pool.sort_values("cost_inr_per_spec_kg").iloc[0]
    if cheapest["vendor"] == best["vendor"]:
        return "Best on your priorities, and the cheapest"
    gap = best["cost_inr_per_spec_kg"] - cheapest["cost_inr_per_spec_kg"]
    if best["inventory_cost_inr"] < cheapest["inventory_cost_inr"] and (best["moq_kg"] or 0) < (cheapest["moq_kg"] or 0):
        return f"Rs {gap:,.2f}/kg dearer than {short(cheapest['vendor'])}, but its MOQ is {best['moq_kg']:,.0f} kg against {cheapest['moq_kg']:,.0f} kg, so holding stock costs less"
    return f"Best on your priorities, Rs {gap:,.2f}/kg dearer than {short(cheapest['vendor'])}"


def options(scored):
    """Three standard awards, all computed from the same normalized quotes."""
    if scored.empty:
        return {}
    q = scored[scored["not_quoted"] != True]  # noqa: E712
    return {
        "Recommended": _pick(q[q["sku_score"].notna()], lambda g: g["cleared_questionnaire"] == True, "sku_score", _why_recommended),  # noqa: E712
        "Lowest bid": _pick(q, lambda g: g["comparable"] == True, "cost_inr_per_spec_kg", lambda b, p: "Lowest landed price"),  # noqa: E712
        "Quality-cleared split": _pick(q, lambda g: g["cleared_questionnaire"] == True, "cost_inr_per_spec_kg", lambda b, p: "Cheapest vendor that cleared the quality questions"),  # noqa: E712
    }


OPTION_HELP = {
    "Recommended": "Best vendor per line on your priorities, among vendors that cleared the quality questions.",
    "Lowest bid": "Lowest landed price per line, whatever the quality answers.",
    "Quality-cleared split": "Cheapest per line, but only among vendors that cleared the quality questions. This is the VP's question.",
}


# ------------------------------------------------------------------ approvals
def add_review(kind, title, payload, for_role, for_plant):
    return db.x("INSERT INTO reviews(kind,title,payload,status,for_role,for_plant,at) VALUES(?,?,?,?,?,?,?)",
                kind, title, json.dumps(payload, ensure_ascii=False, default=str), "pending", for_role, for_plant, time.time())


def reviews(status="pending"):
    rows = db.q("SELECT * FROM reviews WHERE status=? ORDER BY id", status) if status else db.q("SELECT * FROM reviews ORDER BY id")
    for r in rows:
        r["payload"], r["history"] = json.loads(r["payload"]), json.loads(r["history"])
    return rows


def reviews_for(u):
    rows = reviews()
    if u["role"] == "admin":
        return rows
    if u["role"] == "category_manager":
        return [r for r in rows if r["for_role"] == "category_manager"]
    return [r for r in rows if r["for_role"] == "plant_manager" and r["for_plant"] == u["plant"]]


def _update_review(rid, status=None, payload=None, note=None, who=None):
    r = db.q("SELECT * FROM reviews WHERE id=?", rid)[0]
    hist = json.loads(r["history"])
    if note:
        hist.append({"at": time.time(), "who": who, "note": note})
    db.x("UPDATE reviews SET status=?,payload=?,history=?,decided_at=? WHERE id=?", status or r["status"],
         json.dumps(payload, ensure_ascii=False, default=str) if payload is not None else r["payload"], json.dumps(hist, ensure_ascii=False), time.time(), rid)


def decisions(plants=None):
    rows = db.q("SELECT * FROM decisions ORDER BY plant, rm_code")
    return [r for r in rows if plants is None or r["plant"] in plants]


def awards(plant=None):
    rows = db.q("SELECT * FROM awards ORDER BY id DESC")
    return [r for r in rows if plant is None or r["plant"] == plant]


def approval_note(plant, option, lines, total, flags):
    out = [f"Award for the {plant_name(plant)} plant, option: {option}.", f"Total for the 6-month need: Rs {total:,.0f}.", ""]
    for _, r in lines.iterrows():
        if isinstance(r["vendor"], str):
            out.append(f"- {r['material']}: {vendor_names()[r['vendor']]} at Rs {r['price']:,.2f}/kg. {r['why']}.")
        else:
            out.append(f"- {r['material']}: not awarded. {r['why']}.")
    if flags:
        out += ["", "Policy checks:"] + [f"- {f}" for f in flags]
    return "\n".join(out)


def submit_award(u, option, lines, scored):
    """The plant manager sends an option for approval. Rules decide who must approve each part."""
    plant = u["plant"]
    rules = config()["approval_rules"]
    chosen = lines[lines["vendor"].map(lambda x: isinstance(x, str))]
    total = float(chosen["spend"].sum())
    flags = [f"{r['material']}: only {r['comparable_quotes']} comparable quote(s), below our minimum of {rules['min_valid_quotes']}. Reason: these were all the vendors that quoted this line."
             for _, r in chosen.iterrows() if r["comparable_quotes"] < rules["min_valid_quotes"]]
    note = approval_note(plant, option, lines, total, flags)
    within = total <= rules["plant_limit_inr"]
    aid = db.x("INSERT INTO awards(plant,option,total,note,status,by_user,at) VALUES(?,?,?,?,?,?,?)", plant, option, total, note,
               "Approved by plant manager" if within else "Waiting for category manager", u["name"], time.time())
    db.x("DELETE FROM decisions WHERE plant=?", plant)
    qty = scored.groupby("rm_code")["rfx_qty_kg"].first().to_dict()
    for _, r in chosen.iterrows():
        db.x("INSERT INTO decisions(plant,rm_code,material,vendor,price,annual_kg,reason,status,award_id,at) VALUES(?,?,?,?,?,?,?,?,?,?)",
             plant, r["rm_code"], r["material"], r["vendor"], r["price"], float(qty.get(r["rm_code"], 0)) * 2, r["why"],
             f"Approved by {plant_name(plant)} plant manager" if within else "Waiting for category manager", aid, time.time())
    if not within:
        add_review("over_limit", f"{plant_name(plant)} award above the plant limit", {"award_id": aid, "total": total, "note": note}, "category_manager", None)
    conflicts = cross_plant_conflicts(plant, scored)
    for c in conflicts:
        db.x("UPDATE decisions SET status='Waiting for category manager' WHERE plant IN (?,?) AND rm_code=?", c["a"]["plant"], c["b"]["plant"], c["rm_code"])
        add_review("cross_plant", f"Two plants, two vendors: {c['material']}", c, "category_manager", None)
    return {"award_id": aid, "total": total, "within_limit": within, "flags": flags, "conflicts": conflicts, "note": note}


def cross_plant_conflicts(plant, scored):
    """Same material, different vendors at two plants: neither plant can see the combined picture."""
    mine = {d["rm_code"]: d for d in decisions([plant])}
    out = []
    for d in decisions():
        if d["plant"] == plant or d["rm_code"] not in mine or d["vendor"] == mine[d["rm_code"]]["vendor"]:
            continue
        a, b = mine[d["rm_code"]], d
        out.append({"rm_code": d["rm_code"], "material": d["material"], "a": a, "b": b, "saving": group_saving(a, b, scored)})
    return out


def group_saving(a, b, scored):
    """What moving plant a to plant b's vendor would save, using group terms neither plant sees alone."""
    term = next((t for t in config()["group_terms"] if t["vendor"] == b["vendor"] and t["rm_code"] == b["rm_code"]), None)
    if not term:
        return None
    combined = a["annual_kg"] + b["annual_kg"]
    if b["annual_kg"] >= term["min_annual_kg"] or combined < term["min_annual_kg"]:
        return None
    pct = term["discount_pct"] / 100
    rows = scored[(scored["rm_code"] == a["rm_code"]) & (scored["comparable"] == True)].set_index("vendor")  # noqa: E712
    if b["vendor"] not in rows.index or a["vendor"] not in rows.index:
        return None
    alt, cur = rows.loc[b["vendor"]], rows.loc[a["vendor"]]
    alt_price = float(alt["cost_inr_per_spec_kg"]) * (1 - pct)
    a_price_gain = (float(cur["cost_inr_per_spec_kg"]) - alt_price) * a["annual_kg"]
    a_holding = (float(alt["inventory_cost_inr"]) - float(cur["inventory_cost_inr"])) * 2     # 6-month figure to a year
    b_gain = b["price"] * pct * b["annual_kg"]
    return {"term": term, "combined_kg": combined, "plant_b_kg": b["annual_kg"], "alt_price": alt_price, "plant_a_price_gain": a_price_gain,
            "plant_a_extra_holding": a_holding, "plant_b_gain": b_gain, "net": a_price_gain - a_holding + b_gain,
            "moq_now": float(cur["moq_kg"] or 0), "moq_alt": float(alt["moq_kg"] or 0)}


def approve_both(rid, u):
    r = next(x for x in reviews() if x["id"] == rid)
    p = r["payload"]
    for side in ("a", "b"):
        db.x("UPDATE decisions SET status=? WHERE plant=? AND rm_code=?", "Approved by category manager", p[side]["plant"], p["rm_code"])
    _update_review(rid, "approved", note="Approved both decisions as made by the plants.", who=u["name"])


def approve_review(rid, u, note):
    r = next(x for x in reviews() if x["id"] == rid)
    if r["kind"] == "over_limit":
        db.x("UPDATE awards SET status='Approved by category manager' WHERE id=?", r["payload"]["award_id"])
        db.x("UPDATE decisions SET status='Approved by category manager' WHERE award_id=? AND status='Waiting for category manager'", r["payload"]["award_id"])
    _update_review(rid, "approved", note=note, who=u["name"])


def ask_plant(rid, u, note):
    """The category manager asks plant a to move. The plant sees the request and the group saving, not the other plant's details."""
    r = next(x for x in reviews() if x["id"] == rid)
    p = r["payload"]
    s = p["saving"]
    plant = p["a"]["plant"]
    ask = {"review_id": rid, "rm_code": p["rm_code"], "material": p["material"], "from_vendor": p["a"]["vendor"], "to_vendor": p["b"]["vendor"], "note": note,
           "group_saving": s["net"] if s else None, "own_effect": (s["plant_a_price_gain"] - s["plant_a_extra_holding"]) if s else None,
           "moq_now": s["moq_now"] if s else None, "moq_alt": s["moq_alt"] if s else None, "alt_price": s["alt_price"] if s else None}
    add_review("group_request", f"Category manager asks: move {p['material']} to {short(p['b']['vendor'])}?", ask, "plant_manager", plant)
    _update_review(rid, "waiting_plant", note=f"Asked {plant_name(plant)} to move to {short(p['b']['vendor'])}. {note}", who=u["name"])


def plant_reply(req_id, u, accept, reason):
    req = next(x for x in reviews() if x["id"] == req_id)
    p = req["payload"]
    card = next(x for x in reviews(None) if x["id"] == p["review_id"])
    _update_review(req_id, "answered", note=("Accepted" if accept else "Declined") + (f": {reason}" if reason else ""), who=u["name"])
    cp = card["payload"]
    cp["plant_reply"] = {"accept": accept, "reason": reason, "by": u["name"]}
    if accept:
        cp["suggestion"] = f"Approve both plants on {short(p['to_vendor'])} with the group discount."
    else:
        cp["suggestion"] = (f"Approve both decisions as made for now. Re-quote {p['material'].split(' (')[0].lower()} with {short(p['to_vendor'])} at the combined volume once "
                            f"{plant_name(u['plant'])}'s reason no longer applies, and record the saving left on the table.")
    _update_review(card["id"], "pending", payload=cp, note=f"{plant_name(u['plant'])} replied: " + ("accepted." if accept else f"declined. {reason}"), who=u["name"])


def resolve_with_suggestion(rid, u):
    r = next(x for x in reviews() if x["id"] == rid)
    p = r["payload"]
    rep = p.get("plant_reply") or {}
    if rep.get("accept"):
        s = p["saving"]
        db.x("UPDATE decisions SET vendor=?,price=?,reason=?,status=? WHERE plant=? AND rm_code=?", p["b"]["vendor"], s["alt_price"],
             f"Moved at the category manager's request: {p['saving']['term']['discount_pct']}% group discount at combined volume", "Approved by category manager", p["a"]["plant"], p["rm_code"])
        db.x("UPDATE decisions SET price=?,status=? WHERE plant=? AND rm_code=?", p["b"]["price"] * (1 - s["term"]["discount_pct"] / 100), "Approved by category manager", p["b"]["plant"], p["rm_code"])
    else:
        for side in ("a", "b"):
            db.x("UPDATE decisions SET status=? WHERE plant=? AND rm_code=?", "Approved by category manager, re-quote planned" if side == "a" else "Approved by category manager", p[side]["plant"], p["rm_code"])
    _update_review(rid, "approved", note="Approved as suggested: " + p.get("suggestion", ""), who=u["name"])


def answer_question(rid, u, answer):
    _update_review(rid, "answered", note=answer or "Seen.", who=u["name"])


def reset():
    with db._write, db.conn() as c:
        c.executescript("DROP TABLE IF EXISTS decisions; DROP TABLE IF EXISTS awards; DROP TABLE IF EXISTS reviews; DROP TABLE IF EXISTS access_log;")
    init()
