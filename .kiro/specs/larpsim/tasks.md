# LARPsim — Implementation Plan

**Spec:** `larpsim` · **Requirements:** `./requirements.md` · **Design:** `./design.md`

Budget: 16 hours. Ordered so a demoable round exists as early as possible and later phases add polish
rather than risk. Lane labels mark work that can proceed in parallel once phase 1 lands.

**How to read a task.** Each one states the thing to build and, where it is checkable, the condition
that makes it done. Major tasks carry a **Not:** line — the thing we explicitly decided against. A
**Not:** line is as binding as the task itself; doing the forbidden thing is a failed task even if the
feature works.

Numbers written as `(default N, tune in 6.7)` are starting values chosen so the code has one obvious
constant instead of a magic number. They are meant to be tuned. Numbers without that marker come
from the requirements, the scene pack, or existing code and are not free to change.

---

## Phase 0 — Runnable baseline · P0 · **complete**

- [x] 0.1 Install uv and Node without elevation; put both on the user PATH
  - The winget Node MSI stalls on an unanswerable UAC prompt; portable zip used instead
  - `.kiro/scripts/add-tools-to-path.ps1`
  - _Requirements: R1.1, R1.2_
- [x] 0.2 Install Python dependencies into a Python 3.11 venv
  - _Requirements: R1.1_
- [x] 0.3 Install pnpm into a user-writable npm prefix (Corepack fails with EPERM in Program Files)
  - `.kiro/scripts/setup-pnpm.ps1`
  - _Requirements: R1.2_
- [x] 0.4 Confirm pytest (16 passed) and ruff (clean)
  - _Requirements: R1.3_
- [x] 0.5 Confirm pnpm install (182 packages), tsc, and vitest (4 passed)
  - _Requirements: R1.3_
- [x] 0.6 Confirm `GET /health` returns 200 and names the three missing voice IDs
  - `.kiro/scripts/verify-health.ps1`
  - _Requirements: R1.4_

---

## Phase 1 — Rename and restructure (~1.5 h) · P0 · blocks all lanes

**Rail for the whole phase:** `uv run pytest -q` passes with **zero edits to any test file**. A test
that needs changing means the restructure overreached — revert, don't adapt the test.

- [x] 1.1 Rename the product to LARPsim on user-visible surfaces: the `Title` screen heading,
      `frontend/index.html` `<title>`, the `README.md` H1, and the spec and docs headings
  - Done when: `git grep -i scenestealer` returns hits **only** in Python module paths, env var
    names, `MONGODB_DB`, `pyproject.toml` `name`, and prose describing project history
  - **Not:** do not rename the `server`/`prep` packages, any module path, any `*_API_KEY` or other env
    var name, `MONGODB_DB=scenestealer`, the repo directory, or the `scenestealer` project name in
    `pyproject.toml`. Renaming those breaks working credentials and configuration for zero benefit
    (**I8**)
  - _Requirements: R2.1, R2.2, R2.4, I8_
- [x] 1.2 Confirm `uv run pytest -q` (16 passed) and `GET /health` (200) after the rename, proving no
      internal identifier moved
  - _Requirements: R2.3_
- [x] 1.3 Split the repo into `backend/` (`server/` · `prep/` · `scripts/` · `tests/`) and
      `frontend/`, leaving `scenes/` and `assets/` shared at the top level
  - Done when: `backend/server/` still contains `compare/`, `rules/`, `judges/`, `voice/`, `store/`,
    `round/`, `media/` at those exact paths, and no import statement anywhere changed
  - **Not:** do not introduce `api/`, `services/`, `domain/`, or `adapters/` packages. Do not add
    `server/app.py` or split `main.py` into routers. Do not move `schemas.py`, `scene.py`,
    `config.py`, or `rules/votes.py`. Do not turn either half into a separately deployed service.
    The split is folders and ownership only; the layering was considered and rejected because it
    would move every file and break every import to buy nothing a 16-hour demo can spend
  - _Requirements: R3.1, R3.5, R3.6, I7_
