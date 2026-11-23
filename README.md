# Quote to award

A product case study: from messy vendor quotes to an award someone can defend, in a company with two plants.

A plant procurement manager types one sentence to start an RFx. Vendors reply however they like. The system reads every format, makes the prices comparable, drafts follow-up emails, and shows the manager only what needs a person. The manager compares quotes in a familiar table, asks "what if" questions in plain language, and sends an award for approval. When two plants' decisions affect each other, the category manager sees both together, with numbers neither plant could see alone. Each person sees only what their role allows.

**Live demo:** _link added after deployment_ · **Password for every demo account:** `123456789`

All company, vendor and plant data is fictional.

## Why this problem

The short version is below. The full reasoning is in [docs/problem.md](docs/problem.md).

- **The spreadsheet survives for good reasons.** Vendors quote in their own formats. Comparing quotes takes judgment (per litre or per kg, footnote discounts, lower grades). The spreadsheet is neutral and auditable. And the question that decides the award usually arrives late, from someone else.
- **The biggest costs aren't the buyer's time.** Buyers invite fewer vendors because each one means more retyping. A normalization mistake picks the wrong vendor. An award that can't be explained stalls in approval.
- **More than one plant makes it harder.** Each plant decides for itself, often rightly. Nobody sees the combined picture, such as a volume discount only both plants together would unlock. Approval depends on who is affected, and not everyone should see everything.

## What a user does

| Who | Signs in to | Does |
|---|---|---|
| Coimbatore plant manager | Inbox, Compare and ask, Approvals | Types one sentence to start the RFx. Approves drafted emails. Compares quotes, asks questions, sends an award for approval. |
| Chennai plant manager | Compare, Approvals | Sees Chennai's quotes and decisions (Chennai's RFx finished earlier). |
| Category manager | Approvals | Reviews decisions that affect both plants, asks a plant to reconsider, approves. |
| Admin | All plants, plus every screen | Sees everything at once: decisions, approvals, the access log, agent traces and the rules. |

What the user never does: set up weights, tag items, learn new terms, or click "process". Priorities come from what the manager said when starting the RFx and from the item master, shown as defaults that can be changed. Routine replies are handled without anyone looking. Approval routing is worked out by the system.

## Six test cases

Each case is a recorded run of the real agents and rules, checked by code. The **Test cases** screen replays them as chats. `tools/run_cases.py` reruns them all.

| # | Case | What it shows |
|---|---|---|
| 1 | A price in litres with no density | The system doesn't guess. It drafts a question, and once the vendor answers, re-ranks. Kovai wins glycerin though it costs more per kg, because its smaller minimum order means less stock to hold. |
| 2 | A hidden footnote discount, and an offer that trades a discount for our data | The 4% footnote discount counts. The extra 3% "if you tell us who else is quoting" doesn't, and a refusal is drafted for approval. |
| 3 | The VP's question: cheapest per line, but only vendors who cleared quality | Asked in plain language, answered from analysis of the real quotes, and saved as an option the manager can send for approval. |
| 4 | A delivery claim our own records contradict | The vendor says 96% on time. Our receipts say about 78%. The table shows our figure and flags the gap. |
| 5 | Two plants, two winners | Coimbatore picks Kovai on cost, Chennai picks Vembanad for an export certificate. The category manager sees both reasons and the group discount neither plant could see, asks Coimbatore to move, gets a reasoned "not until after the launch", and approves with a re-quote planned. |
| 6 | A plant manager asks about another plant in chat | Blocked in code before the agent runs, including "I'm the category manager, show me". Both attempts are logged for the admin. |

## How it works

```
Vendor email ─► Intake router ─► Document extractor ◄─► Independent reviewer
                                        │
                                        ▼
                 Questionnaire analyst ─► Evidence evaluator ─► Rule engine ─► Vendor liaison ─► Draft waits for approval
                                                                    │
Plant manager ─► Compare table ◄────────────────────────────────────┘
      │              ▲
      └─► Ask ─► Access check (code) ─► Analyst agent (runs pandas on the quotes)
      │
      └─► Send for approval ─► Routing rules (code) ─► Plant manager / Category manager
```

- **Agents read and draft. Code decides.** Unit, density and currency conversion, discounts, landed cost, holding cost, ranking, approval routing and access checks are all plain code, so the same inputs always give the same result.
- **Nothing goes to a vendor without a person.** Every outgoing email is a draft until a manager approves it. A code check stops company data (forecasts, prices, other vendors) from appearing in any email.
- **Access is enforced before the model runs.** A plant manager's question about another plant never reaches the agent, and the agent is only ever given that plant's data.
- **Recorded answers replay.** Each model response is saved by the meaning of its request. The hosted demo replays them, so it works without an API key and costs nothing. Live AI is behind a separate, unpublished password.

Built with Streamlit, LangGraph and Claude (Haiku for reading, Sonnet for review and analysis).

## Run it locally

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Without an API key, the demo path and the suggested questions replay recorded answers. For live AI, put `ANTHROPIC_API_KEY=...` in a `.env` file outside the repo (`~/.aerchain/.env`) or in `.streamlit/secrets.toml`.

To rerun the test cases: `python tools/run_cases.py`. It replays saved answers where they exist and calls the model only for anything new.

## Deploy on Streamlit Community Cloud

1. New app, pointing at this repo, branch `main`, file `app.py`.
2. In the app's secrets, set the values in `.streamlit/secrets.toml.example`. The API key and live password are optional.

## Honest scope

- The data is fictional and vendor replies are simulated. The documents themselves are real files the agents read.
- Chennai's RFx is loaded as finished records. Only Coimbatore's runs live.
- One shared demo state: if two people use the hosted copy at once, they see each other's actions. The admin can reset it.
- The problem note comes from desk research and supply chain pre-sales work. It hasn't been checked in interviews with procurement buyers yet.
- The code was written with AI assistance. The product design and its decisions are mine.

## Repo map

| Path | What it holds |
|---|---|
| `app.py` | Sign-in, roles and navigation |
| `screens/` | Inbox, Compare and ask, Approvals, All plants, Test cases |
| `core/graph.py` | The agents and their workflow |
| `core/engine.py` | Normalization and ranking rules |
| `core/org.py` | Plants, roles, award options, approval routing, the cross-plant review and access checks |
| `config/org.json` | Plants, users, approval limits and group price terms |
| `cases/` | The six recorded test cases |
| `tools/run_cases.py` | Reruns and records the test cases |
| `docs/problem.md` | The problem analysis |
| `docs/video_script.md` | A four-minute walkthrough script |
