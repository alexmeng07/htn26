# SceneStealer

**Can you out-act the movies?**

You perform one character from a real movie scene. The character is cut out of
the film and played back beside your live camera. When the scene ends, a
multimodal model watches *and listens* to both of you, and a panel of three
animated judges gives you funny feedback and a YES or NO. Three YESes and
you're going through.

Built at **Hack the North 2026**.

---

## How it works

Two pipelines. The heavy work happens once, so the live game stays fast.

**① Scene Prep** *(once per scene)* — trim the shot with ffmpeg → isolate the
target character with **SAM 2 on Baseten** → pick 6–10 key moments → have
**OMNI** write a reference sheet describing the character's face, body and voice
at each one → save a **scene pack**.

**② Live Round** *(every play)* — record the player in sync with the clip →
ffmpeg merges character and player into one side-by-side video → **OMNI** scores
face, body and voice against the reference sheet → **plain code** applies the
thresholds and decides the votes → **OpenAI** writes three judge reactions that
match those votes → **ElevenLabs** speaks them → verdict screen.

The vote is decided in code, never by a model: the same performance must always
get the same result.

---

## Setup

**Prerequisites:** [uv](https://docs.astral.sh/uv/), Node 20+, pnpm, ffmpeg.

```bash
git clone <repo> && cd htn26
cp .env.example .env        # then fill in the keys (see below)
make setup                  # Windows: .\tasks.ps1 setup
```

Put your clip at `assets/private/<scene_id>/raw.mp4`, describe it in
`scenes/<scene_id>/scene.yaml` (copy `scenes/_template/scene.yaml`), then:

```bash
make prep SCENE=<scene_id>  # Windows: .\tasks.ps1 prep -Scene <scene_id>
```

## Run

```bash
make dev                    # Windows: .\tasks.ps1 dev
```

API on <http://127.0.0.1:8000>, web app on <http://localhost:5173>.
`make check` reports which services are configured and whether the active scene
pack has been built.

## Test

```bash
make test                   # pytest + vitest
make lint                   # ruff + tsc
```

---

## Environment variables

Every key lives in `.env` (gitignored); `.env.example` documents them all.
`GET /health` tells you which ones are still missing.

| Variable | Needed for | Where it comes from |
|---|---|---|
| `OMNI_BASE_URL`, `OMNI_API_KEY`, `OMNI_MODEL`, `OMNI_MODEL_DEV` | Scoring the performance | yibuapi credit email (one application per team) |
| `OPENAI_API_KEY`, `OPENAI_MODEL_JUDGES` | Judge dialogue | platform.openai.com |
| `ELEVENLABS_API_KEY`, `VOICE_JUDGE_FACE/BODY/VOICE` | Judge voices, SFX, dub | elevenlabs.io — voice IDs from Voice Design |
| `BASETEN_API_KEY`, `SAM2_ENDPOINT_URL` | Character isolation (prep only) | baseten.co, after deploying the Truss |
| `MONGODB_URI`, `MONGODB_DB` | Scene packs, results, leaderboard | MongoDB Atlas |
| `ACTIVE_SCENE`, `DEFAULT_THRESHOLD` | Which scene is loaded | you |

---

## Swapping the scene

Nothing in the code knows which movie is in play. The movie title, character,
briefing, tips, thresholds, key moments and dub voice all live in the **scene
pack** (`scenes/<scene_id>/`). To change scenes: write a new `scene.yaml`, run
`make prep`, point `ACTIVE_SCENE` at it. No code changes.

Real movie clips stay in the gitignored `assets/private/` folder and are used
for the live demo only.

---

## Layout

```
prep/            Scene Prep pipeline (run once per scene)
infra/truss/     SAM 2 packaged for Baseten
server/          FastAPI: compare · rules · judges · voice · store · round
web/             React stage: screens, sprites, camera capture
scenes/          One folder per scene — the only place scene details live
assets/          Judge sprites, cached SFX, fallback lines, private clips
docs/            Codex log, Devpost draft
```

See `HANDOFF.md` for the full design, sponsor tracks and build plan.