- [x] 1.4 Keep the Python project root (`pyproject.toml`, `uv.lock`, `.venv`) at the repo root: one
      venv for the repo
  - Concretely: `pythonpath = ["backend"]` and `testpaths = ["backend/tests"]` for pytest,
    `src = ["backend"]` for ruff, `ROOT = Path(__file__).resolve().parents[2]` in `server/config.py`
    and `scripts/fetch_models.py` so `.env`, `scenes/` and `assets/` still resolve to the repo root
  - **Not:** do not give `backend/` its own `pyproject.toml` or its own `.venv`, and do not move
    `.env`, `scenes/`, or `assets/` under `backend/`. The frontend fetches judge sprites and keypoint
    models out of `assets/` over HTTP; burying them would make it reach across the split for its own
    files
  - _Requirements: R3.1_
- [x] 1.5 Keep `FORCE_FALLBACK` (already in `server/config.py`) as the single no-credentials switch
  - **Not:** do not build an interface-plus-fake pair per external system. Each module owns its own
    fallback beside the real call, the way `compare/fallback.py` already does
  - _Requirements: R3.3_
- [x] 1.6 Keep every existing import path working: `server.main:app`, `server.rules.votes`,
      `server.scene`, `server.schemas`
  - Verified: 16 pytest passed, ruff clean, real uvicorn `GET /health` 200 under
    `uvicorn --app-dir backend server.main:app`
  - _Requirements: R3.5_
- [x] 1.7 Document the layout and where each lane works: `README.md` "Layout", `HANDOFF.md` §9
  - _Requirements: R3.7_
- [~] 1.8 Correct `README.md`, `Makefile`, and `tasks.ps1` on the *toolchain*: portable-zip Node, the
      user-writable npm prefix for pnpm, and that no step needs elevation
  - Path updates for the `backend/`+`frontend/` split are already done; the toolchain notes are not
  - Done when: the setup section matches what actually happened in 0.1–0.3
  - _Requirements: R1.5, R16.1_

---

## Already satisfied — no task needed

Recorded so these requirements are visibly covered rather than silently skipped.

- **R8.1, R8.3, R8.4, R8.5** — the vote rules are implemented in `backend/server/rules/votes.py` and
  covered by `backend/tests/test_votes.py`: per-category threshold comparison, all-three-YES to pass,
  `GOLDEN_BUZZER_SCORE = 90`, and a deterministic tally. **Do not rewrite this module.** It is the one
  place **I2** lives, and it already works
- **R8.2** is the exception: thresholds come from the pack, but the *values* still need tuning — task
  6.7

---

## Phase 2 — Grading domain (~3 h) · P0 · Lane G

Pure logic. No clip needed, no network, no credentials. The largest unknown, so it goes first.

**Rail for the whole phase:** every function here is importable and testable with no camera, no
network, no credentials, and no video file. If a test needs a fixture video, the logic is in the wrong
place — move the I/O to Phase 3.

- [x] 2.1 Confirm MediaPipe installs on Python 3.11 Windows and pin the dependencies and models
  - Verified: `mediapipe 1.0.1`, `numpy 2.4.6`, `opencv-contrib-python 5.0.0.93`, no JAX. Deliberately
    did **not** add `opencv-python`, since mediapipe already supplies `cv2` via the contrib package
    and two providers of the same module conflict
  - Models pinned at v1 and cached in gitignored `assets/models/`: `pose_landmarker_full.task`
    (9.4 MB) and `face_landmarker.task` (3.8 MB), fetched by `backend/scripts/fetch_models.py`
  - Both landmarkers construct and run on CPU via the XNNPACK delegate; a grey frame yields zero
    detections without raising, which is the no-person path R6.8/R6.9 depend on
  - Existing 16 tests still pass after the dependency addition
  - `.kiro/scripts/setup-grading.ps1`, `.kiro/scripts/_probe_landmarkers.py`
  - **Design risk #1 is retired**; the browser-side reference-extraction fallback is not needed
  - _Requirements: R6.4_
