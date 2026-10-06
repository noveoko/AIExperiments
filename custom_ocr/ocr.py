"""CRNN + CTC word recogniser trained with heavy on-the-fly degradation."""
import os
from pathlib import Path
import numpy as np, cv2, torch, torch.nn as nn
from PIL import Image

IMG_H = 32
DEV = "cuda" if torch.cuda.is_available() else "cpu"


def to_gray(img):
    """One-channel uint8. Alpha is laid on white paper. A 3-channel array is OpenCV BGR."""
    if isinstance(img, Image.Image):
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            rgba = img.convert("RGBA")
            rgb = Image.new("RGB", rgba.size, (255, 255, 255))
            rgb.paste(rgba, mask=rgba.getchannel("A"))
            img = rgb
        return np.asarray(img.convert("L"))
    g = np.asarray(img)
    if g.ndim == 2:
        return g if g.dtype == np.uint8 else np.clip(g, 0, 255).astype(np.uint8)
    if g.shape[2] == 4:
        bgr = g[:, :, :3].astype(np.float32)
        a = g[:, :, 3:4].astype(np.float32) / 255.0
        g = np.clip(bgr * a + 255.0 * (1.0 - a), 0, 255).astype(np.uint8)
    return cv2.cvtColor(g, cv2.COLOR_BGR2GRAY)


def degrade(g, rng):
    """Simulate bad scans: scale, morphology, bleed, threshold, blur, noise, JPEG."""
    g = to_gray(g)
    h, w = g.shape
    if rng.random() < 0.8:
        fy, fx = float(rng.uniform(0.45, 1.6)), float(rng.uniform(0.45, 1.6))
        g = cv2.resize(g, (max(8, int(round(w * fx))), max(8, int(round(h * fy)))), interpolation=cv2.INTER_AREA)
    if rng.random() < 0.7:
        s = float(rng.uniform(0.25, 0.8))
        g = cv2.resize(g, (max(8, int(g.shape[1] * s)), max(8, int(g.shape[0] * s))), interpolation=cv2.INTER_AREA)
    if rng.random() < 0.6:
        k = int(rng.choice([3, 5]))
        g = cv2.GaussianBlur(g, (k, k), 0)
    if rng.random() < 0.5:
        k = int(rng.choice([2, 3]))
        ker = np.ones((k, k), np.uint8)
        op = cv2.erode if rng.random() < 0.5 else cv2.dilate
        for _ in range(int(rng.integers(1, 3))):
            g = op(g, ker)
    if rng.random() < 0.45:
        bled = cv2.blur(g, (int(rng.choice([3, 5, 7])), 1))
        mix = float(rng.uniform(0.35, 0.75))
        g = np.clip(g.astype(np.float32) * (1 - mix) + bled.astype(np.float32) * mix, 0, 255).astype(np.uint8)
    g = 128 + (g.astype(np.float32) - 128) * float(rng.uniform(0.25, 1.4)) + float(rng.uniform(-40, 40))
    g = np.clip(g + rng.normal(0, float(rng.uniform(0, 25)), g.shape), 0, 255).astype(np.uint8)
    if rng.random() < 0.35:
        if rng.random() < 0.5:
            _, g = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            bs = int(rng.choice([11, 15, 21]))
            if min(g.shape) <= bs:
                _, g = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            else:
                g = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, bs, int(rng.integers(-5, 8)))
    if rng.random() < 0.6:
        _, buf = cv2.imencode(".jpg", g, [cv2.IMWRITE_JPEG_QUALITY, int(rng.integers(10, 60))])
        g = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
    return g


def prep(g):
    """Height 32, aspect kept, ink bright in [0, 1]. Right pad is 0, the training paper color."""
    g = to_gray(g)
    h, w = g.shape
    if h < 1 or w < 1:
        g = np.full((8, 16), 255, np.uint8)
        h, w = g.shape
    new_w = max(1, int(round(w * IMG_H / h)))
    resized = cv2.resize(g, (new_w, IMG_H), interpolation=cv2.INTER_AREA)
    inv = (255.0 - resized.astype(np.float32)) / 255.0
    pad = (-inv.shape[1]) % 4
    if inv.shape[1] + pad < 16:
        pad += 16 - (inv.shape[1] + pad)
    if pad:
        inv = np.pad(inv, ((0, 0), (0, pad)), mode="constant", constant_values=0)
    return inv


def tensor_view(x):
    """Ink-bright uint8 view of a (1, H, W) or (H, W) float tensor."""
    a = np.asarray(x, np.float32)
    if a.ndim == 3:
        a = a[0]
    return np.clip(a * 255.0, 0, 255).astype(np.uint8)


