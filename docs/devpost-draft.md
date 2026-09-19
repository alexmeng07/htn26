# Devpost draft

**⏰ Select all targeted prizes on Devpost before 2:00 PM EDT Saturday.**

Targeted: Hack the North Finalist · Huawei OMNI Live · OpenAI API (+ Codex) ·
Baseten · MLH ElevenLabs · MLH MongoDB Atlas · MLH GoDaddy Registry.

## Inspiration
_TBD_

## What it does
_TBD_

## How we built it
_One paragraph per sponsor, explaining its real job — not a checkbox._

- **Huawei OMNI (Qwen3.5-Omni)** — acting is audio *and* visual. Our judge has
  to watch your face, read your body and hear your voice at the same moment. A
  single-modality model literally can't grade it. OMNI writes the reference
  sheet once per scene, then compares character and player side-by-side every
  round. _Bonus: reference sheet cached; raw takes deleted after scoring;
  optional in-browser face/pose tracking on the edge._
- **Baseten** — hosts SAM 2 (packaged with Truss) to cut the target character
  out of any movie clip. Real-time judging on the laptop, heavy video
  segmentation on Baseten GPUs.
- **OpenAI** — writes three judge personas and their reactions with structured
  output, always consistent with votes decided in code. Codex built the judges
  module and its tests.
- **ElevenLabs** — three designed judge voices, streamed; cached sound effects;
  the voice-changer dub replay.
- **MongoDB Atlas** — scene packs, round results and a live leaderboard via
  change streams.
- **GoDaddy Registry** — the domain.

## Challenges we ran into
_TBD_

## What we learned
_TBD_

## What's next
_TBD_