- [x] 2.2 Add keypoint timeline models to `server/schemas.py`: one sample = timestamp in seconds since
      take start, 33 pose landmarks each with `x, y, z, visibility`, and the face blendshape
      coefficients as a name→float map. A timeline is an ordered list of samples plus the source fps
  - **Not:** do not add a new report type and do not change `ComparisonReport`, `CategoryScore`,
    `JudgeVote`, `Verdict`, or `RoundResult`. Grading's output *is* the existing `ComparisonReport`,
    so the voice path and the grading path stay interchangeable. Additions only (**I7**)
  - _Requirements: R5.5, R6.4, I7_
- [x] 2.3 Determine the **comparison scope** per reference frame: the set of pose landmarks whose
      `visibility` clears a threshold (default 0.5, tune in 6.7). This set, taken from the
      *reference*, is the only thing graded in that frame
  - Parts the reference does not show are excluded. Parts the player shows but the reference does not
    are ignored. A player further back with their whole torso in shot is neither penalised nor
    rewarded for it
  - **Not:** do not derive the scope from the player, or from the intersection of both sides. If the
    player could shrink the scope by leaving frame, stepping out of shot would become a way to raise
    the score. The scope is a property of the scene, identical for every player and every attempt
  - _Requirements: R6.7_
- [x] 2.4 Derive the scope's measures, each carrying a confidence equal to the minimum `visibility` of
      its contributing landmarks. Full-body scope: elbow, shoulder, hip, knee, neck and torso-lean
      angles. Head-and-shoulders scope: shoulder-line roll, neck flexion, head yaw from ear/nose
      offsets, head roll, shoulder-to-head distance, torso lean where any torso shows, and
      forward/back head position
  - Every measure is an angle or a ratio between points *inside* the scope, so all are translation-
    and scale-invariant by construction (R6.2)
  - Record the count of measures actually used and put it in the report, so a thin-evidence round is
    visible rather than silent (R6.15)
  - **Not:** do not collapse a small scope to one coarse signal. A close-up still yields six or seven
    measures; grading it on shoulder tilt alone would make the score a measure of head angle rather
    than of performance. Do not compare raw landmark coordinates, pixel distances, or bounding boxes
    anywhere in the scoring path
  - _Requirements: R6.2, R6.7, R6.15_
- [x] 2.5 Score pose similarity over the scope: confidence-weighted mean absolute difference across its
      measures, mapped to 0–100 by `100 * (1 - error / MAX_ERROR)` clamped to `[0, 100]`, with
      `MAX_ERROR = 60°` (default, tune in 6.7) as one named constant
  - **Not:** do not call any model, local or remote, in this function. Face and body scores are
    geometric and deterministic; a language model must never touch them (**I3**)
  - _Requirements: R6.1, R6.2_
- [~] 2.6 Keep framing out of the pose score. If a framing signal is wanted, compute it separately —
      player subject scale versus the reference's — expose it as its own small, labelled adjustment,
      and cap it so it cannot flip a vote alone
  - Preferred implementation is a framing nudge on the `Ready` screen *before* the take, not a
    deduction after it: it tells the player something they can still act on
  - **Not:** do not fold distance or framing into the angle comparison. R6.2 requires a correct pose at
    a different distance to score the same; a baked-in distance penalty reintroduces exactly the
    failure scale invariance exists to prevent
  - _Requirements: R6.2, R6.14_
- [x] 2.7 Score facial similarity from blendshape coefficients, weighting expressive channels above
      incidental ones: brow (`brow*`), eye squint (`eyeSquint*`), jaw (`jaw*`), and mouth
      (`mouth*`) at weight 1.0; blinks (`eyeBlink*`) and gaze direction (`eyeLook*`) at weight 0.1
      (defaults, tune in 6.7), since a blink or a glance is timing noise, not acting
  - **Not:** do not compare raw facial landmark positions. Blendshapes are person-invariant; landmark
    positions encode face shape, so a different face making the identical expression would score
    badly (R6.3)
  - _Requirements: R6.1, R6.3_
- [x] 2.8 Align in time with a tolerance window: for each reference sample, score against the
      best-matching player sample within ±250 ms (default, tune in 6.7) rather than requiring exact
      frame alignment. One named constant, used by both face and body
  - **Not:** do not attempt global time-warping or drift correction. R5.1 starts the clip and the
      recorder on the same tick, so the only error to absorb is jitter
  - _Requirements: R6.5_
