# Tripwire: pitch, demo and Q&A

**Tripwire: a pause when it matters.** It's an always-on guardian that runs on the Vexo band. When someone pressures an older adult, on a call or face to face, Tripwire notices, pauses the situation and brings in family before money moves.

---

## 1. Why every sponsor is essential

The rule we pitched ourselves: if we took any sponsor out, Tripwire would stop working. Each one does a job that the others can't.

### Vexo band: the reason Tripwire can exist at all
- **Only an always-worn microphone can protect someone all day.** Scams don't wait for an app to be open. They arrive by phone, at the front door, from a "contractor" in the kitchen, or a "mechanic" quoting $2,000. The Vexo band is on the wrist through all of it.
- **Phones aren't built for this.** Mobile operating systems deliberately restrict apps from listening in the background, for battery and privacy reasons. A phone is also often in another room, face down or dead. An app that needs to be opened protects nobody at the moment it matters.
- **Built for the people who need it most:** elders, patients and people with memory decline, who won't, or can't, operate an app under pressure. The band asks nothing of them. They just wear it.
- **In the product:** band audio feeds our ambient pipeline (speaker `ambient`), so the same detector that protects calls also protects in-person conversations.

### Deepgram (Nova-3): the ears
- **Real-time streaming with end-of-utterance detection** (`endpointing`, `utterance_end_ms`). We act on a sentence the moment it finishes, not at the end of a call.
- **Smart formatting is a detection feature for us.** Deepgram turns "five hundred dollars" into "$500" and "gift cards" into clean tokens. Our evidence engine quotes exact words, and every quote is checked against the transcript before family sees it. Without accurate, normalized transcripts, the evidence can't be trusted. We measured it on the scam script: the transcript was word for word.
- **Audio relay architecture:** browser mic → Tripwire backend → Deepgram. The key never touches a client, and the same relay accepts audio from the band.

### Google DeepMind Gemini (3.5 Flash-Lite): the judgement
- **Fast enough to sit inside a live conversation.** We benchmarked the Flash family on our key: 3.5 Flash-Lite came back in **~620 ms** median, versus 2.6 s for a larger Flash model. A decision that lands 3 seconds late lands after the gift card number is read out.
- **Rules first, Gemini for ambiguity.** Fixed rules catch the obvious script (gift cards, urgency, secrecy). Gemini resolves the grey zone, like "$2,000 for the oil change", where context decides. That makes an always-on device affordable: benign chatter costs nothing, and the model is only called when it matters.
- **It also writes the AI assistant's single live reply** to the caller, within strict safety rules: it never impersonates the wearer, never shares private details, never agrees to pay.

### ElevenLabs (Flash v2.5): the voice
- **The AI has to sound human, calm and in control**, so the caller stays on the line while family is reached, and so a frightened older adult hears reassurance, not a robot. A robotic voice gets hung up on, or triggers a call-back from an angry scammer.
- **Low-latency synthesis** means the assistant speaks within about a second of the takeover.
- **It identifies itself honestly:** "I am Tripwire, an AI assistant." We use a premium voice to be clear, not to deceive.

### Daily: the call surgery
- **Takeover depends on per-participant routing.** The wearer must stop hearing the caller while the AI and the daughter still can. That isn't muting. It's per-track subscription control inside one live room, which Daily's WebRTC rooms give us.
- **Role-scoped, short-lived meeting tokens** for caller, wearer and family. A stranger with the link can't join.
- **The daughter joins the same live room with one tap**, and her real participant-joined event (not a button click) is what stops the AI.

---

## 2. One-minute video (fully AI-generated, labelled "Illustration")

| Time | Picture | Voice-over |
|---|---|---|
| 0–8 s | Close-up: an older woman's hand on a kitchen table, a phone glowing with an incoming call. Slim band on her wrist. | "A convincing voice. An urgent request." |
| 8–18 s | Split screen: the phone, and a soft glow on the band. Transcript words appear: "gift cards", "right now", "don't tell anyone". | "Her Vexo band hears what she hears, and Tripwire knows what pressure sounds like." |
| 18–30 s | The call audio fades away for her. A calm card on screen: "This request may be unsafe." The caller hears a voice. | "Tripwire pauses the moment. An AI assistant, clearly identified, holds the caller." |
| 30–42 s | Daughter at work; her phone lights up: "Mom may be in a risky call", with the exact quoted words. She taps Join. | "Her daughter sees the exact words that raised concern, and joins in one tap." |
| 42–52 s | Mother and daughter on the call; the caller line is gone. | "No money moves until family decides." |
| 52–60 s | Title card: "Tripwire. A pause when it matters." Small caption: "Built on Vexo · Deepgram · Gemini · ElevenLabs · Daily". | (music) |

Generation prompts: "Realistic cinematic close-up of an older adult's hand resting next to a smartphone on a warm kitchen table, slim fabric wristband, incoming call glow, natural window light, restrained documentary tone, no text, no logos, 16:9." Same style for the daughter shot: "woman in her 40s at an office desk glancing at a phone notification, concerned, natural light".

