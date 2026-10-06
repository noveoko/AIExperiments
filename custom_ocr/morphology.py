"""One style for the whole alphabet, learned from the letters already saved.

S(c) is Eidolon Script Regular. θ is a shear, a stroke-radius multiplier, a
horizontal-vs-vertical contrast, an endpoint extension, an endpoint bulb
(as a fraction of the local stroke), and a smoothing amount. M_θ paints
that stroke onto the skeleton of S(c). Counters of the source stay open.
The same θ is applied to every missing character, so letter identity stays
in the outline.
"""
import numpy as np, cv2
from pathlib import Path
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont
from matplotlib import font_manager
from scipy.optimize import differential_evolution
from skimage.morphology import skeletonize
import glyphs as G
import segment as S

EIDOLON = Path(__file__).with_name("fonts") / "eidolon-script-regular.ttf"
DEJAVU = font_manager.findfont("DejaVu Sans")
SCALE = 3
# shear, radius multiplier, contrast, serif px, bulb fraction of local half-width, smooth px
# A multiplier past ~1.2, or a strong vertical emphasis, fills counters.
BOUNDS = np.array([(-0.6, 0.6), (0.75, 1.20), (-0.20, 0.20), (0.0, 2.0), (0.0, 0.35), (0.0, 0.45)])
IDENTITY = np.array([0.0, 1.0, 0.0, 0.0, 0.0, 0.0])
_NB = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], np.uint8)


def _font(path, size):
    return ImageFont.truetype(str(path), max(8, int(size)))


@lru_cache(maxsize=4)
def _cap_ratio(path):
    _, top, _, _ = _font(path, 200).getbbox("H", anchor="ls")
    return max(1.0, -top) / 200


@lru_cache(maxsize=256)
def covers(ch, path=str(EIDOLON)):
    """False when the font draws .notdef for this character."""
    f = _font(path, 48)
    box = (80, 120)

    def ink(c):
        im = Image.new("L", box, 255)
        ImageDraw.Draw(im).text((8, 70), c, font=f, fill=0, anchor="ls")
        return np.array(im)

    return not np.array_equal(ink(ch), ink("\uffff"))


def _raster(ch, path, height):
    """Draw `ch` so its baseline sits on the shared floor of a `height`-tall frame."""
    base = int(round(height * S.BASE_FRAC))
    size = base / _cap_ratio(str(path))
    f = _font(path, round(size))
    pad = max(2, int(size * 0.15))
    width = max(1, int(f.getlength(ch)) + pad * 2 + 2)
    im = Image.new("L", (width, height), 255)
    ImageDraw.Draw(im).text((pad, base), ch, font=f, fill=0, anchor="ls")
    return np.array(im)


@lru_cache(maxsize=256)
def source(ch):
    """High-resolution Eidolon rendering, or DejaVu when Eidolon has no glyph."""
    path = EIDOLON if covers(ch) else DEJAVU
    return _raster(ch, path, G.CH * SCALE), path == DEJAVU


def _shear(g, shear, baseline):
    h, w = g.shape
    extra = int(np.ceil(abs(shear) * h)) + 2
    # Top moves right when shear is positive. The baseline row stays put.
    m = np.float32([[1, -shear, shear * baseline + extra], [0, 1, 0]])
    return cv2.warpAffine(g, m, (w + 2 * extra, h), flags=cv2.INTER_LINEAR, borderValue=255)


def _tangents(sk):
    """Unit tangents. Endpoints point outward, away from their only neighbor."""
    sk = np.asarray(sk, bool)
    ys, xs = np.where(sk)
    tang = np.zeros(sk.shape + (2,), np.float32)
    h, w = sk.shape
    steps = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
    for y, x in zip(ys, xs):
        pts = [(dy, dx) for dy, dx in steps if 0 <= y + dy < h and 0 <= x + dx < w and sk[y + dy, x + dx]]
        if len(pts) == 1:
            vy, vx = -pts[0][0], -pts[0][1]
        elif len(pts) >= 2:
            vy, vx = pts[0][0] - pts[1][0], pts[0][1] - pts[1][1]
            if vy == 0 and vx == 0:
                vy, vx = -pts[0][0], -pts[0][1]
        else:
            vy, vx = 0.0, 1.0
        n = float(np.hypot(vy, vx)) or 1.0
        tang[y, x] = (vy / n, vx / n)
    return tang


