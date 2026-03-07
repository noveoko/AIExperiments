#!/usr/bin/env python3
"""
mshort_cli.py — M-Short v2 End-to-End Pipeline
================================================
Converts a natural language request into a rendered multi-scene Manim video
using the M-Short semantic compression layer to minimise LLM decode latency.

Full pipeline
-------------
  User request
    → LLM (Claude) outputs M-Short code
      → Expansion Engine → valid Manim Python
        → Manim renders each scene → MP4 files
          → ffmpeg stitches scenes → final video

Requirements
------------
  pip install manim anthropic   (anthropic SDK optional, falls back to urllib)
  ANTHROPIC_API_KEY env var must be set

Usage
-----
  python mshort_cli.py "explain the Pythagorean theorem in 3 scenes"
  python mshort_cli.py "animate bubble sort" --scenes 4 --quality h
  python mshort_cli.py "show Fourier series" --dry-run --verbose
  python mshort_cli.py "show Fourier series" --map ./map.py  # custom MAP from ingestion
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import traceback
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Terminal output helpers (no rich required)
# ═══════════════════════════════════════════════════════════════════════════════

def _supports_color() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

_C = _supports_color()
RESET  = "\033[0m"  if _C else ""
BOLD   = "\033[1m"  if _C else ""
DIM    = "\033[2m"  if _C else ""
GREEN  = "\033[92m" if _C else ""
YELLOW = "\033[93m" if _C else ""
RED    = "\033[91m" if _C else ""
CYAN   = "\033[96m" if _C else ""
BLUE   = "\033[94m" if _C else ""

def step(n: int, total: int, msg: str) -> None:
    bar = f"[{n}/{total}]"
    print(f"\n{BOLD}{CYAN}{bar}{RESET} {msg}")

def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET}  {msg}")

def warn(msg: str) -> None:
    print(f"  {YELLOW}⚠{RESET}  {msg}", file=sys.stderr)

def err(msg: str) -> None:
    print(f"  {RED}✗{RESET}  {msg}", file=sys.stderr)

def info(msg: str) -> None:
    print(f"  {DIM}{msg}{RESET}")

def header(msg: str) -> None:
    print(f"\n{BOLD}{BLUE}{'─' * 60}{RESET}")
    print(f"{BOLD}{BLUE}  {msg}{RESET}")
    print(f"{BOLD}{BLUE}{'─' * 60}{RESET}")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Built-in Seed MAP (Pareto Core — top ~100 Manim API calls)
# ═══════════════════════════════════════════════════════════════════════════════
# This MAP is used when no custom map.py is provided.
# Re-run manim_ingestion.py on your codebase to generate a project-specific MAP.

SEED_MAP: dict[str, str] = {
    # ── Structural (!) ─────────────────────────────────────────────────────
    "!S":  "class GenScene(Scene):\n    def construct(self):",
    "!P":  "self.play",
    "!A":  "self.add",
    "!W":  "self.wait",
    "!ES": "",

    # ── Mobjects ($) ───────────────────────────────────────────────────────
    "$Ci": "Circle",
    "$Sq": "Square",
    "$Rc": "Rectangle",
    "$Tr": "Triangle",
    "$Dt": "Dot",
    "$Ln": "Line",
    "$Ar": "Arrow",
    "$DA": "DoubleArrow",
    "$Vc": "Vector",
    "$TX": "Text",
    "$MT": "MathTex",
    "$Tx": "Tex",
    "$VG": "VGroup",
    "$Ax": "Axes",
    "$NL": "NumberLine",
    "$NP": "NumberPlane",
    "$SR": "SurroundingRectangle",
    "$BR": "Brace",
    "$Im": "ImageMobject",
    "$Pk": "ParametricFunction",
    "$FG": "FunctionGraph",
    "$VT": "ValueTracker",
    "$Mx": "Matrix",
    "$Dh": "DashedLine",
    "$Rr": "RoundedRectangle",
    "$Sc": "Sector",
    "$Pl": "Polygon",
    "$El": "Ellipse",
    "$Ac": "Arc",
    "$Sp": "Sphere",
    "$Cb": "Cube",
    "$Cn": "Cone",
    "$Cy": "Cylinder",

    # ── Animations (>) ─────────────────────────────────────────────────────
    ">Cr": "Create",
    ">Un": "Uncreate",
    ">FI": "FadeIn",
    ">FO": "FadeOut",
    ">Wr": "Write",
    ">GF": "GrowFromCenter",
    ">GE": "GrowFromEdge",
    ">Tr": "Transform",
    ">RT": "ReplacementTransform",
    ">TC": "TransformFromCopy",
    ">In": "Indicate",
    ">Fl": "Flash",
    ">SP": "ShowPassingFlash",
    ">AG": "AnimationGroup",
    ">LS": "LaggedStart",
    ">LM": "LaggedStartMap",
    ">Sc": "Succession",
    ">Ro": "Rotate",
    ">MA": "MoveAlongPath",
    ">MT": "MoveToTarget",
    ">DB": "DrawBorderThenFill",
    ">Sp": "SpinInFromNothing",
    ">Si": "ShrinkToCenter",
    ">Wi": "Wiggle",
    ">Br": "Broadcast",

    # ── Methods (~) ────────────────────────────────────────────────────────
    "~an": ".animate",          # RESERVED — animate chain accessor
    "~nt": ".next_to",
    "~mv": ".move_to",
    "~sh": ".shift",
    "~te": ".to_edge",
    "~tc": ".to_corner",
    "~at": ".align_to",
    "~st": ".set_color",
    "~sf": ".set_fill",
    "~ss": ".set_stroke",
    "~so": ".set_opacity",
    "~sc": ".scale",
    "~sr": ".stretch",
    "~ro": ".rotate",
    "~fl": ".flip",
    "~ad": ".add",
    "~rm": ".remove",
    "~bc": ".become",
    "~cp": ".copy",
    "~au": ".add_updater",
    "~ru": ".remove_updater",
    "~gc": ".get_center",
    "~gt": ".get_top",
    "~gb": ".get_bottom",
    "~gl": ".get_left",
    "~gr": ".get_right",
    "~ar": ".arrange",
    "~gi": ".arrange_in_grid",
    "~ss2": ".save_state",
    "~rs": ".restore",
    "~sg": ".set_color_by_gradient",

    # ── Constants (#) ──────────────────────────────────────────────────────
    "#UP": "UP",
    "#DN": "DOWN",
    "#LT": "LEFT",
    "#RT": "RIGHT",
    "#IN": "IN",
    "#OT": "OUT",
    "#OR": "ORIGIN",
    "#UL": "UL",
    "#UR": "UR",
    "#DL": "DL",
    "#DR": "DR",
    "#re": "RED",
    "#bl": "BLUE",
    "#gr": "GREEN",
    "#yw": "YELLOW",
    "#wh": "WHITE",
    "#bk": "BLACK",
    "#gy": "GREY",
    "#or": "ORANGE",
    "#pr": "PURPLE",
    "#pk": "PINK",
    "#tl": "TEAL",
    "#mr": "MAROON",
    "#r1": "RED_A",
    "#r2": "RED_B",
    "#r3": "RED_C",
    "#b1": "BLUE_A",
    "#b2": "BLUE_B",
    "#b3": "BLUE_C",
    "#g1": "GREEN_A",
    "#g2": "GREEN_B",
    "#g3": "GREEN_C",
    "#sm": "smooth",
    "#ln": "linear",
    "#tb": "there_and_back",

    # ── Kwargs (@) — expand to name only; '=' stays in source @r=2 → radius=2
    "@r":  "radius",
    "@c":  "color",
    "@fc": "fill_color",
    "@sc": "stroke_color",
    "@fo": "fill_opacity",
    "@so": "stroke_opacity",
    "@sw": "stroke_width",
    "@w":  "width",
    "@h":  "height",
    "@sl": "side_length",
    "@rt": "run_time",
    "@rf": "rate_func",
    "@lr": "lag_ratio",
    "@b":  "buff",
    "@d":  "direction",
    "@ae": "aligned_edge",
    "@fs": "font_size",
    "@fn": "font",
    "@sf": "scale_factor",
    "@sa": "start_angle",
    "@ag": "angle",
    "@tl": "tip_length",
    "@xr": "x_range",
    "@yr": "y_range",
    "@xl": "x_length",
    "@yl": "y_length",
}

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Expansion Engine (from M-Short v2 Spec §4)
# ═══════════════════════════════════════════════════════════════════════════════

def build_pattern(map_dict: dict[str, str]) -> re.Pattern:
    """Boundary-safe regex — prevents !S matching inside !Sq."""
    boundary = r"(?=[\s(),=\[\]{}|+\-*/<>~#$!@.]|$)"
    return re.compile(
        r"(" + "|".join(re.escape(k) for k in sorted(map_dict, key=len, reverse=True)) + r")" + boundary
    )

def _expand_raw(text: str, map_dict: dict[str, str], pattern: re.Pattern) -> str:
    return pattern.sub(lambda m: map_dict[m.group(0)], text)

# A line is M-Short if it contains a token prefix in a valid position.
# Two sub-patterns combined:
#   1.  Boundary-required prefixes (!  $  >  #  @): must be preceded by
#       start-of-line, whitespace, or punctuation.  This stops Python
#       comments ("# text") and operator chars from false-triggering.
#   2.  Method prefix (~): may be preceded by ANY character, since Manim
#       methods are called on variable names (c~nt, mob~an~sc).  Python's
#       bitwise-NOT operator is ~x (on numbers) and is vanishingly rare in
#       Manim scenes, so the false-positive risk is negligible.
_MSHORT_LINE_RE = re.compile(
    r"(?:(?:^|[\s(,=])[!$>#@][A-Za-z]|~[A-Za-z])"
)

def expand_hybrid(
    text: str, map_dict: dict[str, str], pattern: re.Pattern
) -> tuple[str, list[str]]:
    """
    Line-by-line hybrid expansion.
    M-Short lines are expanded; raw Python lines pass through unchanged.
    Returns (expanded_text, list_of_passthrough_warnings).
    """
    output, warnings = [], []
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        # Blank lines and M-Short comments (# followed by space) always pass through.
        # Note: "#token" (e.g. "#re") is NOT a comment — it is a constant token.
        if not stripped or stripped.startswith("# "):
            output.append(line)
        elif _MSHORT_LINE_RE.search(line):
            output.append(_expand_raw(line, map_dict, pattern))
        else:
            output.append(line)
            if stripped:
                warnings.append(f"line {i:4d} [raw Python]: {line}")
    return "\n".join(output), warnings

_SCENE_CLASS_RE = re.compile(r"class GenScene(\(Scene\):)")

def renumber_scenes(expanded: str) -> str:
    """Renames GenScene → GenScene, GenScene2, GenScene3… to prevent collisions."""
    matches = list(_SCENE_CLASS_RE.finditer(expanded))
    if len(matches) <= 1:
        return expanded
    result = expanded
    # Walk in reverse so offsets remain valid after each substitution
    for idx, match in reversed(list(enumerate(matches))):
        if idx == 0:
            continue
        suffix = idx + 1
        result = result[: match.start()] + f"class GenScene{suffix}" + match.group(1) + result[match.end() :]
    return result

def repair_indentation(expanded: str) -> str:
    """
    Adds 8-space indentation to the body of each construct() block.
    The !ES → '' expansion creates the blank-line sentinel that closes each block.
    """
    output: list[str] = []
    in_construct = False
    for line in expanded.splitlines():
        stripped = line.strip()
        if "def construct(self):" in line:
            in_construct = True
            output.append(line)
        elif in_construct and stripped == "":
            in_construct = False
            output.append(line)
        elif in_construct:
            output.append("        " + stripped)
        else:
            output.append(line)
    return "\n".join(output)

def expand_scene(m_short: str, map_dict: dict[str, str], pattern: re.Pattern) -> tuple[str, list[str]]:
    """
    Full pipeline: hybrid_expand → repair_indentation → renumber_scenes.
    Returns (python_source, passthrough_warnings).
    """
    expanded, warnings = expand_hybrid(m_short, map_dict, pattern)
    indented   = repair_indentation(expanded)
    renumbered = renumber_scenes(indented)
    return renumbered, warnings

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — MAP Loader
# ═══════════════════════════════════════════════════════════════════════════════

def load_map(map_path: Optional[Path]) -> dict[str, str]:
    """
    Loads a MAP dict from a map.py file (generated by manim_ingestion.py).
    Falls back to the built-in SEED_MAP if no path is given or the file is absent.
    """
    if map_path and map_path.exists():
        spec = importlib.util.spec_from_file_location("custom_map", map_path)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "MAP"):
            return mod.MAP
        warn(f"map.py found at {map_path} but has no MAP variable — using seed MAP")
    elif map_path:
        warn(f"map.py not found at {map_path} — using built-in seed MAP")
    return dict(SEED_MAP)

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — System Prompt Builder
# ═══════════════════════════════════════════════════════════════════════════════

def build_system_prompt(map_dict: dict[str, str], n_scenes: int) -> str:
    """
    Assembles the four-section M-Short system prompt.
    Section C (the MAP) is injected at runtime from map_dict.
    """
    # Format MAP as compact token => expansion lines
    def fmt_map(map_dict: dict[str, str]) -> str:
        groups = {
            "Structural (!)":  [(k, v) for k, v in map_dict.items() if k.startswith("!")],
            "Mobjects ($)":    [(k, v) for k, v in map_dict.items() if k.startswith("$")],
            "Animations (>)":  [(k, v) for k, v in map_dict.items() if k.startswith(">")],
            "Methods (~)":     [(k, v) for k, v in map_dict.items() if k.startswith("~")],
            "Constants (#)":   [(k, v) for k, v in map_dict.items() if k.startswith("#")],
            "Kwargs (@)":      [(k, v) for k, v in map_dict.items() if k.startswith("@")],
        }
        lines = []
        for group, items in groups.items():
            if not items:
                continue
            lines.append(f"# {group}")
            for k, v in sorted(items):
                # Collapse newlines in expansion for display
                display_v = v.replace("\n", " | ")
                lines.append(f"{k} => {display_v}")
        return "\n".join(lines)

    scene_instruction = (
        f"Generate EXACTLY {n_scenes} scene{'s' if n_scenes != 1 else ''}."
        if n_scenes > 0
        else "Generate as many scenes as needed for a complete, well-paced animation."
    )

    return textwrap.dedent(f"""
        M-SHORT-V2.0

        === SECTION A: ROLE ===
        You are a Manim Community animation code generator.
        Output ONLY M-Short code — never standard Python, never prose.

        === SECTION B: RULES ===
        1.  Every scene MUST begin with !S and end with !ES on its own line.
        2.  Never invent tokens. Every token you use must appear in Section C.
        3.  If a concept has no token, write it as standard Python (it passes through).
        4.  Kwargs: write @kwarg=value — e.g. @r=2 (NOT radius=2).
        5.  Constants: write #token — e.g. #re (NOT RED), #UP (NOT UP).
        6.  Animate chains: write mob~an~sh(#UP)  (i.e. mob.animate.shift(UP)).
        7.  Nest calls with parentheses: !P(>Cr($Ci(@r=2,@c=#bl)))
        8.  Variable assignments use plain Python: c=$Ci(@r=2)  or  c = $Ci(@r=2)
        9.  Comments are allowed with #  ONLY if preceded by a space.
        10. {scene_instruction}

        === SECTION C: TOKEN MAP ===
        {fmt_map(map_dict)}

        === SECTION D: EXAMPLE ===
        # Standard Manim:
        # class GenScene(Scene):
        #     def construct(self):
        #         c = Circle(radius=2, color=BLUE, fill_opacity=0.5)
        #         t = Text("Hello", color=WHITE)
        #         t.next_to(c, UP, buff=0.3)
        #         c.animate.scale(1.5)
        #         self.play(Create(c), Write(t))
        #         self.wait(1)
        #         self.play(FadeOut(c), FadeOut(t))
        #
        # M-Short equivalent:
        !S
        c=$Ci(@r=2,@c=#bl,@fo=0.5)
        t=$TX("Hello",@c=#wh)
        t~nt(c,#UP,@b=0.3)
        c~an~sc(1.5)
        !P(>Cr(c),>Wr(t))
        !W(1)
        !P(>FO(c),>FO(t))
        !ES
    """).strip()

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — Anthropic API Client (urllib — no SDK dependency)
# ═══════════════════════════════════════════════════════════════════════════════

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VER = "2023-06-01"
DEFAULT_MODEL     = "claude-sonnet-4-20250514"

@dataclass
class LLMResponse:
    content:      str
    input_tokens: int
    output_tokens: int
    model:        str
    stop_reason:  str

def call_anthropic(
    user_prompt:   str,
    system_prompt: str,
    model:         str = DEFAULT_MODEL,
    max_tokens:    int = 4096,
    api_key:       Optional[str] = None,
) -> LLMResponse:
    """
    Calls the Anthropic Messages API using urllib (no SDK required).
    API key is read from ANTHROPIC_API_KEY env var if not supplied directly.

    Raises
    ------
    RuntimeError  if API key is missing or the request fails
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set.\n"
            "  Export it:  export ANTHROPIC_API_KEY=sk-ant-...\n"
            "  Or pass:    --api-key sk-ant-..."
        )

    payload = json.dumps({
        "model":      model,
        "max_tokens": max_tokens,
        "system":     system_prompt,
        "messages":   [{"role": "user", "content": user_prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=payload,
        headers={
            "x-api-key":         key,
            "anthropic-version": ANTHROPIC_API_VER,
            "content-type":      "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Anthropic API error {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error contacting Anthropic API: {e.reason}") from e

    content_blocks = data.get("content", [])
    text = "\n".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
    usage = data.get("usage", {})

    return LLMResponse(
        content=text,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        model=data.get("model", model),
        stop_reason=data.get("stop_reason", "unknown"),
    )

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — M-Short Block Parser
# ═══════════════════════════════════════════════════════════════════════════════

def parse_mshort_blocks(raw_response: str) -> list[str]:
    """
    Extracts individual M-Short scene blocks from an LLM response.
    Each block is the text between a !S token and its matching !ES.

    Handles:
    - Multiple !S/!ES pairs in one response
    - Prose text before/between/after blocks (ignored)
    - Code fences (```...```) around M-Short output (stripped)

    Returns a list of scene strings, each starting with !S and ending with !ES.
    """
    # Strip markdown code fences if the LLM wrapped its output
    text = re.sub(r"```[a-zA-Z]*\n?", "", raw_response)
    text = text.replace("```", "")

    blocks: list[str] = []
    current: list[str] = []
    in_block = False

    for line in text.splitlines():
        stripped = line.strip()

        if stripped == "!S":
            in_block = True
            current = ["!S"]
        elif stripped == "!ES" and in_block:
            current.append("!ES")
            blocks.append("\n".join(current))
            current = []
            in_block = False
        elif in_block:
            current.append(line)

    # Graceful recovery: if LLM forgot !ES on the last block
    if in_block and current:
        current.append("!ES")
        blocks.append("\n".join(current))

    return blocks

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — Python Source Writer
# ═══════════════════════════════════════════════════════════════════════════════

MANIM_HEADER = textwrap.dedent("""\
    from manim import *

""")

def write_scene_file(
    python_source: str,
    scene_index: int,    # 1-based
    output_dir: Path,
    scene_name: str,     # e.g. "GenScene" or "GenScene2"
) -> Path:
    """
    Writes one expanded scene to 