# 2 to 3 minute demo: what to say and do

Target length: **about 2 minutes 40 seconds** (roughly 330 words spoken, plus the pauses while the app answers).
Slides are in [PITCH_DECK.md](PITCH_DECK.md). To view or export them:

```bash
npx @marp-team/marp-cli --no-stdin docs/PITCH_DECK.md --pptx     # PowerPoint
npx @marp-team/marp-cli --no-stdin docs/PITCH_DECK.md --pdf      # PDF (needs Chrome or Chromium installed)
npx @marp-team/marp-cli -s docs                                  # live preview in the browser
```

(Or paste the file into the Marp extension for VS Code.)

---

## The script, with timings

### 0:00 to 0:15 · Slide 1 (title) · say

> India has thousands of government schemes. But the people who need them most (a farmer, a widow, a daily-wage
> worker) cannot read a government website. So we built **Sarkari Saathi**. You just talk.

### 0:15 to 0:45 · Slides 2 and 3 · say

> The official portal, myScheme, lists over three thousand schemes. It is a great record, but it is a lot of text.
> Sarkari Saathi sits on top of it. You speak in your own language, Hindi, English, Tamil and seven more, and it
> answers in the same language, out loud. What you get, who it is for, how to apply.

### 0:45 to 1:50 · Slide 4, then switch to the live app · do and say

Open the app already logged in, on the Desk page, with the microphone on.

| Time | You do | You say / the app does |
| --- | --- | --- |
| 0:45 | Switch to the browser | "Let me show you." |
| 0:50 | Speak in Hindi: **"पीएम किसान योजना के बारे में बताइए"** | App replies aloud: ₹6,000 a year in three instalments, for landholding farmers, apply online or at a Common Service Centre. The scheme card appears. You say: "It tells me what I get, who it is for, and how to apply." |
| 1:10 | Speak: **"इसके लिए कौन से कागज़ चाहिए?"** | App lists Aadhaar, bank account, land records. You say: "A deeper question. This comes from the scheme's own official record." |
| 1:30 | Click **Details** on the card (3 to 4 seconds) | You say: "And the full steps and links are right here." |
| 1:38 | Speak in English: **"Is it still accepting applications in 2026?"** | App says the record shows it opened in February 2019, has no closing date, and sends you to the official portal. You say: "Notice what it does **not** do. It does not guess. If it does not know, it says so." |

### 1:50 to 2:20 · Slide 5 (how it works) · say

> Behind this: speech recognition and voice from Gnani. Scheme data comes live from myScheme. Gemini 2.5 Flash writes
> the answer, but only from the official record. Every answer then passes a guardrail check: no invented schemes, no
> made-up amounts, no promise that you are eligible. If anything fails, a rule-based fallback still answers.

### 2:20 to 2:40 · Slides 7 and 8 · say

> It rotates across eight Gemini keys so it keeps working under load, keeps the popular schemes ready in memory, and
> is ready to deploy on Google Cloud Run. Next: more verified schemes, and state-level schemes.
> **Sarkari Saathi. Bolo, yojana paao.**

If you are running long, cut slide 6 (it is not in the timed script) and shorten the 0:15 section.

---

## Before you record (do all of these)

1. **Do a full dry run first.** The text answers were tested end to end through the backend. The browser
   **microphone, speech recognition and spoken replies were not tested** in this work, so check them yourself.
2. **Ask each of the three demo questions once** before recording, in the same order, and listen to the answers. The
   AI's wording changes a little each time; the facts should not.
3. **Use headphones.** The app mutes the microphone while it speaks, but speakers can still echo into it.
4. **Start the backend a minute early** so the scheme cache is warm, and keep the browser tab open.
5. **Have a typing fallback.** If speech recognition mishears, type the same question in the chat box. Do not fight
   the microphone on camera.
6. **Check the API quota.** Eight Gemini keys are configured; if the app ever answers in a flat, rule-based way, an
   AI call failed. The backend log shows `LLM ok gemini#N` for each AI answer.
7. **Close other tabs and notifications.** Do not show `backend/.env` or any key on screen.
8. **Record the screen at 1080p** and speak slightly slower than you think you need to. Hindi words with a clear
   pause between sentences are easier for the speech recognizer.

## What not to claim on camera

| Do not say | Why | Say instead |
| --- | --- | --- |
| "It's deployed / live" | The deploy guide has not been run | "Ready to deploy on Google Cloud Run" |
| "It knows every scheme in detail" | Full detail depends on the live record; documents and helplines are verified for 7 schemes | "It answers from the official record, and says so when it does not know" |
| "100% accurate" / "always correct" | Guardrails reduce errors; they do not remove them | "Checked against the official record" |
| A percentage of people who miss out on schemes | No verified source in this project | Leave it out |
| "We support Bihar schemes" / state schemes | Not built yet | "Next: state-level schemes" |
| "Works for all 3,272 schemes with documents and helplines" | Only the full record is available for all; the verified extras cover 7 | "Over three thousand schemes, with verified extras for popular ones" |

## If something goes wrong during the take

| Problem | What to do |
| --- | --- |
| It answers in a flat, robotic way | An AI call failed and the fallback replied. Say nothing, ask the question once more; if it repeats, stop and check the backend log |
| No spoken reply | Check browser sound and that the microphone/speaker toggle is not muted; the text still appears on screen |
| A wrong or odd answer | Stop the take. Re-ask the question; do not try to explain it away on camera |