---

## 3. Two-minute live demo (real product)

**Setup before going on stage:** four browser windows. The Presenter on the projector, Caller on laptop A, Wearer on laptop B (headphones on, band on wrist), Family on a phone. Start a session from `/` and open each role link.

| Time | Action | What judges see / hear |
|---|---|---|
| 0:00–0:15 | "Meet Grandma. She's wearing a Vexo band. Tripwire is listening with her." | The Presenter in **Monitoring**, the band chip on the wearer screen. |
| 0:15–0:40 | The caller actor speaks the scam: "Grandma, I'm in trouble, buy $500 in gift cards right now, don't tell anyone, not even Mom." | Live captions stream in; Deepgram text appears on the presenter; evidence words get underlined. |
| 0:40–0:55 | Detection fires. | Risk turns **High** with 5 reasons. State goes **Protecting → Assistant active**. The routing graph cuts the caller→wearer link. The wearer screen turns calm and warm: "This request may be unsafe." |
| 0:55–1:15 | The AI speaks to the caller (audible from laptop A): "I am Tripwire, an AI assistant…" The caller pushes back; the AI gives one live reply. | AI lines appear in the transcript in aqua. |
| 1:15–1:35 | The family phone shows the alert with the verbatim quotes. The daughter taps **Join the call**. | State goes to **Family joined**; the AI stops instantly; the routing graph lights the family link. |
| 1:35–1:50 | The daughter: "Mom, pause. I'll call him on the number we know." The daughter taps **Reconnect wearer**. | The wearer is reconnected only by explicit family action. |
| 1:50–2:00 | "Detects pressure. Pauses the moment. Brings in family. Tripwire, on Vexo." | End session; it resets cleanly for the next demo. |

**If the venue network fails:** use the Presenter's replay (clearly labelled "Demo replay") and say it's a replay.

---

## 4. Q&A defences

**Why not just a phone app?**
Phones aren't designed to listen all day. Background microphone access is restricted by mobile operating systems, it drains the battery, and the phone is often not on the person. The risky moments for elders are often not phone calls at all: a fake contractor at the door, a "grandchild" on a video call, a pushy salesperson in the living room. A band is worn, not opened, so it protects people who will never open an app under pressure: patients, people with dementia, the very elderly.

**Isn't always-on listening a privacy nightmare?**
Tripwire acts on patterns, not recordings. Audio is streamed for transcription and not stored. Session state lives in memory and is wiped when the session ends. Only the specific sentences that triggered an alert go to the chosen family member, and each quote is checked against the transcript. Protection is explicitly enabled by the wearer and family together.

**What about false positives?**
We designed for them. "$2,000 for a repair" alone is only **review**, never a takeover. A takeover needs several independent signals together (payment pressure, urgency, secrecy, a claimed emergency). A false positive costs a 30-second pause and a call from your daughter. A false negative costs someone's savings.

**Doesn't this take away the elder's autonomy?**
The AI never speaks *for* the wearer and never makes decisions. It only pauses. The wearer can end the call at any time, and family, a person they chose, decides when to reconnect. It's the digital version of a daughter saying "hang on, let me talk to them."

**Why hold the caller instead of just hanging up?**
Hanging up leads to call-backs and escalation ("your grandson will go to jail!"). Holding keeps the line stable, puts an AI between the scammer and the victim, and gives family a live line to verify in seconds.

**What if family doesn't answer?**
Today's flow alerts one trusted contact. Next: an escalation chain (second contact, care-home staff), and the wearer stays protected until someone joins or the call ends. The safe default is "paused", never "money moved".

**Is recording a call legal?**
The AI identifies itself as an AI immediately. We don't store audio. Transcripts live only in memory for the session. For production, consent flows follow two-party-consent rules by jurisdiction.

**Does it work on normal cellular calls?**
The prototype protects calls through our app, plus in-person conversations through the band. Carrier and VoIP integrations are on the roadmap. The band's ambient mode already covers the scams no call filter can see.

**Latency?**
Speech to transcript is about 0.3–1 s after the sentence ends (Deepgram endpointing). Rules run instantly; Gemini Flash-Lite is about 0.6 s when needed. The AI voice starts about 1 s after takeover. In our live test, the takeover happened within a second of the scam sentence finishing.

**What if the scammer speaks another language?**
Deepgram and Gemini are multilingual, and the detector's patterns aren't English-specific in principle. Demo scope is English.

**Business model?**
A subscription bundled with the Vexo band for families and care providers. Insurers and banks have a direct incentive: elder fraud costs Americans billions every year.

**What did you actually build in a day?**
A live pipeline, tested end to end in real Chrome with our test harness: browser microphone → Deepgram streaming → rules + Gemini → takeover state machine → ElevenLabs voice to the caller → family alert with verified quotes → family join through call events → explicit wearer reconnect → clean reset. 217 backend tests and a 9-step live browser test pass.
