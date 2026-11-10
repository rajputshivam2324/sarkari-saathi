---
marp: true
theme: default
paginate: true
title: Sarkari Saathi
style: |
  section { font-family: "Segoe UI", "Noto Sans", "Noto Sans Devanagari", sans-serif; padding: 56px 70px; }
  h1 { color: #0b5d3b; }
  h2 { color: #0b5d3b; }
  strong { color: #b45309; }
  section.title { text-align: center; justify-content: center; }
  section.title h1 { font-size: 2.4em; }
  blockquote { border-left: 6px solid #0b5d3b; color: #374151; }
  table { font-size: 0.8em; }
---

<!-- _class: title -->
<!-- _paginate: false -->

# Sarkari Saathi
## बोलिए, योजना पाइए

**Speak. Find the scheme. Know how to apply.**

A voice guide to Indian government schemes, in 10 languages

<!--
SAY (about 12 seconds):
"India has thousands of government schemes. The people who need them most (a farmer, a widow, a daily-wage worker)
cannot read a government website. So we built Sarkari Saathi: you just talk."
-->

---

# The problem

- **3,272 schemes** are listed on myScheme.gov.in alone
- The information is long, written text, mostly in English
- The people who need it most: farmers, elders, daily-wage workers, first-time smartphone users
- Today they depend on a middleman, or they never find the scheme

> A scheme you cannot find or understand is a scheme you do not get.

<!--
SAY (about 15 seconds):
"The official portal, myScheme, lists over three thousand schemes. It is a great record, but it is a lot of text.
Sarkari Saathi sits on top of it."
NOTE: 3,272 is the number the app loaded from myScheme on the day this deck was written. Do not quote a
"percentage of people who miss out": we have no verified figure for that.
-->

---

# The idea: just talk

1. **Speak** in your own language: Hindi, English, Tamil, Telugu, Kannada, Malayalam, Marathi, Punjabi, Bengali, Gujarati
2. It **answers in the same language, out loud**
3. It tells you what you **get**, who it is **for**, and **how to apply**
4. Full steps and official links appear **on screen**

<!--
SAY (about 15 seconds):
"You speak in your own language, and it answers in the same language, out loud. It tells you what you get, who
it is for, and how to apply. The full steps and official links appear on the screen."
-->

---

# Live demo

| You ask | What to notice |
| --- | --- |
| "पीएम किसान योजना के बारे में बताइए" | Speaks the benefit, who it is for, how to apply. Scheme card appears |
| "इसके लिए कौन से कागज़ चाहिए?" | Answers from the official record, in Hindi |
| "Is it still accepting applications in 2026?" (switch to English) | **Does not guess.** Says the record has no closing date and points to the official portal |

<!--
SAY (about 70 seconds, see docs/DEMO_SCRIPT.md for the exact words and clicks).
-->

---

# How it works

**Speech in** (Gnani Prisma) → **understand** the person → **find** schemes (live myScheme) → **write** the answer (Gemini 2.5 Flash, only from the official record) → **check** it (guardrails) → **speech out** (Gnani Timbre)

- Answers use the scheme's full official record: eligibility, exclusions, every apply route
- If the AI is slow, rate limited or fails a check, a **rule-based answer** still replies

<!--
SAY (about 30 seconds):
"Behind this: speech recognition and voice from Gnani. Scheme data comes live from myScheme. Gemini 2.5 Flash writes the
answer, but only from the official record. Every answer then passes a guardrail check: no invented schemes, no made-up
amounts, no promise that you are eligible. If anything fails, a rule-based fallback still answers."
-->

---

# Honest by design

- Says **"I don't have that"** instead of guessing: closing dates, approval time, missing helplines
- A **verified supplement** for 7 popular schemes: documents, helplines, fees, each tied to an official page
- Never says "you are eligible": only "looks like a fit", and points to the official decision
- Never reads out a made-up phone number, amount or website

> For a person who cannot double-check, a wrong answer is worse than "ask the Common Service Centre".

<!--
SAY (part of the 30 seconds above, or skip if short on time).
-->

---

# Built to keep working

- **8 Gemini keys** rotate; a key that hits its limit rests while the others carry on (tested: 20 simultaneous requests, 20 answered)
- Popular schemes are **pre-loaded** and answer without waiting on myScheme; others are fetched live in about 0.1 to 0.5 s
- **Ready to deploy** on Google Cloud Run behind `sarkari-api.shivamio.in`

<!--
SAY (about 15 seconds):
"It rotates across eight Gemini keys so it keeps working under load, keeps the popular schemes ready in memory, and is
ready to deploy on Google Cloud Run."
DO NOT say "deployed" or "live in production" until the steps in docs/DEPLOY_GCP.md have been run.
-->

---

<!-- _class: title -->

# Next

More verified schemes · state-level schemes · reach people who do not use a smartphone

## Sarkari Saathi
### बोलिए, योजना पाइए

<!--
SAY (about 10 seconds):
"Next: more verified schemes and state-level schemes. Sarkari Saathi. Bolo, yojana paao."
NOTE: "Next" items are plans, not features. Say "next", not "we support".
-->
