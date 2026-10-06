"""Draw the cuts between characters.

Each cut is a straight line from the top of the crop to the bottom. Dragging an
end slants it. Dragging across the picture redraws the nearest cut.
"""
import base64

import cv2
import numpy as np
import streamlit as st

import segment as S

_HTML = """
<div id="root">
  <canvas id="view" aria-label="Character cuts. Drag a red line to move it, drag an end to slant it, or drag across the crop to redraw the nearest cut."></canvas>
  <p class="hint">Drag a red line sideways, or pull either end to slant it. Drag across the crop to redraw the nearest cut. Yellow is the floor.</p>
</div>
"""

_CSS = """
#root {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  font-family: var(--st-font);
  color: var(--st-text-color);
}
#view {
  width: 100%;
  touch-action: none;
  border-radius: var(--st-border-radius, 0.5rem);
  background: var(--st-secondary-background-color);
  cursor: crosshair;
}
.hint { margin: 0; font-size: 0.85rem; opacity: 0.85; }
"""

# Element properties, not window listeners: CCv2 only runs cleanup on unmount.
_JS = """
export default function (component) {
  const { data, parentElement, setStateValue } = component;
  const root = parentElement.querySelector("#root");
  const canvas = parentElement.querySelector("#view");
  if (!root || !canvas || !data || !data.png) return;

  const W = Math.max(1, Number(data.w) || 1);
  const H = Math.max(1, Number(data.h) || 1);
  const floorY = data.floor == null ? Math.round(0.75 * (H - 1)) : Math.max(0, Math.min(H - 1, Number(data.floor) || 0));
  const labels = Array.isArray(data.labels) ? data.labels : [];
  const hint = parentElement.querySelector(".hint");
  if (hint && data.hint) hint.textContent = data.hint;
  const clone = (ls) => (ls || []).map((p) => [Number(p[0]), Number(p[1])]);
  let lines = clone(data.lines);
  let drag = null;
  let cssW = 0;
  let cssH = 0;

  function mono(xs) {
    const out = [];
    const last = xs.length - 1;
    for (let i = 0; i < xs.length; i++) {
      let hi = W - 1 - (last - i);
      let lo = out.length ? out[out.length - 1] + 1 : 1;
      if (hi < 1) hi = 1;
      if (lo > hi) lo = hi;
      out.push(Math.min(Math.max(Math.round(xs[i]), lo), hi));
    }
    return out;
  }

  function clampLines() {
    if (!lines.length || W < 2) return;
    const tops = mono(lines.map((p) => p[0]));
    const bots = mono(lines.map((p) => p[1]));
    lines = tops.map((a, i) => [a, bots[i]]);
  }
  clampLines();

  function layout() {
    const img = canvas._img;
    const w = root.clientWidth;
    if (!img || !img.naturalWidth || w < 2) return false;
    const h = Math.max(1, Math.round(img.naturalHeight * (w / img.naturalWidth)));
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

  function xOf(line, yImg) {
    if (H <= 1) return line[0];
    return line[0] + (line[1] - line[0]) * (yImg / (H - 1));
  }

  function cssOf(xImg, yImg) {
    return [(xImg / W) * cssW, (yImg / H) * cssH];
  }

  function imgOf(px, py) {
    return [(px / cssW) * W, (py / cssH) * H];
  }

  function rel(e) {
    const r = canvas.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  }

  function stroke(ctx, x0, y0, x1, y1, color, width) {
    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(x1, y1);
    ctx.lineCap = "round";
    ctx.strokeStyle = "rgba(0,0,0,0.85)";
    ctx.lineWidth = width + 2;
    ctx.stroke();
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.stroke();
  }

  function draw() {
    if (!layout()) return;
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, cssW, cssH);
    ctx.drawImage(canvas._img, 0, 0, cssW, cssH);

    const fy = cssOf(0, floorY)[1];
    ctx.beginPath();
    ctx.moveTo(0, fy);
    ctx.lineTo(cssW, fy);
    ctx.strokeStyle = "rgba(0,0,0,0.8)";
    ctx.lineWidth = 3;
    ctx.stroke();
    ctx.strokeStyle = "#ffb000";
    ctx.lineWidth = 1.5;
    ctx.stroke();

    const edges = [0].concat(lines.map((ln) => ln[0]), [W]);
    ctx.font = "600 12px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    for (let i = 0; i < labels.length && i + 1 < edges.length; i++) {
      const a = cssOf(edges[i], 0)[0];
      const b = cssOf(edges[i + 1], 0)[0];
      if (b - a < 14) continue;
      const text = String(labels[i]);
      ctx.fillStyle = "rgba(0,0,0,0.65)";
      const tw = ctx.measureText(text).width;
      ctx.fillRect((a + b) / 2 - tw / 2 - 3, 4, tw + 6, 16);
      ctx.fillStyle = "#ffffff";
      ctx.fillText(text, (a + b) / 2, 6);
    }

    lines.forEach((ln) => {
      const [x0, y0] = cssOf(ln[0], 0);
      const [x1, y1] = cssOf(ln[1], H - 1);
      stroke(ctx, x0, y0, x1, y1, "#ff4b4b", 2);
      for (const end of [0, 1]) {
        const [hx, hy] = [cssOf(ln[end], 0)[0], end === 0 ? 10 : cssH - 10];
        ctx.beginPath();
        ctx.arc(hx, hy, 5, 0, Math.PI * 2);
        ctx.fillStyle = "#ffffff";
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = "#ff4b4b";
        ctx.stroke();
      }
    });

    if (drag && drag.mode === "draw") {
      const [x0, y0] = cssOf(drag.ext[0], 0);
      const [x1, y1] = cssOf(drag.ext[1], H - 1);
      stroke(ctx, x0, y0, x1, y1, "#7ee081", 2);
    }
  }

  function distToSeg(px, py, ax, ay, bx, by) {
    const dx = bx - ax;
    const dy = by - ay;
    const l2 = dx * dx + dy * dy || 1;
    let t = ((px - ax) * dx + (py - ay) * dy) / l2;
    t = Math.max(0, Math.min(1, t));
    const qx = ax + t * dx;
    const qy = ay + t * dy;
    return Math.hypot(px - qx, py - qy);
  }

  function hit(px, py) {
    let best = null;
    lines.forEach((ln, i) => {
      for (const end of [0, 1]) {
        const hx = cssOf(ln[end], 0)[0];
        const hy = end === 0 ? 10 : cssH - 10;
        const d = Math.hypot(px - hx, py - hy);
        if (d <= 10 && (!best || d < best.d)) best = { d, mode: end === 0 ? "top" : "bottom", index: i };
      }
    });
    if (best) return best;
    lines.forEach((ln, i) => {
      const [x0, y0] = cssOf(ln[0], 0);
      const [x1, y1] = cssOf(ln[1], H - 1);
      const d = distToSeg(px, py, x0, y0, x1, y1);
      if (d <= 7 && (!best || d < best.d)) best = { d, mode: "move", index: i };
    });
    return best;
  }

  function extend(x0, y0, x1, y1) {
    if (Math.abs(y1 - y0) < 0.5) {
      const x = (x0 + x1) / 2;
      return [x, x];
    }
    const xt = x0 + ((0 - y0) * (x1 - x0)) / (y1 - y0);
    const xb = x0 + (((H - 1) - y0) * (x1 - x0)) / (y1 - y0);
    return [xt, xb];
  }

  function nearest(xImg) {
    let best = 0;
    let dist = Infinity;
    lines.forEach((ln, i) => {
      const d = Math.abs(xOf(ln, floorY) - xImg);
      if (d < dist) {
        dist = d;
        best = i;
      }
    });
    return best;
  }

  function emit() {
    clampLines();
    setStateValue("lines", lines.map((p) => [Math.round(p[0]), Math.round(p[1])]));
  }

  canvas.onpointerdown = (e) => {
    if (!cssW || !lines.length) return;
    const [px, py] = rel(e);
    const found = hit(px, py);
    const [ix, iy] = imgOf(px, py);
    if (!found) {
      drag = { mode: "draw", x0: ix, y0: iy, ext: [ix, ix] };
    } else {
      drag = { mode: found.mode, index: found.index, ix, lines: clone(lines) };
    }
    canvas.setPointerCapture(e.pointerId);
    e.preventDefault();
  };

  canvas.onpointermove = (e) => {
    const [px, py] = rel(e);
    if (!drag) {
      const found = cssW ? hit(px, py) : null;
      canvas.style.cursor = !found ? "crosshair" : found.mode === "move" ? "ew-resize" : "grab";
      return;
    }
    if (!cssW) return;
    const [ix, iy] = imgOf(px, py);
    if (drag.mode === "draw") {
      drag.ext = extend(drag.x0, drag.y0, ix, iy);
    } else if (drag.mode === "move") {
      const dx = ix - drag.ix;
      const src = drag.lines[drag.index];
      lines[drag.index] = [src[0] + dx, src[1] + dx];
      clampLines();
    } else {
      const src = drag.lines[drag.index];
      lines[drag.index] = drag.mode === "top" ? [ix, src[1]] : [src[0], ix];
      clampLines();
    }
    draw();
  };

  canvas.onpointerup = (e) => {
    if (!drag) return;
    const [px, py] = rel(e);
    if (drag.mode === "draw") {
      const [ix, iy] = imgOf(px, py);
      const moved = Math.hypot(px - cssOf(drag.x0, drag.y0)[0], py - cssOf(drag.x0, drag.y0)[1]);
      if (moved >= 6) {
        const ext = extend(drag.x0, drag.y0, ix, iy);
        const at = ext[0] + (ext[1] - ext[0]) * (floorY / Math.max(H - 1, 1));
        lines[nearest(at)] = ext;
        clampLines();
      }
    }
    drag = null;
    draw();
    emit();
  };

  canvas.onpointercancel = () => {
    drag = null;
    draw();
  };

  if (root._ro) root._ro.disconnect();
  root._ro = new ResizeObserver(() => draw());
  root._ro.observe(root);

  if (!canvas._img || canvas._src !== data.png) {
    const img = new Image();
    canvas._img = img;
    canvas._src = data.png;
    img.onload = () => draw();
    img.src = "data:image/png;base64," + data.png;
  } else if (canvas._img.complete) {
    draw();
  }

  return () => {
    if (root._ro) root._ro.disconnect();
  };
}
"""

