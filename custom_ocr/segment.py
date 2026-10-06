"""Ways to split a cropped string image into N characters, given the true text."""
from pathlib import Path
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
from sklearn.cluster import KMeans

EIDOLON = Path(__file__).with_name("fonts") / "eidolon-script-regular.ttf"
_FONTS = {}


def prior_w(c):
    """Rough relative glyph width (an 'i' is narrow, an 'm' is wide)."""
    if c in "iIl1.,:;|!'": return 0.45
    if c in "fjrtJ ": return 0.7
    if c in "mwMW@": return 1.5
    return 1.0


BASE_FRAC = 0.75                                 # floor (baseline) as a fraction of the canonical frame


def _stretch(g):
    g = g.astype(np.float32)
    lo, hi = float(g.min()), float(max(np.percentile(g, 90), g.min() + 1))
    return np.clip((g - lo) * 255 / (hi - lo), 0, 255).astype(np.uint8)


def _blit(src, dest_y, canvas):
    """Paste `src` into `canvas` at row `dest_y` (negative clips the top)."""
    h = src.shape[0]
    y0 = max(0, dest_y)
    y1 = min(canvas.shape[0], dest_y + h)
    if y1 <= y0:
        return
    s0 = y0 - dest_y
    canvas[y0:y1] = src[s0:s0 + (y1 - y0)]


def to_ink(gray, floor_y=None, frame_h=64):
    """Dark ink on a light background, contrast stretched.

    Without `floor_y`, trim to the ink bbox and return `(gray, ink, None)`.
    With `floor_y` (baseline row in `gray`), trim only the empty side margins,
    then scale so that row lands on `BASE_FRAC` of a `frame_h`-tall frame.
    The top of the crop stays the top of the frame, so cap height is shared
    across samples; descenders below the floor are kept until the frame ends.
    """
    gray = np.asarray(gray)
    if gray.ndim == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_RGB2GRAY)
    _, b = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    if (b > 0).mean() > 0.5:
        gray, b = 255 - gray, 255 - b
    ink = b > 0
    ys, xs = np.where(ink)
    if len(xs) == 0:
        raise ValueError("No ink found in the crop")
    if floor_y is None:
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        return _stretch(gray[y0:y1, x0:x1]), ink[y0:y1, x0:x1], None

    x0, x1 = max(0, int(xs.min()) - 1), min(gray.shape[1], int(xs.max()) + 2)
    gray, ink = gray[:, x0:x1], ink[:, x0:x1]
    h_in = gray.shape[0]
    floor_y = float(np.clip(floor_y, 0, h_in - 1))
    g = _stretch(gray)
    base = int(round(frame_h * BASE_FRAC))
    scale = min(base / max(floor_y, 1.0), 8.0)
    if g.shape[1] * scale > 8000:
        scale = 8000 / g.shape[1]
    new_w = max(1, int(round(g.shape[1] * scale)))
    new_h = max(1, int(round(h_in * scale)))
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    g = cv2.resize(g, (new_w, new_h), interpolation=interp)
    ink_r = cv2.resize(ink.astype(np.uint8), (new_w, new_h), interpolation=cv2.INTER_NEAREST) > 0
    dest = base - int(round(floor_y * new_h / h_in))
    bg = int(np.percentile(g, 95))
    frame = np.full((frame_h, new_w), bg, np.uint8)
    mask = np.zeros((frame_h, new_w), bool)
    _blit(g, dest, frame)
    _blit(ink_r, dest, mask)
    return frame, mask, base


def _expected(text, W):
    w = np.array([prior_w(c) for c in text])
    return np.concatenate([[0], np.cumsum(w) / w.sum() * W])


def _font(size):
    size = max(8, int(size))
    if size not in _FONTS:
        _FONTS[size] = ImageFont.truetype(str(EIDOLON), size)
    return _FONTS[size]


def _advances(text, size=200):
    f = _font(size)
    return np.array([max(float(f.getlength(c)), 0.5) for c in text])


def _eidolon_edges(text, W, size=200):
    w = _advances(text, size)
    return np.concatenate([[0.0], np.cumsum(w) / w.sum() * W])


def _band(ink, floor):
    """Rows from the top of the frame down to the floor. Descenders live below that."""
    h = ink.shape[0]
    y1 = int(round(h * BASE_FRAC)) if floor is None else int(np.clip(round(floor), 1, h))
    return ink[:y1]


