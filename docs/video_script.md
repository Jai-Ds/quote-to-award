# Video script: about 4 minutes

Record the live app at 1080p, browser zoom 90%. Spoken lines are plain text. **Do** lines are actions. Before recording, reset the demo as Admin (All plants, Rules, Reset).

## 0:00-0:30 The problem

**Do:** show the sign-in screen.

Buyers retype vendor quotes into spreadsheets, and not because they lack tools. Vendors quote in their own formats, comparing quotes takes judgment, and the question that decides the award usually arrives late from someone else. In a company with two plants, it gets harder: each plant decides for itself, and nobody sees the combined picture. This app takes a buyer from messy quotes to an approved award, across two plants.

## 0:30-1:10 One sentence, then the system works

**Do:** sign in as Coimbatore plant manager. In the Inbox, click Draft the RFx, then Send to 5 vendors.

I type one sentence. Quantities come from the forecast and bill of materials, so I don't type them. My worry about peptide supply has already become questions for vendors.

**Do:** wait for replies. Point at Needs you.

Five vendors reply in five formats: Excel, PDF, Word, a photo, and an email. The agents read them all. I only see what needs me: two drafted replies.

## 1:10-1:50 The ugly edges stay inside the flow

**Do:** open Tungabhadra's draft.

Tungabhadra offered 3% more if we tell them who else is quoting. The system counts the 4% discount hidden in their footnote, refuses the conditional 3%, and drafts the refusal. Nothing is sent until I approve.

**Do:** open Kovai's draft and approve it. In Demo controls, send Kovai's answer to the open question.

Kovai priced glycerin per litre with no density. The system won't guess, so it asked. Kovai replies with the density, and nobody clicks process.

## 1:50-2:40 Compare and ask

**Do:** open Compare and ask. Point at glycerin, then at Tungabhadra's red flag.

This is the comparison table buyers already know: vendors across, lines down, landed price per kg. Glycerin now goes to Kovai, even though it's 70 paise dearer, because its minimum order is 200 kg against 500, so we hold less stock. And Tungabhadra says it delivers on time 96% of the time; our own receipts say 78%.

**Do:** click the VP's question chip.

Here's the VP's question: cheapest per line, but only vendors who cleared quality. The answer comes from real analysis, and it's saved as an option in the table.

**Do:** click Send for approval.

The approval note is drafted for me, including the lines with fewer than three quotes.

## 2:40-3:30 Two plants, one decision

**Do:** sign out, sign in as Category manager. Open the glycerin card.

Chennai chose Vembanad, because its export customer audits for a certificate only Vembanad holds. Coimbatore chose Kovai. Both are right locally. What neither plant could see: together they cross Vembanad's group discount tier. The card shows the net saving.

**Do:** ask Coimbatore to move. Sign in as Coimbatore, decline with the launch reason. Sign back in as Category manager and approve as suggested.

Coimbatore declines with a reason: it won't switch suppliers during the February launch. The suggestion is to approve both now and re-quote after March. Every decision, reason and approver is recorded.

## 3:30-3:50 Who sees what

**Do:** sign in as Coimbatore, open Compare and ask, type "Which vendor did Chennai choose for glycerin?"

A plant manager can't see another plant's decisions. The block is in code, before the agent runs, so the agent never has the data to leak.

## 3:50-4:10 Close

**Do:** open Test cases.

Six hard cases, each recorded from a real run and checked by code. The repo has the problem note, the code and these cases.