- [x] 2.9 Aggregate into a `ComparisonReport`: drop reference samples with no detection, weight samples
      within ±250 ms of a key moment at 3× (default, tune in 6.7), emit the per-moment notes, and set
      `best_moment` and `worst_moment` to the highest- and lowest-scoring key moments
  - Set `player_not_visible` when fewer than 60% of player samples contain a detected person; set
    `player_silent` when voiced audio covers under 20% of the take (defaults, tune in 6.7)
  - **Not:** do not let an excluded frame count as a zero. A frame where the *character* is off-screen
    is not a player failure, and scoring it as one would punish the player for the film's editing
    (R6.8)
  - _Requirements: R6.6, R6.8, R6.9, R6.10, R6.11_
- [x] 2.10 Unit-test comparison against hand-built synthetic timelines: identical (expect 100),
      mirrored, uniformly scaled (expect near-identical to the unscaled case, proving R6.2),
      time-shifted inside the tolerance (expect near-identical) and outside it, partially visible,
      and empty
  - Add the scope cases explicitly: a reference with only head and shoulders visible must grade on
    head and shoulders; a player with extra parts visible must score the same as one without them;
    and a player who leaves frame must not score *better* than one who stays in it
  - Every test here runs with no video file, no credentials, and no network, which is what proves R3.4
  - **Not:** do not use a video file in these tests. A generated fixture contains no human, so no
    landmarker detects anything in it; synthetic timelines are stronger evidence and keep every unit
    test free of copyrighted media (**I5**, decision D1 tier 2)
  - _Requirements: R3.4, R6.2, R6.3, R6.7, R6.12_
- [x] 2.11 Assert determinism: the same timelines and pack scored twice produce byte-identical face and
      body scores, across at least 5 repeats
  - Also record the wall-clock time for a 10.4 s take: it must be a small fraction of the 8 s round
    budget and must involve no network call (R6.13)
  - _Requirements: R6.12, R6.13, I3_
- [x] 2.12 Expose `POST /grade/compare`: two keypoint timelines plus a scene id in, a
      `ComparisonReport` out, so the lane is drivable with curl before any camera exists
  - **Not:** do not put scoring logic in the route. It calls the same function `round/pipeline.py`
    calls, so the standalone path cannot drift from the composed one
  - _Requirements: R3.2_

---

## Phase 3 — Keypoint extraction and prep (~2 h) · P0 · Lane A

- [x] 3.1 Extract reference pose and face over the trimmed clip in Python, cached as a discrete prep
      artifact so re-running prep skips it
  - _Requirements: R4.6, R4.2_
- [x] 3.2 Sample the player live in the browser during the take, timestamped against the same clock
      as the recording, and upload the timeline with the take
  - **Not:** do not timestamp from `Date.now()` or wall clock. It must be the recording clock, or
    sample *t* stops meaning reference *t* and the whole alignment assumption (R5.1) collapses
  - **Amended 2026-09-19:** the clock is the *character video's* `currentTime`, not the recorder's
    elapsed time. Found in the parity check (3.4): playback stalled ~0.5 s over a 10.4 s clip, so
    elapsed-time stamps drifted off the reference and the same clip scored face 40 / body 53. The
    player copies what they see, so the video's own position is the true shared clock. After the
    change: 96 / 97, stable over 3 runs
  - _Requirements: R5.4, R5.5_
- [x] 3.3 Implement server-side player extraction as the fallback when the browser cannot sample,
      calling the same comparison code as the browser path
  - _Requirements: R5.8_
- [x] 3.4 Parity-test Python and browser extraction on the same input: same model files, same
      normalisation, and a resulting category score within 2 points on the 0–100 scale
  - **Not:** do not let the two paths use different model versions or different normalisation. The
    models are pinned at v1 in `assets/models/` for exactly this reason (R6.4)
  - Verified 2026-09-19 (manual, in Chrome): the reference clip sampled in the browser (GPU delegate,
    full frame) grades 96 face / 97 body against the Python reference (CPU, cropped); the Python
    server path on the same clip grades 95 / 97. Within 2 points. Not yet an automated test
  - _Requirements: R6.4_