def _snap(prior, cost):
    """Move each interior boundary to the cheapest column near it."""
    W, n = len(cost), len(prior) - 1
    avg, out = W / max(n, 1), [0.0]
    for c in prior[1:-1]:
        lo = int(max(out[-1] + 1, c - 0.4 * avg))
        hi = int(min(W - 1, c + 0.4 * avg))
        if hi < lo:
            out.append(max(c, out[-1] + 1))
            continue
        window = cost[lo:hi + 1]
        near = np.flatnonzero(window <= window.min() + 0.5)
        out.append(lo + near[np.argmin(np.abs(near - (c - lo)))])
    return np.array(out + [W])


def equal(ink, text, gray=None, floor=None):
    return np.linspace(0, ink.shape[1], len(text) + 1)


def width_prior(ink, text, gray=None, floor=None):
    return _expected(text, ink.shape[1])


def valley(ink, text, gray=None, floor=None):
    """Snap each prior-based cut to the nearest low point of the vertical ink profile."""
    prof = np.convolve(ink.sum(0).astype(float), np.ones(3) / 3, "same")
    return _snap(_expected(text, ink.shape[1]), prof)


def kmeans(ink, text, gray=None, floor=None):
    """Cluster ink-pixel x-coordinates into N groups (init from width priors); cut between centres."""
    W = ink.shape[1]
    e = _expected(text, W)
    xs = np.where(ink)[1].reshape(-1, 1)
    if len(xs) < len(text):
        return e
    km = KMeans(len(text), init=((e[:-1] + e[1:]) / 2).reshape(-1, 1), n_init=1).fit(xs)
    c = np.sort(km.cluster_centers_.ravel())
    return np.concatenate([[0], (c[:-1] + c[1:]) / 2, [W]])


def dp(ink, text, lam=2.0, gray=None, floor=None):
    """Dynamic programming: pick cuts minimising  sum(width error^2) + lam * ink_on_cut."""
    n, W = len(text), ink.shape[1]
    prof = ink.sum(0).astype(float); prof /= prof.max() + 1e-9
    e = np.diff(_expected(text, W))
    INF = 1e18
    cost = np.full((n + 1, W + 1), INF); back = np.zeros((n + 1, W + 1), int); cost[0, 0] = 0
    for k in range(1, n + 1):
        hi = W if k == n else W - (n - k)
        for b in range(k, hi + 1):
            a = np.arange(k - 1, b)
            tot = cost[k - 1, a] + ((b - a - e[k - 1]) / e[k - 1]) ** 2
            j = int(np.argmin(tot))
            cost[k, b] = tot[j] + (lam * prof[min(b, W - 1)] if k < n else 0)
            back[k, b] = a[j]
    cuts, b = [W], W
    for k in range(n, 0, -1):
        b = back[k, b]; cuts.append(b)
    return np.array(cuts[::-1])


def eidolon_widths(ink, text, gray=None, floor=None):
    """Scale Eidolon Script's real advance widths to the crop."""
    return _eidolon_edges(text, ink.shape[1])


def cap_gaps(ink, text, gray=None, floor=None):
    """Valleys in the ink above the floor, so descenders cannot bridge a gap."""
    prof = np.convolve(_band(ink, floor).sum(0).astype(float), np.ones(5) / 5, "same")
    return _snap(_eidolon_edges(text, ink.shape[1]), prof)


def _assign(adv, widths):
    """How many characters each region owns. Regions stay in order and each gets one."""
    n, k = len(adv), len(widths)
    if k >= n:
        return [1] * n
    pref = np.concatenate([[0.0], np.cumsum(adv)])
    share = np.asarray(widths, float)
    share = share / share.sum()
    total = pref[-1]
    INF = 1e18
    cost = np.full((k + 1, n + 1), INF)
    back = np.zeros((k + 1, n + 1), int)
    cost[0, 0] = 0
    for j in range(1, k + 1):
        for i in range(j, n - (k - j) + 1):
            for t in range(1, i - (j - 1) + 1):
                a = i - t
                c = cost[j - 1, a] + ((pref[i] - pref[a]) / total - share[j - 1]) ** 2
                if c < cost[j, i]:
                    cost[j, i], back[j, i] = c, t
    counts, i = [], n
    for j in range(k, 0, -1):
        t = int(back[j, i]) or 1
        counts.append(t)
        i -= t
    return counts[::-1]


