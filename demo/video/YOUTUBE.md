# YouTube upload

**Title** (68 characters)
Tripwire: the Vexo band that pauses a scam call and brings in family

**Alternative titles**
- An AI that steps in when Grandpa gets a scam call | Tripwire on Vexo
- Tripwire: a pause when it matters (Vexo Hacks demo)

**Description**
A convincing voice. An urgent request. Grandpa, alone with the decision.

Tripwire runs on the Vexo band, an always-listening wristband. When someone pressures an older adult (gift cards, "right now", "don't tell anyone"), Tripwire notices within about a second:
• it pauses the call, and an AI assistant that clearly identifies itself holds the caller
• the wearer gets a calm warning instead of the scammer's voice
• a trusted family member gets the exact words that raised concern, and joins in one tap
• if the wearer falls, the band alerts family automatically

How it works
• Vexo band: always-on mic over Bluetooth, LED alerts, fall detection
• Deepgram Nova-3: real-time streaming speech-to-text
• Google DeepMind Gemini Decision 1: a calibrated scam probability on every sentence (~420 ms), plus Gemini 3.5 Flash-Lite for the AI's single safe reply
• ElevenLabs: the calm, human voice of the Tripwire assistant
• Daily: WebRTC call rooms with per-track routing, so the wearer stops hearing the caller while the AI and family still can
• FastAPI + Next.js: session state machine, verified evidence, live console

Principles: identifies itself as AI · never moves money · family decides when the wearer rejoins.

Built in a day at Vexo Hacks.

Chapters
0:00 The call
0:21 Tripwire detects pressure
0:25 The AI takes over
0:32 Family joins in one tap
0:44 What it does: calls, in-person scams, falls
0:52 How it works
1:08 A pause when it matters

Story scenes are illustrations with AI-generated voices.

**Tags**
Tripwire, Vexo, Vexo band, Vexo Hacks, scam prevention, elder fraud, grandparent scam, AI safety, wearable AI, Deepgram, Gemini, Gemini Decision, Google DeepMind, ElevenLabs, Daily, WebRTC, hackathon, fall detection, family safety, voice AI

**Thumbnail text** (on a frame of the red band next to the phone)
"Grandpa, buy gift cards. NOW." → *Tripwire stepped in.*

**Settings:** Category Science & Technology · Not made for kids · Altered or synthetic content: **Yes** (the story uses AI-generated voices).