- [x] 3.5 Select 6–10 key moments from the keypoint timeline by largest pose or expression change,
      spread across the clip; when the duration supports fewer than 6, take what it supports and warn
  - **Not:** do not fail prep on a short clip, and do not pad with evenly spaced filler moments
  - _Requirements: R4.7, R4.8_
- [x] 3.6 Resolve the clip tolerantly: the configured filename first, then the single video file in the
      scene's private directory if the configured name is absent, printing loudly that it substituted.
      When nothing is found, fail immediately naming the exact expected path and any near misses
  - _Requirements: R4.4, R4.5_
- [~] 3.7 Generate a rights-clean fixture clip with ffmpeg for media plumbing only: 1280×720, 30 fps,
      10.4 s, written to its own gitignored scene directory with a matching `scene.yaml`
  - Use it to exercise trim, side-by-side construction, duration and dimension handling, and the
    media routes. Its *lack* of a detectable person is the test for the no-person paths R6.8/R6.9
  - Confirms the existing `prep/trim.py` normalises height and frame rate and cuts to the configured
    start and end (R4.3)
  - **Not:** do not write it over `assets/private/test-scene-1/test_clip_1.mp4` — the real clip is now
    there. Do not use it to validate grading quality; it contains no human to detect
  - _Requirements: R4.3, D1_
- [x] 3.8 Build the reference sheet with one multimodal call for the whole clip, cached so re-running
      prep does not repeat it; on failure write empty prose and continue
  - **Not:** do not call per key moment, and do not fail prep when the call fails. The sheet gives the
    judges quotable specifics; its absence costs flavour, not a round
  - _Requirements: R4.9, R4.10_
- [~] 3.9 Implement MongoDB access in `store/db.py`: lazy client, short connect timeout, pack upsert,
      result upsert with a local JSON mirror, leaderboard aggregation with local fallback
  - **Not:** do not let an unreachable MongoDB fail prep or fail a round. It warns and mirrors locally
    (R4.12, R14.3)
  - _Requirements: R4.11, R4.12, R14.1, R14.2, R14.3_
- [x] 3.10 Assemble the pack: validate against the scene-pack model, record duration and a prepared-at
      stamp, upsert. Run the segmentation stage last and treat failure as non-fatal
  - **Not:** do not make any scored field depend on segmentation output. Masks feed the replay overlay
    only, and a segmentation failure cannot change a verdict (**I9**)
  - _Requirements: R4.1, R4.11, R4.14, I9_
- [x] 3.11 Run prep end to end on the fixture scene; confirm `GET /scene` serves the resulting pack
  - _Requirements: R4.1_
- [x] 3.12 Run prep on `assets/private/test-scene-1/test_clip_1.mp4` (present as of 2026-09-19) and
      confirm extraction finds a person in the `[227, 0, 1160, 720]` region across the 10.4 s, and
      that the selected key moments land on visible expression changes
  - This is the first time grading meets real footage; it is the checkpoint for grading quality
  - _Requirements: R4.6, R4.7_

---

## Phase 4 — One full round (~3 h) · P0 · Lanes C, D, E

- [~] 4.1 Smoke-test the paid services before anything depends on them: multimodal
      describe-and-listen, structured judge output, speech and voice design, MongoDB, and SAM 2.
      Record the working payload shapes and the measured latencies
  - **Not:** do not build against a guessed payload shape. Confirm the wire format first
  - _Requirements: R7.2, R9.1, R10.1, R14.1_
