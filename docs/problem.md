# The problem: from messy quotes to an award someone can defend

This note explains why the quote spreadsheet exists, who it hurts most, and what changes when a company has more than one plant. The build in this repo follows from it.

## Why the spreadsheet survives

Buyers don't retype quotes because they lack tools. They retype because of how sourcing works.

1. **Vendors quote in their own format.** The buyer is one customer among many. A vendor sends whatever its ERP or price list produces: a PDF, an Excel sheet, a photo of a rate card, or a line in an email. Small vendors have no portal. Asking all of them to use one template doesn't work.
2. **Comparing quotes needs judgment, not copying.** One vendor prices per litre and another per kg. One hides a discount in a footnote. One offers a lower grade. Each needs a decision about how to make the numbers comparable, and retyping is how the buyer checks each one.
3. **The spreadsheet is neutral and auditable.** Finance, quality and the plant can all open it. It shows what was compared and why. Anything that replaces it must keep that.
4. **The criteria arrive late.** The question that decides the award often comes from someone else at the end, such as a VP asking for "cheapest per line, but only vendors who passed quality". The buyer then rebuilds the sheet. So the real job isn't comparing prices. It's reaching an award decision that holds up when other people question it.

## Who it hurts most

The buyer spends the time, but the larger costs land elsewhere.

- **Fewer vendors get invited.** Each extra vendor means more retyping, so buyers invite the usual few. Incumbents keep winning, and prices stay where they are.
- **A normalization mistake picks the wrong vendor.** A litre read as a kg, or a discount counted that was only conditional, changes the winner. That costs real money for the life of the contract.
- **Awards that can't be defended stall.** If the buyer can't show why a vendor won, approval drags, or audit questions it later.
- **Plants that can't see each other lose leverage.** This one only shows up in larger companies, below.

## What changes with more than one plant

Most real buyers work in companies with several plants or business units. That is where the hard problems are.

- **Each plant decides for itself, for good reasons.** A plant making an economy product for the domestic market picks on cost. A plant making an export product picks the vendor whose certificate its customer's audit requires. Both decisions can be right.
- **Nobody sees the combined picture.** Two plants buying the same material from different vendors may miss a volume discount that only their combined volume would unlock. They may also both load one small vendor past its capacity. Each plant's decision looks fine on its own.
- **Approval depends on who is affected.** A plant manager can approve their own award up to a limit. When a decision touches another plant, the group category manager should see both decisions together, with the reasons and the numbers, before awards are final.
- **Not everyone may see everything.** A plant manager should see their own plant's quotes and decisions, not another plant's prices. That restriction has to be enforced by the system, not left to the AI's discretion.

## What we build, and what we leave out

**We build** the path from messy quotes to an approved award, for two plants:

- The system reads every quote format, normalizes units and costs, and drafts follow-up emails. The plant manager sees only what needs a person.
- Priorities are inferred from what the buyer already said and from plant policy, shown as defaults that can be changed, never set up from scratch.
- A comparison table in the buyer's own format, with a chat panel that answers "what if" questions by changing the table.
- Approval routing that knows who must approve, including a cross-plant review for the category manager.
- Access by role, enforced in code.

**We leave out**, on purpose:

- Contracts, purchase orders and invoices, which come after the award.
- Vendor onboarding and master-data clean-up.
- A real email system: vendor replies are simulated.
- More than two plants. Two are enough to show every cross-plant problem above.

## How we'll know it works

- Before the first useful answer, the user types one sentence and configures nothing.
- A procurement person can finish the core task without anyone explaining the app.
- Six recorded test cases pass, each covering one of the hard parts above.

## Limits of this note

This note comes from desk research and pre-sales work with supply chain planners. It hasn't yet been checked in interviews with procurement buyers. The data, vendors and plants are fictional.