def components(ink, text, gray=None, floor=None):
    """Merge broken strokes, then split whatever is still touching using Eidolon widths."""
    band = _band(ink, floor)
    n, W = len(text), ink.shape[1]
    _, _, stats, _ = cv2.connectedComponentsWithStats(band.astype(np.uint8), 8)
    boxes = [[int(s[0]), int(s[0] + s[2])] for s in stats[1:] if s[4] >= 3]
    boxes.sort()
    while len(boxes) > n and len(boxes) > 1:
        gaps = [boxes[i + 1][0] - boxes[i][1] for i in range(len(boxes) - 1)]
        i = int(np.argmin(gaps))
        # A speck inside a letter (a descender nub, a dot) must not shrink the parent.
        boxes[i][1] = max(boxes[i][1], boxes[i + 1][1])
        del boxes[i + 1]
    if not boxes:
        return _eidolon_edges(text, W)
    edges = [0]
    for i in range(len(boxes) - 1):
        edges.append(int(round((boxes[i][1] + boxes[i + 1][0]) / 2)))
    edges.append(W)
    counts = _assign(_advances(text), [edges[i + 1] - edges[i] for i in range(len(edges) - 1)])
    cuts, ci = [0.0], 0
    adv = _advances(text)
    for a, b, k in zip(edges, edges[1:], counts):
        part = adv[ci:ci + k]
        bounds = np.concatenate([[0.0], np.cumsum(part)])
        bounds = a + bounds / bounds[-1] * (b - a)
        cuts.extend(bounds[1:])
        ci += k
    return np.array(cuts)


def _render_string(text, height, floor):
    """Eidolon rendering of `text` with the baseline on `floor`, plus the pen position of each cut."""
    base = int(round(height * BASE_FRAC)) if floor is None else int(np.clip(round(floor), 1, height - 1))
    _, top, _, _ = _font(200).getbbox("H", anchor="ls")
    font = _font(base / max(-top / 200, 0.2))
    widths = [max(float(font.getlength(c)), 0.5) for c in text]
    width = max(1, int(np.ceil(sum(widths))) + 2)
    im = Image.new("L", (width, height), 255)
    draw, pen, bounds = ImageDraw.Draw(im), 1.0, [1.0]
    for ch, w in zip(text, widths):
        draw.text((pen, base), ch, font=font, fill=0, anchor="ls")
        pen += w
        bounds.append(pen)
    return np.array(im), np.array(bounds)


def _ncc(a, b):
    a = a.astype(np.float32); b = b.astype(np.float32)
    a = a - a.mean(); b = b - b.mean()
    return float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-6))