- [x] 4.2 Implement the voice comparison in `compare/omni.py`: build the side-by-side video — character
      left, player right, frame-synced, carrying the player's audio only — then one multimodal call
      that receives the pack's reference sheet, validate the reply against `ComparisonReport`, retry
      once on malformed output, abandon and fall back past an 8 s budget, and switch between
      `OMNI_MODEL_DEV` and `OMNI_MODEL` by env var
  - Keep the per-moment qualitative notes from the reply; the judges need them for specificity (R7.5)
  - **Not:** do not let this call set `face` or `body` — take only `voice` and the qualitative notes
    from it. Those two are already scored geometrically in Phase 2, and overwriting them would
    destroy determinism (**I3**, R7.9). Do not exceed one call per round; the credit cap is 40 CAD.
    Do not put the scene audio on the side-by-side track — the player's microphone only
  - _Requirements: R7.1, R7.2, R7.3, R7.4, R7.5, R7.6, R7.7, R7.8_
- [x] 4.3 Implement the local voice estimate used when the model is unavailable: derive a 0–100 score
      from the take's own audio envelope — voiced ratio, energy variance, and timing against the key
      moments — with no network
  - **Not:** do not return a fixed number or a random one. A constant makes every fallback round
    identical and the fallback obvious on stage
  - _Requirements: R15.2_
- [~] 4.4 Implement judge writing in `judges/writer.py`: one structured call for all three judges, the
      prompt stating each vote as already-decided fact, validated against `JudgeLines`, plus a
      sentiment check that a NO does not read as praise, retried once
  - **Not:** do not ask the model to decide or revise a vote, and do not send it the raw thresholds to
    reason about. Code decides; the model only reacts to what it is handed (**I2**)
  - _Requirements: R9.1, R9.2, R9.3, R9.4, R9.5, R9.6_
- [x] 4.5 Write and commit pre-written lines for every judge × vote × band, and implement selection as
      a pure tested function. Bands: NO far-below (score < threshold − 15), NO near-miss
      (≥ threshold − 15), YES pass (< 90), YES golden (≥ 90, matching `GOLDEN_BUZZER_SCORE`) — 3
      judges × 4 bands = 12 lines minimum, in `assets/fallback/`
  - These are also what the line writer falls back to when it is unavailable (R15.3)
  - **Not:** do not generate these at runtime. They exist so a dead network still produces a show
    (**I6**)
  - _Requirements: R9.7, R9.8, R15.3_
- [x] 4.6 Synthesise speech with the first judge awaited and judges two and three generated
      concurrently, so the reveal can start before all three are ready
  - When synthesis fails, the verdict still plays from speech bubbles plus the cached sound effects
    from 4.8 (R10.5, R15.4)
  - **Not:** do not block the reveal on all three voices, and do not let a synthesis failure abort the
    verdict. The show is degraded silently, never cancelled
  - _Requirements: R10.1, R10.2, R10.5, R15.4_
- [x] 4.7 Design the three judge voices from text descriptions, store the IDs in `.env`, and confirm
      `GET /health` reports no missing credentials
  - **Not:** do not clone the actor's voice or any real person's voice. Designed from description
    only (**I4**)
  - _Requirements: R10.3, R10.6, I4_
- [x] 4.8 Generate the sound-effect set once — drumroll, YES, NO, applause, golden buzzer — and cache
      it in `assets/sfx/` so playback needs no further calls
  - _Requirements: R10.4_
- [x] 4.9 Implement `round/pipeline.py` in this order: grading first (local, no network), then
      side-by-side, voice, tally, lines, speech. Log per-stage timing. Delete the raw take when
      `DELETE_TAKES_AFTER_SCORING` is set and the replay was not kept
  - Any unrecoverable stage failure emits an `error` event so the stream always terminates (R11.7)
  - **Not:** do not put grading behind the network call. Grading first means a dead network still
    yields real face and body scores, which is what makes the offline round (**I6**) more than a
    stub. Do not let a failure leave the SSE stream open with the client spinning
  - _Requirements: R11.1, R11.2, R11.4, R11.5, R11.7, R11.8_
- [x] 4.10 Accept the take plus its keypoint timeline on `POST /rounds/{id}/take` (currently 501),
      return promptly, run the pipeline in the background, and add the static mounts for round audio
      and judge assets
  - Close the client half too: recording stops when the character video ends and the take uploads
    immediately (R5.2), carrying camera and microphone only
  - **Not:** do not score synchronously inside the request. The client is waiting on the SSE stream.
    Do not capture the scene audio into the take — it would leak the film's other voices into the
    voice score (R5.3)
  - _Requirements: R5.2, R5.3, R5.5, R11.1_
