# Live demo: two scenarios, about 2 minutes

**Cast:** Ayush plays **Grandma** and wears the Vexo band. A teammate plays the **Scammer**, and a second teammate plays the **Daughter** on a phone.
**Screens:** the Presenter on the projector, the Caller on laptop A (the scammer's), the Wearer on laptop B (Grandma's, with headphones), the Family page on the daughter's phone.

Everything below is live: band mic, Deepgram, Gemini, ElevenLabs, our backend. Nothing is pre-recorded.

---

## Before you go on stage (5 minutes)

1. Start the backend and frontend: `make backend` and `cd frontend && npm run dev`.
2. Check the keys: `python -m backend.audio.provider_checks.run_all`. You want Daily, Deepgram and Gemini to show PASS. ElevenLabs only fails its read-permission check; speech works.
3. Close any Vexo dashboard tab. **Double-tap the band** (blue blink = discoverable).
4. On laptop B, open http://localhost:3000, choose **Call** and click **Start session**. Copy the four role links.
5. Attach the band to that session: `python -m backend.band_bridge --band 17 --session <id> --token <presenter token>`. The band breathes green, then shows **solid blue** (listening).
6. Open the Presenter on the projector, the Wearer on laptop B, the Caller on laptop A, and the Family link on the daughter's phone.
7. On the Caller and Wearer screens, click **Join call**. The live captions should show "live".
8. Set laptop speaker volume to about 60%. Keep the room as quiet as you can.

For **Scenario 2**, start a second session in **Ambient** mode and attach the band to it, the same way.

---

## Scenario 1: the grandchild phone scam (about 70 s)

| Time | Who | Say / do | What the judges see |
|---|---|---|---|
| 0:00 | Ayush (to the audience) | "This is my grandmother. She wears a Vexo band. Tripwire listens with her all day. She never has to open an app." | The Presenter shows **Monitoring**. The band glows blue. |
| 0:08 | Scammer (laptop A) | *"Grandma, it's me. I'm in trouble. I need you to buy five hundred dollars in gift cards right now. Please don't tell anyone, not even Mom."* | Captions stream in. On the presenter, the transcript fills and "gift cards", "right now" and "don't tell anyone" get **underlined as evidence**. |
| 0:20 | Grandma | *"Should I call your mother?"* | The wearer line appears. |
| 0:24 | Scammer | *"No! There's no time."* | Risk turns **High**: gift cards, urgency, secrecy, claimed emergency. The state moves **Protecting → Assistant active**. The routing graph **cuts the caller→wearer link**. |
| 0:28 | (automatic) | Nobody touches anything. | **The band blinks red on Grandma's wrist.** Her screen turns calm: "This request may be unsafe." The caller's voice is gone from her headphones. |
| 0:32 | AI (heard on laptop A) | *"I am Tripwire, an AI assistant. This conversation has been paused for family verification. Please explain your request."* | The AI line appears in aqua. |
| 0:40 | Scammer | *"It has to happen now!"* | The AI gives **one** calm reply. It never negotiates, never pays. |
| 0:46 | Daughter (phone) | The phone shows "**Mom may be in a risky call**" with the exact quoted words. She taps **Join the call**. | State goes to **Family joined**; the AI stops instantly; the band **breathes blue**. |
| 0:55 | Daughter | *"Mom, it's me. Hang on. I'll call him on the number we know."* Then she taps **Reconnect wearer**. | The wearer is reconnected only because family chose to. |
| 1:05 | Ayush | "Detected. Paused. Family in. No money moved." | Click **End session**; the band turns off. |

## Scenario 2: the in-person scam, which no phone app can see (about 45 s)

Start the **Ambient** session and attach the band. There's no call this time; the band is the only ear.

| Time | Who | Say / do | What the judges see |
|---|---|---|---|
| 0:00 | Ayush | "Not every scam is a phone call. Here's a 'mechanic' in Grandma's driveway." | The presenter shows **Monitoring**, ambient mode. |
| 0:05 | Scammer (standing next to Ayush, speaking normally) | *"Ma'am, your car is not safe to drive. The repair is two thousand dollars, and you need to pay right now with gift cards. Don't call your daughter, there's no time."* | The band's mic → live transcript on the presenter. |
| 0:15 | (automatic) | — | Risk is **High** (gift cards, payment, large amount, urgency). **The band blinks red.** The daughter's phone gets the alert with the verbatim quotes: "The repair is $2,000." · "pay right now with gift cards" · "there's no time". |
| 0:25 | Ayush | "A phone can't hear this: it's in her purse. The band can. And no app had to be opened." | |
| 0:30 | Ayush | (Optional) "And if she ever falls, the band's motion sensor alerts family automatically." | |

**Contrast line for Q&A:** "$2,000 for a repair" *alone* is only **Review**, never an alert storm. It takes several pressure signals together (payment method + urgency + secrecy) to trigger.

---

## If something goes wrong

| Problem | Fix (out loud, honestly) |
|---|---|
| Band not found | Close the dashboard tab, double-tap the band, re-run the bridge command. |
| Captions don't start | Click **Start** on the live captions strip; check the browser mic permission. |
| Network down | Use the Presenter's **Demo replay** (clearly labelled) and say it's a replay. |
| The AI voice is silent | The text still shows; ElevenLabs falls back to the browser voice, which is labelled. |

## Verified before the demo (2026-11-14)
- **Scenario 2 on the real band 17:** band mic → Deepgram → high risk → family alert with verbatim quotes → LED red. No touch needed.
- **Scenario 1 call pipeline in real Chrome:** 9/9 checks: live Deepgram transcript, high risk, takeover active, ElevenLabs opening line and reply heard by the caller, family join stops the AI, explicit reconnect, clean end.
