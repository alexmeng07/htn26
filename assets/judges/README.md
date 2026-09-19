# Judge sprites

One folder per judge: `assets/judges/<judge_id>/`

**Four images each, named exactly:** `idle.png`, `talking.png`, `yes.png`, `no.png`

- PNG, transparent background.
- Same canvas size for all four states of a judge, and ideally across all three
  judges (e.g. 512x512), so swapping states doesn't make them jump.
- `judge.json` alongside them: display name, category, the env var holding their
  ElevenLabs voice ID, and a one-line persona for the OpenAI prompt.

**How four images become an animation**

| State | Animation |
|---|---|
| Idle | gentle up-and-down "breathing" bob |
| Talking | swap `talking` / `idle` a few times a second while the voice plays (reads as lip-flap) |
| Deliberating | idle images leaning toward each other with a small whisper wobble |
| Yes / No | quick scale-pop + ding or buzzer, then hold `yes` or `no` |

The three personas are **original characters**. Don't impersonate real
talent-show judges by name or voice.
