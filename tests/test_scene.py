"""Scene packs must be swappable, and scene details must live in exactly one place."""

import re
import subprocess

import pytest

from server.config import ROOT
from server.scene import load_config, load_pack

# Paths allowed to name a movie, character or actor: the scene packs
# themselves, the private clip folder, and prose. Plus this guard, which has
# to spell the terms out in order to search for them.

ALLOWED = (
    "scenes/",
    "assets/private/",
    "docs/",
    "HANDOFF.md",
    "README.md",
    "tests/test_scene.py",
)

# The worked example from HANDOFF.md. If any of these leak into code, the "swap
# the scene with no code changes" promise is already broken. Split so this
# file's own source does not contain the literals it searches for.
EXAMPLE_TERMS = ["Inter" + "stellar", "Coo" + "per", "McCon" + "aughey"]


def test_template_and_dev_scene_both_load():
    cfg = load_config("dev-clip")
    assert cfg.scene_id == "dev-clip"
    assert cfg.thresholds.face > 0


def test_pack_loads_from_config_before_prep_has_run():
    """The UI must boot on a scene that has not been prepped yet."""
    pack = load_pack("dev-clip")
    assert pack.character_name
    assert pack.isolated_video == ""  # not prepped; empty, not an error


def test_unknown_scene_raises_clearly():
    with pytest.raises(FileNotFoundError):
        load_config("no-such-scene")


@pytest.mark.parametrize("term", EXAMPLE_TERMS)
def test_no_scene_details_are_hardcoded(term):
    """Nothing scene-specific may appear in code, prompts, UI text or configs."""
    result = subprocess.run(
        ["git", "grep", "-lI", "-i", term],
        cwd=ROOT, capture_output=True, text=True,
    )
    leaked = [
        path
        for path in result.stdout.splitlines()
        if path and not any(re.match(rf"^{re.escape(prefix)}", path) for prefix in ALLOWED)
    ]
    assert not leaked, f"'{term}' is hardcoded in: {leaked}"