- [~] 4.11 Integration-test the pipeline under `FORCE_FALLBACK=1`: assert the event order
      `judging` → `verdict_ready` → `dub_ready`, a complete `RoundResult`, and identical scores across
      repeated runs
  - _Requirements: R11.2, R11.3, R6.12_
- [~] 4.12 Play one real round end to end and record the measured wait from take-end to first judge
      speaking; target ≤ 8 s, the span the deliberation animation covers
  - **Not:** do not assume the timing. R11.4 asks for a measured number written down
  - Measured 2026-09-19, one live round, server-side keypoints: take-end -> verdict 23.5 s
    (grading 4.6, side-by-side 0.8, OMNI voice 11.5, lines 6.2 [OpenAI out of credits], voices 0.3).
    Since then: side-by-side cut to 360p/10fps (OMNI 10.8 s -> 7.1 s, same score); browser
    keypoints remove the 4.6 s. Expected ~10 s -- still over the 8 s target; OMNI is the floor
  - _Requirements: R11.4_

---

## Phase 5 — The show (~2 h) · P0 · Lane B

- [x] 5.1 Generate placeholder judge sprites and document the drop-in contract: `assets/judges/<id>/`
      holding `idle.png`, `talking.png`, `yes.png`, `no.png`, all transparent PNG at one shared canvas
      size (512×512), plus the existing `judge.json`
  - Done when: replacing the placeholder files with real art needs no code change (R12.4)
  - **Not:** do not hardcode per-judge image paths or sizes in components. The four names and one
    canvas size are the contract
  - _Requirements: R12.3, R12.4_
- [~] 5.2 Build `Briefing` and `Ready`, including the headphone gate that blocks the countdown until
      confirmed when the pack sets `other_voices_in_audio`
  - _Requirements: R5.6, R12.7_
- [~] 5.3 Handle denied camera or microphone permission on `Ready` with a recoverable error: say which
      device was refused, how to re-grant it, and offer retry without reloading the app
  - **Not:** do not let a denied permission dead-end the player or crash into the countdown. This is
    the single most likely failure when a stranger plays at a booth
  - _Requirements: R5.7_
- [x] 5.4 Build `Deliberation`: dimmed stage, conferring sprites, drumroll, subscribed to the round
      event stream
  - _Requirements: R12.1_
- [x] 5.5 Build `Verdict`: judges revealed one at a time — talking animation, speech bubble, their
      audio, then the YES or NO image and its sound effect
  - _Requirements: R12.2_
- [x] 5.6 Build `Result`: celebration on pass, the distinct golden-buzzer variant, and Try Again
      showing the tip from a judge who voted NO
  - _Requirements: R11.6, R12.5, R12.6_
- [~] 5.7 Draw the live skeleton overlay during the performance
  - **Not:** do not feed the overlay's samples into scoring, and do not gate the round on it
    rendering. It is for feel only (R5.9)
  - _Requirements: R5.9_
- [~] 5.8 Extend the hardcoded-scene guard in `backend/tests/test_scene.py` to cover `frontend/src/`,
      so a film title, character, actor, or line committed into a screen fails the suite
  - Every scene-specific string comes from the pack served by `GET /scene`
  - **Not:** do not leave this as a manual read-through. It is a test, or it rots (**I1**)
  - _Requirements: R12.7, I1_

---

## Phase 6 — Survive anything (~1.5 h) · P1

- [x] 6.1 Wire `FORCE_FALLBACK` so one env var makes every external call take its local path, and a
      complete round runs from local assets
  - **Not:** do not add a second switch or per-service flags. One switch, checked in one place per
    module
  - _Requirements: R15.1_
- [~] 6.2 Show the light-hearted fallback notice when `RoundResult.fallback_used` is set
  - _Requirements: R15.5_
- [~] 6.3 Handle the no-headphones path: mute the scene audio for the take and show subtitles
  - _Requirements: R15.7_
