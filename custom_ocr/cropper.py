"""Rotate, crop, and mark the floor (baseline) of an uploaded snippet.

Positive angles are counter-clockwise, the same convention as PIL.Image.rotate.
The box and the floor are fractions of the rotated canvas, so a downscaled
preview and the full-resolution crop describe the same region.
"""
import base64
import io

import numpy as np
import streamlit as st
from PIL import Image

DEFAULT_CROP = {"angle": 0.0, "x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0, "floor": 0.8}

_HTML = """
<div id="root">
  <canvas id="view" aria-label="Crop box. Drag inside to move, drag the edges to resize, drag the yellow floor line to the baseline."></canvas>
  <div class="tools">
    <span id="rot-label">Rotation</span>
    <button type="button" id="a-m90">-90</button>
    <button type="button" id="a-m1">-1</button>
    <button type="button" id="a-m01">-0.1</button>
    <input id="angle" type="range" min="-180" max="180" step="0.1" aria-labelledby="rot-label" />
    <button type="button" id="a-p01">+0.1</button>
    <button type="button" id="a-p1">+1</button>
    <button type="button" id="a-p90">+90</button>
    <span id="ang">0.0°</span>
  </div>
  <p class="hint">Drag the box around the string. Drag the yellow floor line onto the baseline the letters sit on. Descenders hang below it.</p>
</div>
"""

_CSS = """
#root {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  font-family: var(--st-font);
  color: var(--st-text-color);
}
#view {
  width: 100%;
  touch-action: none;
  border-radius: var(--st-border-radius, 0.5rem);
  background: var(--st-secondary-background-color);
}
.tools {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
}
.tools button, #rot-label {
  font: inherit;
  font-size: 0.85rem;
}
.tools button {
  color: var(--st-text-color);
  background: var(--st-secondary-background-color);
  border: 1px solid var(--st-border-color);
  border-radius: var(--st-border-radius, 0.4rem);
  padding: 0.15rem 0.45rem;
  cursor: pointer;
}
#angle { flex: 1; min-width: 8rem; }
#ang { min-width: 4.2rem; text-align: right; font-variant-numeric: tabular-nums; }
.hint { margin: 0; font-size: 0.85rem; opacity: 0.85; }
"""

# Listeners are assigned as element properties (not window listeners) because
# CCv2 does not run the cleanup function on every data change, only on unmount.
_JS = """
export default function (component) {
  const { data, parentElement, setStateValue } = component;
  const root = parentElement.querySelector("#root");
  const canvas = parentElement.querySelector("#view");
  const slider = parentElement.querySelector("#angle");
  const ang = parentElement.querySelector("#ang");
  if (!root || !canvas || !slider || !ang || !data || !data.png) return;

  const spec = data.crop || { angle: 0, x: 0, y: 0, w: 1, h: 1, floor: 0.8 };
  let angle = Math.max(-180, Math.min(180, Number(spec.angle) || 0));
  let box = {
    x: Number(spec.x) || 0,
    y: Number(spec.y) || 0,
    w: Number(spec.w) || 1,
    h: Number(spec.h) || 1,
  };
  let floor = Math.max(0.02, Math.min(0.98, Number(spec.floor) || 0.8));
  let drag = null;
  let cssW = 0;
  let cssH = 0;
  const fill = data.fill || [255, 255, 255];

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const rotSize = (w, h, deg) => {
    const r = (deg * Math.PI) / 180;
    const c = Math.abs(Math.cos(r));
    const s = Math.abs(Math.sin(r));
    return [w * c + h * s, w * s + h * c];
  };

  function layout() {
    const img = canvas._img;
    const w = root.clientWidth;
    if (!img || !img.naturalWidth || w < 2) return false;
    const [rw, rh] = rotSize(img.naturalWidth, img.naturalHeight, angle);
    const h = Math.max(1, Math.round(rh * (w / rw)));
    cssW = w;
    cssH = h;
    const dpr = window.devicePixelRatio || 1;
    const bw = Math.max(1, Math.round(w * dpr));
    const bh = Math.max(1, Math.round(h * dpr));
    if (canvas.width !== bw || canvas.height !== bh) {
      canvas.width = bw;
      canvas.height = bh;
    }
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    return true;
  }

  function boxPx() {
    return { x: box.x * cssW, y: box.y * cssH, w: box.w * cssW, h: box.h * cssH };
  }

  function draw() {
    if (!layout()) return;
    const img = canvas._img;
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);
    ctx.fillStyle = "rgb(" + fill[0] + "," + fill[1] + "," + fill[2] + ")";
    ctx.fillRect(0, 0, cssW, cssH);
    const [rw] = rotSize(img.naturalWidth, img.naturalHeight, angle);
    const sc = cssW / rw;
    ctx.save();
    ctx.translate(cssW / 2, cssH / 2);
    ctx.rotate((-angle * Math.PI) / 180);
    ctx.drawImage(
      img,
      (-img.naturalWidth * sc) / 2,
      (-img.naturalHeight * sc) / 2,
      img.naturalWidth * sc,
      img.naturalHeight * sc
    );
    ctx.restore();

    const b = boxPx();
    ctx.save();
    ctx.fillStyle = "rgba(0,0,0,0.45)";
    ctx.beginPath();
    ctx.rect(0, 0, cssW, cssH);
    ctx.rect(b.x, b.y, b.w, b.h);
    ctx.fill("evenodd");
    ctx.restore();

    ctx.strokeStyle = "#ff4b4b";
    ctx.lineWidth = 2;
    ctx.strokeRect(b.x + 1, b.y + 1, Math.max(0, b.w - 2), Math.max(0, b.h - 2));

    const handles = [
      [b.x, b.y],
      [b.x + b.w, b.y],
      [b.x, b.y + b.h],
      [b.x + b.w, b.y + b.h],
      [b.x + b.w / 2, b.y],
      [b.x + b.w / 2, b.y + b.h],
      [b.x, b.y + b.h / 2],
      [b.x + b.w, b.y + b.h / 2],
    ];
    ctx.lineWidth = 1;
    for (const [hx, hy] of handles) {
      ctx.fillStyle = "#ffffff";
      ctx.strokeStyle = "#ff4b4b";
      ctx.fillRect(hx - 4, hy - 4, 8, 8);
      ctx.strokeRect(hx - 4, hy - 4, 8, 8);
    }

    const fy = b.y + floor * b.h;
    ctx.beginPath();
    ctx.moveTo(b.x, fy);
    ctx.lineTo(b.x + b.w, fy);
    ctx.strokeStyle = "rgba(0,0,0,0.8)";
    ctx.lineWidth = 4;
    ctx.stroke();
    ctx.strokeStyle = "#ffb000";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(b.x, fy - 6);
    ctx.lineTo(b.x, fy + 6);
    ctx.moveTo(b.x + b.w, fy - 6);
    ctx.lineTo(b.x + b.w, fy + 6);
    ctx.stroke();

    ctx.font = "600 12px sans-serif";
    const label = "floor";
    const tw = ctx.measureText(label).width;
    const above = fy - b.y > 18;
    const top = above ? fy - 18 : fy + 3;
    ctx.fillStyle = "rgba(0,0,0,0.72)";
    ctx.fillRect(b.x + 4, top, tw + 8, 15);
    ctx.fillStyle = "#ffb000";
    ctx.fillText(label, b.x + 8, top + 12);
  }

  function hit(px, py) {
    const b = boxPx();
    const near = (x, y) => Math.abs(px - x) <= 8 && Math.abs(py - y) <= 8;
    if (near(b.x, b.y)) return "nw";
    if (near(b.x + b.w, b.y)) return "ne";
    if (near(b.x, b.y + b.h)) return "sw";
    if (near(b.x + b.w, b.y + b.h)) return "se";
    const fy = b.y + floor * b.h;
    if (px >= b.x && px <= b.x + b.w && Math.abs(py - fy) <= 7) return "floor";
    if (px >= b.x && px <= b.x + b.w && Math.abs(py - b.y) <= 6) return "n";
    if (px >= b.x && px <= b.x + b.w && Math.abs(py - (b.y + b.h)) <= 6) return "s";
    if (py >= b.y && py <= b.y + b.h && Math.abs(px - b.x) <= 6) return "w";
    if (py >= b.y && py <= b.y + b.h && Math.abs(px - (b.x + b.w)) <= 6) return "e";
    if (px > b.x && px < b.x + b.w && py > b.y && py < b.y + b.h) return "move";
    return null;
  }

  function rel(e) {
    const r = canvas.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  }

  const cursors = {
    floor: "ns-resize", move: "move",
    n: "ns-resize", s: "ns-resize", e: "ew-resize", w: "ew-resize",
    nw: "nwse-resize", se: "nwse-resize", ne: "nesw-resize", sw: "nesw-resize",
  };

  function emit() {
    setStateValue("crop", {
      angle: Math.round(angle * 10) / 10,
      x: box.x, y: box.y, w: box.w, h: box.h,
      floor: floor,
    });
  }

  function showAngle() {
    slider.value = String(angle);
    ang.textContent = angle.toFixed(1) + "°";
  }

  canvas.onpointerdown = (e) => {
    const [x, y] = rel(e);
    const mode = hit(x, y);
    if (!mode) return;
    drag = { mode, x, y, box: { x: box.x, y: box.y, w: box.w, h: box.h }, floor };
    canvas.setPointerCapture(e.pointerId);
    e.preventDefault();
  };
  canvas.onpointermove = (e) => {
    const [x, y] = rel(e);
    if (!drag) {
      canvas.style.cursor = cursors[hit(x, y)] || "default";
      return;
    }
    if (!cssW || !cssH) return;
    const dx = (x - drag.x) / cssW;
    const dy = (y - drag.y) / cssH;
    if (drag.mode === "move") {
      box.x = clamp(drag.box.x + dx, 0, 1 - drag.box.w);
      box.y = clamp(drag.box.y + dy, 0, 1 - drag.box.h);
    } else if (drag.mode === "floor") {
      const py = drag.box.y * cssH + drag.floor * drag.box.h * cssH + (y - drag.y);
      floor = clamp((py - drag.box.y * cssH) / (drag.box.h * cssH), 0.02, 0.98);
    } else {
      const min = 0.03;
      let x0 = drag.box.x;
      let y0 = drag.box.y;
      let x1 = x0 + drag.box.w;
      let y1 = y0 + drag.box.h;
      const m = drag.mode;
      if (m === "n" || m === "nw" || m === "ne") y0 = clamp(drag.box.y + dy, 0, y1 - min);
      if (m === "s" || m === "sw" || m === "se") y1 = clamp(drag.box.y + drag.box.h + dy, y0 + min, 1);
      if (m === "w" || m === "nw" || m === "sw") x0 = clamp(drag.box.x + dx, 0, x1 - min);
      if (m === "e" || m === "ne" || m === "se") x1 = clamp(drag.box.x + drag.box.w + dx, x0 + min, 1);
      box = { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
    }
    draw();
  };
  canvas.onpointerup = () => {
    if (!drag) return;
    drag = null;
    emit();
  };

  function bump(d) {
    angle = clamp(Math.round((angle + d) * 10) / 10, -180, 180);
    showAngle();
    draw();
    emit();
  }
  parentElement.querySelector("#a-m90").onclick = () => bump(-90);
  parentElement.querySelector("#a-m1").onclick = () => bump(-1);
  parentElement.querySelector("#a-m01").onclick = () => bump(-0.1);
  parentElement.querySelector("#a-p01").onclick = () => bump(0.1);
  parentElement.querySelector("#a-p1").onclick = () => bump(1);
  parentElement.querySelector("#a-p90").onclick = () => bump(90);
  slider.oninput = () => {
    angle = Number(slider.value);
    ang.textContent = angle.toFixed(1) + "°";
    draw();
  };
  slider.onchange = () => emit();
  showAngle();

  if (root._ro) root._ro.disconnect();
  root._ro = new ResizeObserver(() => draw());
  root._ro.observe(root);

  if (!canvas._img || canvas._src !== data.png) {
    const img = new Image();
    canvas._img = img;
    canvas._src = data.png;
    img.onload = () => draw();
    img.src = "data:image/png;base64," + data.png;
  } else {
    canvas._img.onload = () => draw();
    if (canvas._img.complete) draw();
  }

  return () => {
    if (root._ro) root._ro.disconnect();
  };
}
"""

_COMPONENT = st.components.v2.component("ocr_cropper", html=_HTML, css=_CSS, js=_JS)


def clean(spec):
    """Clamp a crop spec into the rotated canvas."""
    src = spec if isinstance(spec, dict) else {}
    d = dict(DEFAULT_CROP)
    for k in d:
        if k in src:
            try:
                d[k] = float(src[k])
            except (TypeError, ValueError):
                pass
    d["angle"] = max(-180.0, min(180.0, d["angle"]))
    d["w"] = max(0.01, min(1.0, d["w"]))
    d["h"] = max(0.01, min(1.0, d["h"]))
    d["x"] = max(0.0, min(1.0 - d["w"], d["x"]))
    d["y"] = max(0.0, min(1.0 - d["h"], d["y"]))
    d["floor"] = max(0.0, min(1.0, d["floor"]))
    return d


def _read_crop(result):
    if result is None:
        return None
    try:
        return result["crop"]
    except Exception:
        return getattr(result, "crop", None)


def paper_color(img):
    """Average of the four corners, used to fill the wedges rotation reveals."""
    a = np.asarray(img)
    pts = np.stack([a[0, 0], a[0, -1], a[-1, 0], a[-1, -1]]).astype(np.int16)
    return [int(v) for v in pts.mean(axis=0)]


def _preview_b64(img, max_side=1200):
    w, h = img.size
    scale = min(1.0, max_side / max(w, h))
    preview = img
    if scale < 1:
        preview = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    preview.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


@st.cache_data(max_entries=4, show_spinner=False)
def _encoded(raw: bytes):
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    return _preview_b64(img), paper_color(img)


def widget(raw, *, key):
    """Interactive rotate + crop + floor. `raw` is the original file bytes."""
    state = st.session_state.get(key, {})
    stored = state.get("crop") if isinstance(state, dict) else None
    spec = clean(stored)
    png, fill = _encoded(raw)
    result = _COMPONENT(
        key=key,
        data={"png": png, "fill": fill, "crop": spec},
        default={"crop": spec},
        on_crop_change=lambda: None,
        width="stretch",
    )
    return clean(_read_crop(result) or spec)


def apply(img, spec):
    """Rotate and crop `img`. Returns the PIL crop and the floor row inside it."""
    spec = clean(spec)
    angle = spec["angle"]
    rot = img if abs(angle) < 0.05 else img.rotate(
        angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=tuple(paper_color(img))
    )
    width, height = rot.size
    left = max(0, min(width - 1, int(round(spec["x"] * width))))
    top = max(0, min(height - 1, int(round(spec["y"] * height))))
    right = max(left + 1, min(width, int(round((spec["x"] + spec["w"]) * width))))
    bottom = max(top + 1, min(height, int(round((spec["y"] + spec["h"]) * height))))
    crop = rot.crop((left, top, right, bottom))
    floor_y = int(round(spec["floor"] * crop.size[1]))
    return crop, max(0, min(crop.size[1] - 1, floor_y))


def mark_floor(img, floor_y):
    """RGB preview with a yellow band centered on the floor row."""
    a = np.array(img.convert("RGB"))
    h = a.shape[0]
    y = int(np.clip(round(floor_y), 0, h - 1))
    t = max(1, h // 150)
    a[max(0, y - t):min(h, y + t + 1), :, :] = (255, 176, 0)
    return a