def _binary(g):
    g = np.asarray(g)
    if g.shape[0] != G.CH:
        g = G.canon(g)
    return g < (int(g.max()) + int(g.min())) / 2


def _enclosed(ink):
    """Background regions that do not touch the border. Those are the counters."""
    ink = np.asarray(ink, bool)
    n, lab = cv2.connectedComponents((~ink).astype(np.uint8), 4)
    holes = np.zeros(ink.shape, bool)
    h, w = ink.shape
    for i in range(1, n):
        ys, xs = np.where(lab == i)
        if not len(ys):
            continue
        if ys.min() == 0 or xs.min() == 0 or ys.max() == h - 1 or xs.max() == w - 1:
            continue
        holes[ys, xs] = True
    return holes


def _shrink_holes(holes, max_px):
    """Erode each counter by up to `max_px`, and stop before a counter vanishes."""
    cur = holes.astype(np.uint8)
    if max_px <= 0 or not cur.any():
        return cur.astype(bool)
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    for _ in range(int(max_px)):
        nxt = cv2.erode(cur, ker)
        _, lab = cv2.connectedComponents(cur)
        if any(nxt[lab == i].sum() == 0 for i in range(1, lab.max() + 1)):
            break
        cur = nxt
    return cur.astype(bool)


def _paint(sk, radius, tang, serif):
    h, w = sk.shape
    canvas = np.full((h, w), 255, np.uint8)
    count = cv2.filter2D(sk.astype(np.uint8), cv2.CV_16S, _NB, borderType=cv2.BORDER_CONSTANT)
    ys, xs = np.where(sk)
    for y, x in zip(ys, xs):
        r = max(1, int(np.floor(radius[y, x])))
        cv2.circle(canvas, (int(x), int(y)), r, 0, -1, lineType=cv2.LINE_8)
        if count[y, x] == 1 and serif >= 1:
            vy, vx = tang[y, x]
            for step in range(1, int(serif) + 1):
                py = int(round(y + vy * step))
                px = int(round(x + vx * step))
                if 0 <= py < h and 0 <= px < w:
                    cv2.circle(canvas, (px, py), r, 0, -1, lineType=cv2.LINE_8)
    return canvas


def _clip_theta(theta):
    t = np.array(theta, float)
    return np.array([float(np.clip(v, lo, hi)) for v, (lo, hi) in zip(t, BOUNDS)])


def apply(ch, theta):
    """Mutate the source outline of `ch` and return a 64px-tall glyph."""
    shear, radius_k, contrast, serif, bulb, smooth = _clip_theta(theta)
    src, _ = source(ch)
    base = int(round(src.shape[0] * S.BASE_FRAC))
    g = _shear(src, shear, base)
    mask = g < 128
    if not mask.any():
        return np.full((G.CH, 1), 255, np.uint8)
    sk = skeletonize(mask)
    if not sk.any():
        sk = mask
    dist = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 3)
    tang = _tangents(sk)
    # cos(2φ) = tx² − ty² for a unit tangent: +1 horizontal, −1 vertical.
    mod = 1 + contrast * (tang[:, :, 1] ** 2 - tang[:, :, 0] ** 2)
    mod = np.clip(mod, 0.85, 1.15)
    radius = np.maximum(0.6, dist * radius_k * mod)
    count = cv2.filter2D(sk.astype(np.uint8), cv2.CV_16S, _NB, borderType=cv2.BORDER_CONSTANT)
    radius = radius + np.where(sk & (count == 1), bulb * dist, 0.0)
    holes = _enclosed(mask)
    if holes.any():
        # Stop two paint-pixels short of a counter so the disk cannot cross it.
        clearance = cv2.distanceTransform(np.where(holes, 0, 255).astype(np.uint8), cv2.DIST_L2, 3)
        radius = np.minimum(radius, np.maximum(0.6, clearance - 2))
    painted = _paint(sk, radius, tang, serif * SCALE)
    if smooth > 0.05:
        painted = cv2.GaussianBlur(painted, (0, 0), smooth * SCALE)
        # A light-gray counter must stay white. 128 was painting those pixels black.
        painted = np.where(painted < 72, 0, 255).astype(np.uint8)
    if holes.any():
        painted = painted.copy()
        painted[_shrink_holes(holes, SCALE)] = 255
    width = max(1, int(round(painted.shape[1] * G.CH / painted.shape[0])))
    out = cv2.resize(painted, (width, G.CH), interpolation=cv2.INTER_AREA)
    return G.trim(out)