- [~] 6.4 Prep a second scene, flip `ACTIVE_SCENE`, and confirm every scene-specific string and media
      path changes with **no code edit**
  - This is the acceptance test for **I1**; a single required code change is a failure
  - _Requirements: R4.13, I1_
- [~] 6.5 Break segmentation deliberately and confirm face, body, voice, the votes, and the verdict are
      byte-identical to the working run
  - _Requirements: R13.4, I9_
- [~] 6.6 Run the offline rehearsal: network adapter disabled, one complete round start to finish
  - **Not:** do not substitute "mocked network" for this. Requirement R15.6 means the adapter is
    actually off (**I6**)
  - _Requirements: R15.6, I6_
- [~] 6.7 Tune the thresholds and every `(default N, tune in 6.7)` constant above toward a 30–50%
      first-time pass rate, and write the final values into `scenes/test-scene-1/scene.yaml` and the
      named constants
  - Includes the scope visibility threshold (2.3), `MAX_ERROR` (2.5), the framing cap (2.6), the
    blendshape channel weights (2.7), the ±250 ms window (2.8), and the key-moment 3× and flag
    percentages (2.9)
  - Watch the **body** score distribution specifically: if it clusters above its threshold on nearly
    every take, the body judge is rubber-stamping and the three-judge show is really a two-judge show.
    That is the signal that design risk #3 has bitten and a wider shot is worth the re-prep
  - **Not:** do not tune by editing scores or adding per-player adjustments. Thresholds and constants
    only
  - _Requirements: R8.2_

---

## Phase 7 — Extras and write-ups (~1.5 h) · P2

Dropped before anything above is weakened, and recorded here as dropped with a reason if so.

- [x] 7.1 Produce the replay with the player's audio transformed into a voice designed from the pack's
      `dub_voice_style`, generated in parallel with judging, emitting `dub_ready` on success or failure
  - **Not:** do not let replay work delay or block the verdict (R13.2)
  - _Requirements: R13.1, R13.2, R13.5_
- [x] 7.2 Composite the player into the scene where masks exist, falling back to side-by-side
  - Done 2026-09-19: `server/media/composite.py`. Player cut out with the pose model's segmentation
    mask (no per-round SAM 2), the character painted out of the frame (low-res inpaint), the player
    fitted to the character's outline and colour-matched; ~17 s for 10.4 s, after the verdict
  - _Requirements: R13.3_
- [x] 7.3 Build the `Dub` and `Leaderboard` screens, the leaderboard updating without a manual reload
  - _Requirements: R13.5, R14.2, R14.4_
- [~] 7.4 Correct `HANDOFF.md` where it contradicts this spec: the scene is chosen, grading is
      geometric rather than model-scored, and segmentation is cosmetic
  - _Requirements: R16.2_
- [~] 7.5 Write the per-sponsor paragraphs honestly — naming the specific job each technology does —
      and update the agent log
  - **Not:** do not claim segmentation affects scoring or that grading is multimodal. Both are false
    and both are checkable from the repo
  - _Requirements: R16.3, R16.4_
- [~] 7.6 Confirm no credential and no clip is in git history; record the source and licence note in
      the pack
  - _Requirements: R16.5, R16.6, I5_

---

## Reserve (~1.5 h)

- [~] 8.1 Feature freeze
- [~] 8.2 Rehearse end to end
- [~] 8.3 Record a backup video

---

## Execution notes

- Tasks are checked off when their stated condition holds, not when code is written.
- A **Not:** line is binding. It records a decision already made, usually after considering the
  alternative. Re-litigate it in the spec, not in the code.
- Phase 1 is a refactor with a hard rail: the existing test suite passes **unchanged** throughout. A
  test that needs editing means the refactor overreached.
- Anything dropped for time is marked dropped here with a reason. Silent omission is not acceptable.
- `test_clip_1.mp4` has arrived, so nothing is blocked on it. Task 3.12 is now runnable, and it is the
  first real check on grading quality.
- Environment quirk: the PowerShell tool mangles long commands and truncates progress output.
  Multi-step shell work goes in a script under `.kiro/scripts/` that logs to an absolute path, run in
  the background, then read back. Tooling workaround, not a project convention.
