# SAM 2 on Baseten (Truss)

Cuts the target character out of a movie clip so the player has something exact
to imitate. Runs **once per scene** during Scene Prep, never during a round.

## Files

```
config.yaml       GPU, pip/apt deps, cached weights
model/model.py    load() + predict()
```

## Deploy

```bash
pip install --upgrade truss          # or: uvx truss push
export BASETEN_API_KEY=...           # Baseten dashboard -> API keys
cd infra/truss/sam2
truss push --publish                 # newer CLIs: baseten model push
```

Copy the resulting URL into `.env`:

```
SAM2_ENDPOINT_URL=https://model-<model_id>.api.baseten.co/environments/production/predict
```

Use `/development/predict` plus `truss watch` while iterating — it hot-reloads
`model.py` without rebuilding the container.

## Contract

**In:** `video_b64` (the trimmed clip) + `box` *or* `point` marking the
character on the **first frame**.
**Out:** `isolated_b64` (character on a dark background), COCO-RLE `masks`,
a per-frame `visible` array, `fps`, `frame_count`, `size`.

Compositing happens on the GPU box, where the frames already live: one finished
mp4 plus RLE masks is a few MB, whereas shipping raw per-frame PNGs back would
be hundreds. Baseten caps a request body at **100MB**.

A 20-40s clip propagates in ~1-3 minutes, well inside Baseten's **20-minute**
synchronous timeout — so this is an ordinary request/response call. No async
endpoint, no webhooks.

`visible == false` marks a frame where SAM 2 found nothing: the film has cut
away from the character. Those frames are skipped when scoring, and the UI shows
"(hold your reaction)".

## Escape hatch

The same `model.py` runs anywhere with a GPU. If the Baseten deploy stalls, run
it on Colab and point the client at it:

```bash
uv run python -m prep.isolate_client --scene <id> --endpoint http://<host>/predict
```

Keep pushing the Baseten version for the prize.

## Before you build

Ask the booth (`#spons-baseten-2026` on Slack) for the promo credit code and
whether they have a known-good torch/CUDA pin — a mismatch there costs build
minutes. The HTN starter repo is README-only; it covers their hosted LLM API,
not custom Truss deploys, so there's no SAM example to crib from.