_COMPONENT = st.components.v2.component("ocr_dividers", html=_HTML, css=_CSS, js=_JS)


def _png(gray):
    ok, buf = cv2.imencode(".png", np.asarray(gray, np.uint8))
    if not ok:
        raise ValueError("Could not draw the crop.")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _read_lines(result):
    if result is None:
        return None
    try:
        return result["lines"]
    except Exception:
        return getattr(result, "lines", None)


def lines_ok(lines, n, width):
    if not isinstance(lines, (list, tuple)) or len(lines) != n:
        return False
    for item in lines:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            return False
        try:
            float(item[0])
            float(item[1])
        except (TypeError, ValueError):
            return False
    return width >= 1


def widget(gray, lines, floor, labels, *, key):
    """Canvas of the crop. Returns one [top x, bottom x] pair per interior cut."""
    gray = np.asarray(gray, np.uint8)
    h, w = gray.shape[:2]
    lines = S.clamp_lines(lines, w)
    hint = (
        "Drag a red line sideways, or pull either end to slant it. Drag across the crop to redraw the nearest cut. Yellow is the floor."
        if lines else
        "One character, so there is no cut to draw. Yellow is the floor."
    )
    result = _COMPONENT(
        key=key,
        data={
            "png": _png(gray), "w": w, "h": h, "lines": lines,
            "floor": None if floor is None else int(floor), "labels": list(labels), "hint": hint,
        },
        default={"lines": lines},
        on_lines_change=lambda: None,
        width="stretch",
    )
    got = _read_lines(result)
    if lines_ok(got, len(lines), w):
        return S.clamp_lines(got, w)
    return lines