def eidolon_template(ink, text, gray=None, floor=None):
    """Slide an Eidolon rendering of the whole string over the crop and read its glyph edges."""
    img = ink.astype(np.uint8) * 255 if gray is None else np.asarray(gray)
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    H, W = img.shape
    rend, bounds = _render_string(text, H, floor)
    best = (-1e9, 1.0, 0.0)
    for scale in np.linspace(0.75, 1.35, 25):
        ws = max(1, int(round(rend.shape[1] * scale)))
        scaled = cv2.resize(rend, (ws, H), interpolation=cv2.INTER_AREA)
        if ws <= W:
            for off in range(0, W - ws + 1, max(1, (W - ws) // 24)):
                score = _ncc(img[:, off:off + ws], scaled)
                if score > best[0]:
                    best = (score, scale, float(off))
        else:
            for off in range(0, ws - W + 1, max(1, (ws - W) // 24)):
                score = _ncc(img, scaled[:, off:off + W])
                if score > best[0]:
                    best = (score, scale, -float(off))
    _, scale, off = best
    return bounds * scale + off - bounds[0] * scale


def necks(ink, text, gray=None, floor=None):
    """Cut where a vertical line crosses the least stroke, not the least ink."""
    band = _band(ink, floor)
    dist = cv2.distanceTransform(band.astype(np.uint8), cv2.DIST_L2, 3)
    return _snap(_eidolon_edges(text, ink.shape[1]), dist.max(0))


METHODS = {
    "1 · Equal width": equal,
    "2 · Width prior": width_prior,
    "3 · Ink-profile valleys": valley,
    "4 · K-means on ink pixels": kmeans,
    "5 · Dynamic programming": dp,
    "6 · Eidolon widths": eidolon_widths,
    "7 · Cap-band gaps": cap_gaps,
    "8 · Components, then split": components,
    "9 · Eidolon template": eidolon_template,
    "10 · Thinnest necks": necks,
}


def segment(ink, text, method, gray=None, floor=None):
    W, n = ink.shape[1], len(text)
    if n == 1:
        return np.array([0, W])
    cuts = np.round(METHODS[method](ink, text, gray=gray, floor=floor)).astype(int)
    cuts[0], cuts[-1] = 0, W
    for i in range(1, n):                       # force strictly increasing
        cuts[i] = max(cuts[i], cuts[i - 1] + 1)
    for i in range(n - 1, 0, -1):
        cuts[i] = min(cuts[i], cuts[i + 1] - 1)
    return cuts


def slice_chars(gray, ink, cuts):
    """Per-character crops: full string height (keeps baseline), trimmed horizontally."""
    out = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        g, m = gray[:, a:b], ink[:, a:b]
        cols = np.where(m.any(0))[0]
        if len(cols):
            g = g[:, max(cols.min() - 1, 0): cols.max() + 2]
        out.append(g if g.shape[1] else gray[:, a:a + 1])
    return out


def clamp_lines(lines, width):
    """Keep each cut as a top x and a bottom x, ordered so the lines do not cross."""
    width = int(width)
    cleaned = []
    for item in lines or []:
        try:
            a, b = int(round(float(item[0]))), int(round(float(item[1])))
        except (TypeError, ValueError, IndexError):
            continue
        cleaned.append([a, b])
    if not cleaned or width < 2:
        return [[0, 0] for _ in cleaned]

    def mono(xs):
        out = []
        last = len(xs) - 1
        for i, x in enumerate(xs):
            hi = width - 1 - (last - i)
            lo = 1 if not out else out[-1] + 1
            if hi < 1:
                hi = 1
            if lo > hi:
                lo = hi
            out.append(int(min(max(int(x), lo), hi)))
        return out

    tops = mono([a for a, _ in cleaned])
    bots = mono([b for _, b in cleaned])
    return [[a, b] for a, b in zip(tops, bots)]


def slice_lines(gray, ink, lines):
    """Slice on straight cuts. A cut is the column at the top and the column at the bottom.

    Vertical cuts match slice_chars. A slanted cut keeps the full height and paints
    the neighboring letter as paper, so a script join can lean without taking the next glyph.
    """
    gray = np.asarray(gray)
    ink = np.asarray(ink, bool)
    h, w = gray.shape[:2]
    lines = clamp_lines(lines, w)
    if not lines or all(a == b for a, b in lines):
        cuts = [0] + [a for a, _ in lines] + [w]
        return slice_chars(gray, ink, cuts)
    ys = np.arange(h, dtype=np.float64)
    denom = max(h - 1, 1)
    bounds = [np.zeros(h)]
    for top, bot in lines:
        bounds.append(top + (bot - top) * (ys / denom))
    bounds.append(np.full(h, float(w)))
    bounds = np.stack(bounds)
    for i in range(1, bounds.shape[0]):
        bounds[i] = np.maximum(bounds[i], bounds[i - 1] + 1)
    for i in range(bounds.shape[0] - 2, -1, -1):
        bounds[i] = np.minimum(bounds[i], bounds[i + 1] - 1)
    bounds[0], bounds[-1] = 0, w
    xs = np.arange(w)
    out = []
    for i in range(bounds.shape[0] - 1):
        region = (xs[None, :] >= bounds[i][:, None]) & (xs[None, :] < bounds[i + 1][:, None])
        g = np.full((h, w), 255, np.uint8)
        g[region] = gray[region]
        cols = np.flatnonzero(region.any(0))
        if len(cols) == 0:
            out.append(np.full((h, 1), 255, np.uint8))
            continue
        g = g[:, cols[0]: cols[-1] + 1]
        sub = ink[:, cols[0]: cols[-1] + 1] & region[:, cols[0]: cols[-1] + 1]
        ink_cols = np.flatnonzero(sub.any(0))
        if len(ink_cols):
            g = g[:, max(int(ink_cols.min()) - 1, 0): int(ink_cols.max()) + 2]
        out.append(g if g.shape[1] else np.full((h, 1), 255, np.uint8))
    return out