def preview_source(ch):
    """Unmutated source glyph in the same frame, for the reconstruction row."""
    src, _ = source(ch)
    width = max(1, int(round(src.shape[1] * G.CH / src.shape[0])))
    return G.trim(cv2.resize(src, (width, G.CH), interpolation=cv2.INTER_AREA))


def _place(mask, width):
    out = np.zeros((mask.shape[0], width), bool)
    cols = np.where(mask.any(0))[0]
    if not len(cols):
        return out
    shift = int(round(width / 2 - (cols.min() + cols.max()) / 2))
    x0 = max(0, shift)
    s0 = max(0, -shift)
    n = min(mask.shape[1] - s0, width - x0)
    if n > 0:
        out[:, x0:x0 + n] = mask[:, s0:s0 + n]
    return out


def _masks(pred, target):
    def m(g):
        g = np.asarray(g)
        if g.shape[0] != G.CH:
            g = G.canon(g)
        return g < (int(g.max()) + int(g.min())) / 2

    a, b = m(pred), m(target)
    width = max(a.shape[1], b.shape[1]) + 4
    return _place(a, width), _place(b, width)


def iou(pred, target):
    a, b = _masks(pred, target)
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return float(inter) / float(union) if union else 0.0


def _chamfer(a, b):
    if not a.any() or not b.any():
        return 8.0
    da = cv2.distanceTransform((~a).astype(np.uint8), cv2.DIST_L2, 3)
    db = cv2.distanceTransform((~b).astype(np.uint8), cv2.DIST_L2, 3)
    return float(da[b].mean() + db[a].mean())


def _mismatch(pred, target):
    a, b = _masks(pred, target)
    overlap = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    iou_loss = 1 - (float(overlap) / float(union) if union else 0.0)
    return iou_loss + 0.01 * _chamfer(a, b)


def _counter_frac(pred, holes):
    """Share of the source counter that the mutation painted black."""
    if holes is None or not holes.any():
        return 0.0
    ink = _binary(pred)
    width = max(ink.shape[1], holes.shape[1]) + 4
    a, b = _place(ink, width), _place(holes, width)
    return float(np.logical_and(a, b).sum() / b.sum()) if b.any() else 0.0


def _keeps_counters(ch, crop):
    """A solid crop must not vote on the shared stroke."""
    src = preview_source(ch)
    src_ink, crop_ink = _binary(src), _binary(crop)
    if _enclosed(src_ink).any() and not _enclosed(crop_ink).any():
        return False
    if src_ink.any() and crop_ink.mean() > 1.35 * src_ink.mean():
        return False
    return True


