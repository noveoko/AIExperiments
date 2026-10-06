"""Glyph store, augmentation, and string composition."""
import numpy as np, cv2
from pathlib import Path
from PIL import Image

CH = 64                                              # canonical glyph height


def canon(g):
    return cv2.resize(g, (max(1, round(g.shape[1] * CH / g.shape[0])), CH), interpolation=cv2.INTER_AREA)


def trim(g):
    m = g < (int(g.max()) + int(g.min())) / 2
    cols = np.where(m.any(0))[0]
    return g[:, max(cols.min() - 1, 0): cols.max() + 2] if len(cols) else g


def augment(g, rng):
    """Random affine + stroke thickness + blur + noise. Keeps the vertical frame (baseline)."""
    H, W = g.shape; pad = max(4, H // 6)
    bg = int(np.percentile(g, 90))
    c = cv2.copyMakeBorder(g, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=bg)
    ang, sc, sh = rng.uniform(-4, 4), rng.uniform(.93, 1.07), rng.uniform(-.1, .1)
    M = cv2.getRotationMatrix2D((c.shape[1] / 2, c.shape[0] / 2), ang, sc)
    M[0, 1] += sh; M[1, 2] += rng.integers(-1, 2)
    c = cv2.warpAffine(c, M, (c.shape[1], c.shape[0]), borderValue=bg, flags=cv2.INTER_LINEAR)
    k = int(rng.choice([-1, 0, 0, 1]))              # ink is dark -> erode(gray) = thicker stroke
    if k: c = (cv2.erode if k > 0 else cv2.dilate)(c, np.ones((2, 2), np.uint8))
    s = rng.uniform(0, .8)
    if s > .2: c = cv2.GaussianBlur(c, (0, 0), s)
    c = np.clip(c + rng.normal(0, 4, c.shape), 0, 255).astype(np.uint8)
    return trim(c[pad:pad + H])


# ---------- disk persistence (file names use code points: safe on case-insensitive disks)
def save_store(store, d):
    d = Path(d); d.mkdir(parents=True, exist_ok=True)
    for f in d.glob("*.png"): f.unlink()
    for ch, lst in store.items():
        for i, g in enumerate(lst):
            Image.fromarray(g).save(d / f"U{ord(ch):05X}_{i}.png")


def load_store(d):
    store = {}
    for f in sorted(Path(d).glob("U*_*.png")):
        ch = chr(int(f.stem[1:].split("_")[0], 16))
        store.setdefault(ch, []).append(np.array(Image.open(f).convert("L")))
    return store


# ---------- compose a full string image from exemplars
def compose(text, store, rng):
    parts = []
    for ch in text:
        if ch == " ": parts.append(np.full((CH, int(CH * rng.uniform(.25, .45))), 255, np.uint8))
        else:
            g = store[ch][rng.integers(len(store[ch]))]
            parts.append(g if g.shape[0] == CH else canon(g))
        parts.append(np.full((CH, int(rng.integers(0, CH // 8 + 1)) + 1), 255, np.uint8))
    p = int(rng.integers(4, 16))
    img = cv2.copyMakeBorder(np.hstack(parts), p, p, p, p, cv2.BORDER_CONSTANT, value=255)
    s = rng.uniform(.8, 1.2)
    img = cv2.resize(img, None, fx=s, fy=s * rng.uniform(.9, 1.1), interpolation=cv2.INTER_LINEAR)
    return (img.astype(float) * rng.integers(200, 256) / 255).astype(np.uint8)