def save_model_inputs(upload, train, dest, rng=None):
    """Write the float tensor that enters forward, plus a clean and a degraded training row."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng() if rng is None else rng
    rows = {
        "poniatowskiego": prep(upload)[None],
        "train_clean": prep(train)[None],
        "train_degraded": prep(degrade(train, rng))[None],
    }
    for name, arr in rows.items():
        np.save(dest / f"{name}.npy", arr.astype(np.float32))
        cv2.imwrite(str(dest / f"{name}.png"), tensor_view(arr))
    return rows["poniatowskiego"], rows["train_clean"]


class CRNN(nn.Module):
    def __init__(s, nc):
        super().__init__()
        blk = lambda i, o: [nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU()]
        s.cnn = nn.Sequential(*blk(1, 32), nn.MaxPool2d(2), *blk(32, 64), nn.MaxPool2d(2),
                              *blk(64, 128), nn.MaxPool2d((2, 1)), *blk(128, 128), nn.MaxPool2d((2, 1)))
        s.rnn = nn.LSTM(256, 128, num_layers=2, bidirectional=True, batch_first=True)
        s.fc = nn.Linear(256, nc)

    def forward(s, x):                                  # x: (B,1,32,W) -> (B,W/4,C)
        f = s.cnn(x).permute(0, 3, 1, 2).flatten(2)
        return s.fc(s.rnn(f)[0])


def _batch(items, c2i, rng, augment):
    imgs = [prep(degrade(g, rng) if augment else g) for g, _ in items]
    W = max(i.shape[1] for i in imgs)
    x = np.zeros((len(imgs), 1, IMG_H, W), np.float32)
    for i, im in enumerate(imgs): x[i, 0, :, :im.shape[1]] = im
    il = torch.tensor([im.shape[1] // 4 for im in imgs])
    tl = torch.tensor([len(t) for _, t in items])
    tg = torch.tensor([c2i[c] for _, t in items for c in t])
    return torch.from_numpy(x).to(DEV), tg, il, tl


def _decode(logits, chars):
    out = []
    for seq in logits.argmax(-1).cpu().numpy():
        s, prev = [], 0
        for k in seq:
            if k != prev and k != 0: s.append(chars[k - 1])
            prev = k
        out.append("".join(s))
    return out


def fingerprint(items):
    """Identity of a training list: text order and the sorted alphabet."""
    order = [t for _, t in items]
    return {"n": len(order), "order": order, "chars": sorted({c for t in order for c in t})}


def _atomic_save(obj, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    torch.save(obj, tmp)
    os.replace(tmp, path)


def _checkpoint_blob(model, opt, chars, epoch, epochs, bs, lr, rng, fp):
    return {
        "state": model.state_dict(),
        "optim": opt.state_dict(),
        "chars": chars,
        "epoch": int(epoch),
        "epochs": int(epochs),
        "bs": int(bs),
        "lr": float(lr),
        "rng": rng.bit_generator.state,
        "fingerprint": fp,
    }


def peek_checkpoint(path):
    """Epoch and dataset identity, without keeping the weights."""
    blob = torch.load(path, map_location="cpu", weights_only=False)
    return {k: blob[k] for k in ("epoch", "epochs", "bs", "lr", "chars", "fingerprint")}


def load_checkpoint(path):
    """Full resume blob, tensors on the training device."""
    return torch.load(path, map_location=DEV, weights_only=False)


def load_model(path):
    """Inference pair from a weights file or a training checkpoint."""
    blob = torch.load(path, map_location=DEV, weights_only=False)
    chars = list(blob["chars"])
    model = CRNN(len(chars) + 1).to(DEV)
    model.load_state_dict(blob["state"])
    model.eval()
    return model, chars


def same_fingerprint(a, b):
    return a["n"] == b["n"] and list(a["order"]) == list(b["order"]) and list(a["chars"]) == list(b["chars"])


def can_resume(ckpt, items):
    """True when this checkpoint was written for this training list."""
    return bool(ckpt) and "fingerprint" in ckpt and same_fingerprint(ckpt["fingerprint"], fingerprint(items))


def train(items, epochs, bs, lr, progress, ckpt_path=None, weights_path=None, resume=None):
    """Train for `epochs` passes. After each finished epoch, write a resume checkpoint.

    `resume` is a dict from load_checkpoint. Training then continues at the next
    epoch with the same weights, Adam state, and numpy draws. A crash mid-epoch
    leaves the previous finished epoch on disk.
    """
    rng = np.random.default_rng(0)
    fp = fingerprint(items)
    chars = list(fp["chars"]); c2i = {c: i + 1 for i, c in enumerate(chars)}
    texts = sorted({t for _, t in items}); rng.shuffle(texts)
    held = set(texts[:max(1, len(texts) // 10)]) if len(texts) > 1 else set()   # split by *string*
    tr = [x for x in items if x[1] not in held]; va = [x for x in items if x[1] in held]
    model = CRNN(len(chars) + 1).to(DEV)
    opt = torch.optim.Adam(model.parameters(), lr=lr); ctc = nn.CTCLoss(zero_infinity=True)
    start = 0
    if resume:
        if not same_fingerprint(resume["fingerprint"], fp):
            raise ValueError("Checkpoint dataset does not match the current training images.")
        if list(resume["chars"]) != chars:
            raise ValueError("Checkpoint alphabet does not match this dataset.")
        model.load_state_dict(resume["state"])
        opt.load_state_dict(resume["optim"])
        for group in opt.param_groups:
            group["lr"] = lr
        rng.bit_generator.state = resume["rng"]
        start = int(resume["epoch"]) + 1
    for ep in range(start, epochs):
        model.train(); idx = rng.permutation(len(tr)); losses = []
        for i in range(0, len(idx), bs):
            x, tg, il, tl = _batch([tr[j] for j in idx[i:i + bs]], c2i, rng, True)
            lp = model(x).log_softmax(2).permute(1, 0, 2)
            loss = ctc(lp, tg, il, tl)
            opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 5); opt.step()
            losses.append(loss.item())
        acc = None
        if va:
            model.eval(); vr = np.random.default_rng(1)
            with torch.no_grad():
                x, *_ = _batch(va, c2i, vr, True)
                acc = float(np.mean([p == t for p, (_, t) in zip(_decode(model(x), chars), va)]))
        blob = _checkpoint_blob(model, opt, chars, ep, epochs, bs, lr, rng, fp)
        if ckpt_path:
            _atomic_save(blob, ckpt_path)
        if weights_path:
            _atomic_save({"state": blob["state"], "chars": chars}, weights_path)
        progress(ep, epochs, float(np.mean(losses)), acc)
    return model, chars


def predict(model, chars, gray):
    model.eval()
    with torch.no_grad():
        x = torch.from_numpy(prep(gray))[None, None].to(DEV)
        return _decode(model(x), chars)[0]