def fit(store, synth=(), maxiter=12, holdout=True):
    """Fit one θ to the original crop of each real glyph. Returns plain Python values."""
    pairs = [(ch, lst[0]) for ch, lst in sorted(store.items()) if ch not in synth and lst]
    if not pairs:
        raise ValueError("Save at least a few real glyphs first.")
    voting = [(ch, g) for ch, g in pairs if _keeps_counters(ch, g)]
    skipped = [ch for ch, g in pairs if not _keeps_counters(ch, g)]
    if len(voting) < 4:
        voting, skipped = pairs, []
    holes = {ch: _enclosed(_binary(preview_source(ch))) for ch, _ in voting}

    def loss(theta):
        scores = []
        for ch, g in voting:
            pred = apply(ch, theta)
            scores.append(_mismatch(pred, g) + 0.35 * _counter_frac(pred, holes[ch]))
        return float(np.mean(scores))

    res = differential_evolution(
        loss, BOUNDS, seed=0, popsize=2, mutation=0.5, recombination=0.7,
        maxiter=maxiter, atol=0.01, tol=0.01, polish=False, workers=1, updating="immediate",
    )
    theta = _clip_theta(res.x)
    scores = {ch: iou(apply(ch, theta), g) for ch, g in voting}
    out = {
        "theta": [float(v) for v in theta],
        "iou": float(np.mean(list(scores.values()))),
        "fallback": [ch for ch, _ in voting if not covers(ch)],
        "skipped": skipped,
    }
    if holdout and len(voting) >= 4:
        hold = voting[len(voting) // 2][0]
        sub = {ch: [g] for ch, g in voting if ch != hold}
        held = fit(sub, maxiter=max(6, maxiter // 2), holdout=False)
        out["holdout"] = iou(apply(hold, held["theta"]), dict(voting)[hold])
        out["holdout_char"] = hold
    return out


def jitter(theta, rng):
    scale = np.array([0.04, 0.03, 0.02, 0.15, 0.03, 0.04])
    return _clip_theta(np.asarray(theta, float) + rng.normal(0, scale))


RAMP_R = 8


def advance(ch):
    """Eidolon advance width. Relative widths, not pixels."""
    path = EIDOLON if covers(ch) else DEJAVU
    return max(0.5, float(_font(path, 200).getlength(ch)))


def glyph_width(ch, char_px, ref_advance):
    """Pixel width of `ch` when a typical letter is `char_px` wide."""
    ref = max(float(ref_advance), 0.5)
    return max(1, int(round(float(char_px) * advance(ch) / ref)))


def _ink_mask(g):
    g = np.asarray(g)
    return g < (float(g.max()) + float(g.min())) / 2


def _signed(ink):
    """Positive on paper, negative inside ink. Zero on the boundary."""
    ink_u = ink.astype(np.uint8)
    inside = cv2.distanceTransform(ink_u, cv2.DIST_L2, 3)
    outside = cv2.distanceTransform(1 - ink_u, cv2.DIST_L2, 3)
    return np.where(ink, -inside, outside).astype(np.float32)


def _fill_ramp(ramp):
    ramp = np.array(ramp, float)
    known = np.isfinite(ramp)
    if not known.any():
        return np.linspace(0, 255, len(ramp))
    x = np.arange(len(ramp))
    ramp[~known] = np.interp(x[~known], x[known], ramp[known])
    return ramp


def _edge_width(ramp):
    """Width, in pixels, of the rise from ink to paper."""
    ramp = np.asarray(ramp, float)
    dark = int(np.argmin(ramp))
    seg = ramp[dark:]
    span = float(seg[-1] - seg[0]) if len(seg) else 0.0
    if span < 5:
        return 0.0
    lo, hi = seg[0] + 0.3 * span, seg[0] + 0.7 * span
    i0 = int(np.argmax(seg >= lo))
    i1 = int(np.argmax(seg >= hi))
    return float(max(i1 - i0, 0))


def _corr_len(res):
    res = np.asarray(res, float)
    res = res - res.mean()
    var = float((res * res).mean())
    if var < 1e-3 or res.shape[1] < 4:
        return 0.5
    for lag in range(1, min(12, res.shape[1] - 1)):
        ac = float((res[:, :-lag] * res[:, lag:]).mean() / var)
        if ac < 0.5:
            return float(lag)
    return 8.0


def _pixel_factor(g):
    """Integer block size. 1 when the crop is not visibly pixelated.

    Nearest-neighbor upscaling can put the block seam on either phase, so both are tried.
    """
    g = np.asarray(g, np.float32)
    best_f, best = 1, 1.6
    w = g.shape[1]
    for f in (2, 3, 4):
        if min(g.shape) < f * 4:
            continue
        for phase in range(f):
            cols = np.arange(w)
            bid = (cols - phase) // f
            valid = cols[:-1] >= phase
            same = (bid[:-1] == bid[1:]) & valid
            boundary = valid & ~same
            if same.sum() < 4 or boundary.sum() < 2:
                continue
            diff = np.abs(g[:, :-1] - g[:, 1:])
            intra = float(diff[:, same].mean())
            inter = float(diff[:, boundary].mean())
            score = inter / (intra + 1e-3)
            if score > best:
                best, best_f = score, f
    return best_f


def _wiggle(ink):
    """RMS normal wobble of the contour, clamped to a fraction of the stroke."""
    cnts, _ = cv2.findContours(ink.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    vals = []
    k = 9
    for c in cnts:
        if len(c) < k * 2:
            continue
        p = c.reshape(-1, 2).astype(np.float32)
        pad = np.concatenate([p[-k:], p, p[:k]], 0)
        sm = cv2.blur(pad.reshape(-1, 1, 2), (1, k * 2 + 1)).reshape(-1, 2)[k:-k]
        d = p - sm
        t = np.roll(sm, -1, 0) - np.roll(sm, 1, 0)
        nrm = np.sqrt((t * t).sum(1)) + 1e-6
        normal = d[:, 0] * (-t[:, 1] / nrm) + d[:, 1] * (t[:, 0] / nrm)
        vals.append(float(np.sqrt(np.mean(normal ** 2))))
    if not vals:
        return 0.0
    half = float(cv2.distanceTransform(ink.astype(np.uint8), cv2.DIST_L2, 3).max())
    return float(min(np.median(vals), 0.25 * max(half, 1.0)))


def _one_profile(g):
    g = np.asarray(g, np.float32)
    ink = _ink_mask(g)
    signed = _signed(ink)
    bins = []
    for d in range(-RAMP_R, RAMP_R + 1):
        if d == -RAMP_R:
            sel = signed <= d + 0.5
        elif d == RAMP_R:
            sel = signed > d - 0.5
        else:
            sel = (signed > d - 0.5) & (signed <= d + 0.5)
        bins.append(float(np.median(g[sel])) if sel.sum() >= 8 else np.nan)
    ramp = _fill_ramp(bins)
    idx = np.clip(np.rint(signed), -RAMP_R, RAMP_R).astype(int)
    res = g - ramp[idx + RAMP_R]
    return {
        "ramp": ramp,
        "ink_sigma": float(res[signed < -1].std()) if np.any(signed < -1) else 0.0,
        "paper_sigma": float(res[signed > 1].std()) if np.any(signed > 1) else 0.0,
        "corr": _corr_len(res),
        "pixel": _pixel_factor(g),
        "wiggle": _wiggle(ink),
        "ink_level": float(ramp[0]),
        "paper_level": float(ramp[-1]),
        "edge": _edge_width(ramp),
        "width": int(g.shape[1]),
    }


def measure_capture(store, synth=()):
    """One capture profile from the original real crops. Plain Python values."""
    pairs = [(ch, lst[0]) for ch, lst in sorted(store.items()) if ch not in synth and lst]
    # A filled-in photo still carries the edge and the noise. Only a flat mask does not.
    usable = [(ch, g) for ch, g in pairs if len(np.unique(np.asarray(g))) >= 16]
    if len(usable) < 2:
        usable = pairs
    if not usable:
        raise ValueError("Save at least one real glyph first.")
    profs = [_one_profile(g) for _, g in usable]
    ramp = np.median([p["ramp"] for p in profs], 0)

    def med(key):
        return float(np.median([p[key] for p in profs]))

    return {
        "ramp": [float(v) for v in ramp],
        "ink_sigma": med("ink_sigma"),
        "paper_sigma": med("paper_sigma"),
        "corr": med("corr"),
        "pixel": int(np.median([p["pixel"] for p in profs])),
        "wiggle": med("wiggle"),
        "ink_level": float(ramp[0]),
        "paper_level": float(ramp[-1]),
        "edge": _edge_width(ramp),
        "char_px": med("width"),
        "ref_advance": float(np.median([advance(ch) for ch, _ in usable])),
    }


def _to_size(shape, width_px, height_px):
    tw, th = max(1, int(width_px)), max(1, int(height_px))
    interp = cv2.INTER_AREA if tw <= shape.shape[1] else cv2.INTER_CUBIC
    return cv2.resize(np.asarray(shape), (tw, th), interpolation=interp)


def prepare_capture(phi, char_px):
    """Return φ scaled so a typical letter is `char_px` wide. Does not mutate `phi`."""
    measured = max(float(phi.get("char_px") or char_px), 1.0)
    scale = float(char_px) / measured
    out = dict(phi)
    out["_height_scale"] = scale
    out["_dist_scale"] = scale
    out["pixel"] = max(1, int(round(float(phi.get("pixel") or 1) * scale)))
    return out


def render(ch, theta, phi, rng, char_px):
    """Stroke, then capture, at the user's character width."""
    phi = prepare_capture(phi, char_px)
    shape = apply(ch, theta)
    width = glyph_width(ch, char_px, phi.get("ref_advance") or advance(ch))
    height = max(1, int(round(G.CH * float(phi["_height_scale"]))))
    return _capture_sized(shape, phi, rng, width, height)


def _capture_sized(shape, phi, rng, width, height):
    g = _to_size(shape, width, height)
    dist_scale = float(phi.get("_dist_scale") or 1.0)
    pixel = max(1, int(phi.get("pixel") or 1))
    if pixel > 1:
        sh = max(1, g.shape[0] // pixel)
        sw = max(1, g.shape[1] // pixel)
        small = cv2.resize(g, (sw, sh), interpolation=cv2.INTER_AREA)
        g = cv2.resize(small, (g.shape[1], g.shape[0]), interpolation=cv2.INTER_NEAREST)
    ink = _ink_mask(g)
    signed = _signed(ink)
    amp = float(phi.get("wiggle") or 0) * dist_scale
    if amp > 0.15:
        gh, gw = max(2, g.shape[0] // 8), max(2, g.shape[1] // 8)
        field = rng.standard_normal((gh, gw)).astype(np.float32)
        field = cv2.resize(field, (g.shape[1], g.shape[0]), interpolation=cv2.INTER_CUBIC)
        field -= field.mean()
        field *= amp / (float(field.std()) + 1e-6)
        half = float(cv2.distanceTransform(ink.astype(np.uint8), cv2.DIST_L2, 3).max())
        field = np.clip(field, -0.25 * max(half, 1), 0.25 * max(half, 1))
        signed = signed - field
    ramp = np.asarray(phi["ramp"], float)
    d_meas = signed / max(dist_scale, 1e-3)
    idx = np.clip(np.rint(d_meas), -RAMP_R, RAMP_R).astype(int)
    out = ramp[idx + RAMP_R].astype(np.float32)
    noise = rng.standard_normal(out.shape).astype(np.float32)
    corr = float(phi.get("corr") or 0.5) * dist_scale
    if corr > 0.4:
        noise = cv2.GaussianBlur(noise, (0, 0), corr)
    noise /= float(noise.std()) + 1e-6
    ink_now = d_meas < -0.5
    out += noise * np.where(ink_now, float(phi.get("ink_sigma") or 0), float(phi.get("paper_sigma") or 0))
    for mask, level in ((ink_now, phi.get("ink_level")), (~ink_now, phi.get("paper_level"))):
        if mask.sum() >= 5 and level is not None:
            out[mask] += float(level) - float(np.median(out[mask]))
    return np.clip(out, 0, 255).astype(np.uint8)
