import hashlib, io, string
from pathlib import Path
import numpy as np, cv2, pandas as pd, streamlit as st
from PIL import Image
import segment as S, glyphs as G, ocr as O, cropper, dividers, morphology as M

WORK = Path("work"); GDIR = WORK / "glyphs"; DDIR = WORK / "dataset"
st.set_page_config(page_title="Font → OCR studio", layout="wide")
ss = st.session_state
for k, v in dict(store=None, sample=None, sid=0, method=list(S.METHODS)[0],
                 synth=set(), dataset=[], model=None, morph=None).items():
    if k not in ss: ss[k] = v
if ss.store is None: ss.store = G.load_store(GDIR)

STEPS = ["1 · Crop & label", "2 · Pick segmentation", "3 · Pick exemplars",
         "4 · Complete alphabet", "5 · Generate dataset", "6 · Train & test OCR"]
step = st.sidebar.radio("Step", STEPS)
st.sidebar.caption(f"Glyphs stored: {len(ss.store)} characters, {sum(map(len, ss.store.values()))} images")


def _even_cuts(smp):
    return S.segment(smp["ink"], smp["text"], "1 · Equal width", smp["gray"], smp.get("floor")).tolist()


def _lines_of(cuts):
    return [[int(c), int(c)] for c in list(cuts)[1:-1]]


def _remember(smp, lines):
    """Store the drawn cuts. `cuts` is where each line crosses the floor."""
    H, W = smp["ink"].shape[:2]
    lines = S.clamp_lines(lines, W)
    y = H // 2 if smp.get("floor") is None else int(np.clip(smp["floor"], 0, H - 1))
    cuts = [0]
    for top, bot in lines:
        x = top if H <= 1 else top + (bot - top) * y / (H - 1)
        cuts.append(int(round(x)))
    cuts.append(W)
    for i in range(1, len(cuts)):
        cuts[i] = max(cuts[i], cuts[i - 1] + 1)
    for i in range(len(cuts) - 2, -1, -1):
        cuts[i] = min(cuts[i], cuts[i + 1] - 1)
    cuts[0], cuts[-1] = 0, W
    rec = {"sid": smp["sid"], "n": len(smp["text"]), "w": W, "h": H, "lines": lines, "cuts": cuts}
    ss.manual_cuts = rec
    return rec


def _cuts_record(smp):
    """Saved splits for this crop. Missing means step 2 has not been opened."""
    H, W = smp["ink"].shape[:2]
    n = len(smp["text"])
    rec = ss.get("manual_cuts")
    if rec and rec.get("sid") == smp["sid"] and rec.get("n") == n and rec.get("w") == W and rec.get("h", H) == H:
        return rec
    return None


def _crops_for(smp, rec):
    if rec is None:
        return S.slice_chars(smp["gray"], smp["ink"], _even_cuts(smp))
    if rec.get("lines") is not None:
        return S.slice_lines(smp["gray"], smp["ink"], rec["lines"])
    return S.slice_chars(smp["gray"], smp["ink"], rec["cuts"])


def _thumbs(smp, crops):
    cols = st.columns(len(smp["text"]))
    for col, ch, g in zip(cols, smp["text"], crops):
        label = "space" if ch == " " else ch
        col.image(g, caption=label, width="stretch", alt=f"Slice for {label}")


def _show_splits(smp, cuts, alt):
    vis = cv2.cvtColor(np.asarray(smp["gray"]), cv2.COLOR_GRAY2RGB)
    for x in list(cuts)[1:-1]:
        cv2.line(vis, (int(x), 0), (int(x), vis.shape[0] - 1), (255, 0, 0), 1)
    fy = smp.get("floor")
    if fy is not None:
        y = int(np.clip(fy, 0, vis.shape[0] - 1))
        cv2.line(vis, (0, y), (vis.shape[1] - 1, y), (255, 176, 0), 1)
    st.image(vis, width=min(900, max(300, vis.shape[1] * 3)), alt=alt)
    _thumbs(smp, S.slice_chars(smp["gray"], smp["ink"], cuts))


# ------------------------------------------------------------------ 1
if step == STEPS[0]:
    st.header("Crop a multi-character string")
    st.caption("Rotate until the text is level. Put the top of the box on the tops of the capitals "
               "and the yellow floor on the baseline, so every sample shares a size. "
               "Descenders (g, j, p, q, y) hang below the floor.")
    up = st.file_uploader("Upload an image", type=["png", "jpg", "jpeg", "bmp", "tif", "tiff"])
    if up:
        raw = up.getvalue()
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        digest = hashlib.sha1(raw).hexdigest()[:12]
        c1, c2 = st.columns(2)
        with c1:
            spec = cropper.widget(raw, key=f"crop-{digest}")
        cropped, floor_y = cropper.apply(img, spec)
        with c2:
            st.caption("Preview — the center of the yellow band is the floor")
            st.image(cropper.mark_floor(cropped, floor_y), width="stretch",
                     alt="Cropped snippet with the floor marked in yellow")
        text = st.text_input("What does the crop say? (exact, case-sensitive)", placeholder="Warszawska")
        if st.button("Segment →", type="primary", disabled=not text):
            try:
                g, ink, floor = S.to_ink(np.array(cropped.convert("L")), floor_y, frame_h=G.CH)
                ss.sid += 1
                ss.sample = dict(gray=g, ink=ink, text=text, sid=ss.sid, floor=floor)
                st.success("Done. Go to step 2.")
            except ValueError as e:
                st.error(str(e))

# ------------------------------------------------------------------ 2
elif step == STEPS[1]:
    st.header("Split the characters")
    smp = ss.sample
    if not smp: st.info("Crop a string first."); st.stop()
    text, sid = smp["text"], smp["sid"]
    W, n = smp["ink"].shape[1], len(text)
    if ss.get("auto_for") != sid:
        ss.auto_for = sid
        ss.show_auto = False
    if "div_gen" not in ss:
        ss.div_gen = 0
    div_key = f"dividers-{sid}-{ss.div_gen}"
    if ss.get("pending_auto"):
        chosen = ss.pending_auto
        ss.pending_auto = None
        fresh = _lines_of(S.segment(smp["ink"], text, chosen, smp["gray"], smp.get("floor")).tolist())
        ss.div_gen += 1
        div_key = f"dividers-{sid}-{ss.div_gen}"
        ss[div_key] = {"lines": fresh}
        _remember(smp, fresh)
    if n > 1 and st.button("Reset lines"):
        even = _lines_of(_even_cuts(smp))
        ss.div_gen += 1
        div_key = f"dividers-{sid}-{ss.div_gen}"
        ss[div_key] = {"lines": even}
        _remember(smp, even)
        st.rerun()
    rec = _cuts_record(smp)
    if rec is None or rec.get("lines") is None:
        lines = _lines_of(_even_cuts(smp) if rec is None else rec["cuts"])
    else:
        lines = rec["lines"]
    stored = ss.get(div_key, {})
    stored_lines = stored.get("lines") if isinstance(stored, dict) else None
    if dividers.lines_ok(stored_lines, max(n - 1, 0), W):
        lines = stored_lines
    elif isinstance(stored, dict) and "lines" in stored:
        ss[div_key] = {"lines": S.clamp_lines(lines, W)}
    labels = ["space" if ch == " " else ch for ch in text]
    lines = dividers.widget(smp["gray"], lines, smp.get("floor"), labels, key=div_key)
    rec = _remember(smp, lines)
    _thumbs(smp, S.slice_lines(smp["gray"], smp["ink"], rec["lines"]))
    if st.button("Run automatic segmentation"):
        ss.show_auto = True
    if ss.get("show_auto"):
        st.caption("Pick a result, then use its cuts. You can still move the lines above.")
        methods = list(S.METHODS)
        if ss.method not in methods:
            ss.method = methods[0]
        for name in methods:
            try:
                auto = S.segment(smp["ink"], text, name, smp["gray"], smp.get("floor"))
            except Exception as e:
                st.warning(f"{name} failed: {e}")
                continue
            st.subheader(name)
            _show_splits(smp, auto, f"Automatic splits for {name}")
        ss.method = st.radio("Automatic approach", methods, index=methods.index(ss.method))
        if st.button("Use these cuts"):
            ss.pending_auto = ss.method
            st.rerun()

# ------------------------------------------------------------------ 3
elif step == STEPS[2]:
    st.header("Pick exemplary versions of each character")
    smp = ss.sample
    if not smp: st.info("Crop a string first."); st.stop()
    rec = _cuts_record(smp)
    if rec is None:
        st.caption("Using even spacing. Open step 2 to draw the cuts.")
    crops = _crops_for(smp, rec)
    k = st.slider("Variants per character (first = your original crop)", 4, 24, 12)
    picked = {}
    for i, (ch, g) in enumerate(zip(smp["text"], crops)):
        if ch == " ": continue
        with st.expander(f"'{ch}'  (position {i + 1})", expanded=i < 3):
            rng = np.random.default_rng(smp["sid"] * 1000 + i)
            variants = [g] + [G.augment(g, rng) for _ in range(k - 1)]
            cols = st.columns(6)
            for j, v in enumerate(variants):
                with cols[j % 6]:
                    st.image(v, width=80)
                    if st.checkbox("use", key=f"s{smp['sid']}c{i}v{j}", value=(j == 0)):
                        picked.setdefault(ch, []).append(v)
    if st.button("Save selected to alphabet", type="primary"):
        for ch, vs in picked.items():
            ss.store.setdefault(ch, []).extend(G.canon(v) for v in vs)
            ss.synth.discard(ch)
        G.save_store(ss.store, GDIR)
        st.success(f"Saved {sum(map(len, picked.values()))} glyphs.")

# ------------------------------------------------------------------ 4
elif step == STEPS[3]:
    st.header("Complete the alphabet")
    st.caption("Missing letters start as Eidolon Script. One morphology, fitted to your saved glyphs, repaints every one of them.")
    alpha = st.text_input("Characters you need", string.ascii_letters + string.digits)
    missing = [c for c in dict.fromkeys(alpha) if c not in ss.store]
    real = {c: gs for c, gs in ss.store.items() if c not in ss.synth and gs}
    st.write(f"Have **{len(alpha) - len(missing)}** / {len(alpha)}.  Missing: `{''.join(missing) or '—'}`")
    if missing and not real:
        st.info("Save at least one real glyph in step 3, then generate the rest.")
    crop_px = int(round(float(np.median([gs[0].shape[1] for gs in real.values()])))) if real else 24
    if "char_px" not in ss:
        ss.char_px = crop_px
    if real:
        st.number_input(
            "Average character width (px)",
            min_value=4, max_value=256, step=1, key="char_px",
            help="A typical generated letter is this many pixels wide. "
                 "Narrow and wide letters stay in Eidolon’s proportions.",
        )
        st.caption(f"Saved crops are about {crop_px} px wide.")
    if ss.morph and real:
        theta = ss.morph["theta"]
        phi = ss.morph.get("capture") or M.measure_capture(ss.store, ss.synth)
        note = f"Ink overlap on the saved letters: {ss.morph['iou']:.0%}."
        if ss.morph.get("holdout") is not None:
            note += f" Held out {ss.morph['holdout_char']}: {ss.morph['holdout']:.0%}."
        if ss.morph.get("fallback"):
            note += f" No Eidolon glyph for {''.join(ss.morph['fallback'])}; those use DejaVu."
        skipped = ss.morph.get("skipped") or []
        if skipped:
            shown = "".join(skipped[:24])
            extra = f" +{len(skipped) - 24}" if len(skipped) > 24 else ""
            note += f" Ignored {len(skipped)} saved glyphs whose counters were already filled ({shown}{extra})."
        note += (f" Capture: edge {phi['edge']:.1f}px, ink noise σ {phi['ink_sigma']:.0f}, "
                 f"correlation {phi['corr']:.1f}px, pixel factor {phi['pixel']}.")
        st.caption(note)
        shown = sorted(real)[:6]
        st.caption("Eidolon, the stroke, the capture, and your crop.")
        cols = st.columns(len(shown))
        for col, ch in zip(cols, shown):
            with col:
                st.image(M.preview_source(ch), caption=f"{ch} Eidolon", width=70, alt=f"Eidolon outline of {ch}")
                st.image(M.apply(ch, theta), caption="stroke", width=70, alt=f"Stroke of {ch}")
                caught = M.render(ch, theta, phi, np.random.default_rng(ord(ch)), int(ss.char_px))
                st.image(caught, caption="captured", width=70, alt=f"Captured {ch}")
                st.image(real[ch][0], caption="yours", width=70, alt=f"Saved crop of {ch}")
    if missing and st.button("Generate missing letters", type="primary", disabled=not real):
        with st.spinner("Fitting one style to the saved letters…"):
            ss.morph = M.fit(ss.store, ss.synth)
            ss.morph["capture"] = M.measure_capture(ss.store, ss.synth)
        theta, phi = ss.morph["theta"], ss.morph["capture"]
        for c in missing:
            rng = np.random.default_rng(ord(c))
            base = M.render(c, theta, phi, rng, int(ss.char_px))
            copies = [M.render(c, M.jitter(theta, rng), phi, rng, int(ss.char_px)) for _ in range(4)]
            ss.store[c] = [base] + copies
            ss.synth.add(c)
        lacking = [c for c in missing if not M.covers(c)]
        if lacking:
            ss.morph["fallback"] = list(dict.fromkeys([*ss.morph.get("fallback", []), *lacking]))
        G.save_store(ss.store, GDIR)
        st.rerun()
    cols = st.columns(10)
    for i, ch in enumerate(sorted(ss.store)):
        with cols[i % 10]:
            tag = " (synth)" if ch in ss.synth else ""
            st.image(ss.store[ch][0], caption=f"{ch}{tag} ×{len(ss.store[ch])}", width=70,
                     alt=f"Stored glyph {ch}")
    c1, c2 = st.columns(2)
    if ss.synth and c1.button("Delete generated glyphs"):
        for c in list(ss.synth):
            ss.store.pop(c, None)
        ss.synth = set()
        G.save_store(ss.store, GDIR)
        st.rerun()
    if ss.store and c2.button("Delete all glyphs"):
        ss.store = {}; ss.synth = set(); ss.morph = None
        G.save_store({}, GDIR)
        st.rerun()

# ------------------------------------------------------------------ 5
elif step == STEPS[4]:
    st.header("Generate synthetic training images")
    up = st.file_uploader("Text file, one string per line", type=["txt", "csv"])
    raw = up.read().decode("utf-8") if up else st.text_area("…or paste strings here", "Warszawska\nMarszałkowska\nKrakowska")
    words = [w.strip() for w in raw.splitlines() if w.strip()]
    n = st.slider("Images per string", 10, 100, 30)
    bad = sorted({c for w in words for c in w if c != " " and c not in ss.store})
    if bad: st.warning(f"Alphabet is missing: {''.join(bad)} (step 4)")
    if st.button("Generate", type="primary", disabled=bool(bad) or not words):
        DDIR.mkdir(parents=True, exist_ok=True)
        rng = np.random.default_rng(42); ss.dataset = []; rows = []
        bar = st.progress(0.0)
        for wi, w in enumerate(words):
            for j in range(n):
                img = G.compose(w, ss.store, rng); fn = f"{wi:04d}_{j:03d}.png"
                cv2.imwrite(str(DDIR / fn), img); ss.dataset.append((img, w)); rows.append((fn, w))
            bar.progress((wi + 1) / len(words))
        pd.DataFrame(rows, columns=["file", "text"]).to_csv(DDIR / "labels.tsv", sep="\t", index=False)
        st.success(f"{len(ss.dataset)} images saved to {DDIR}/")
    if ss.dataset:
        for i, idx in enumerate(np.random.default_rng(0).choice(len(ss.dataset), min(12, len(ss.dataset)), replace=False)):
            st.image(ss.dataset[idx][0], caption=ss.dataset[idx][1], width=220)

# ------------------------------------------------------------------ 6
else:
    st.header("Train a degradation-robust OCR model")
    if not ss.dataset and (DDIR / "labels.tsv").exists():
        df = pd.read_csv(DDIR / "labels.tsv", sep="\t", dtype=str)
        ss.dataset = [(O.to_gray(cv2.imread(str(DDIR / r.file), cv2.IMREAD_UNCHANGED)), r.text) for r in df.itertuples()]
    if not ss.dataset: st.info("Generate a dataset first."); st.stop()
    st.write(f"{len(ss.dataset)} images, {len({t for _, t in ss.dataset})} distinct strings. Device: `{O.DEV}`")
    c1, c2, c3 = st.columns(3)
    epochs = c1.number_input("Epochs", 1, 200, 30); bs = c2.number_input("Batch size", 4, 256, 32)
    lr = c3.number_input("Learning rate", 1e-5, 1e-1, 1e-3, format="%.5f")
    if ss.model is None and (WORK / "ocr.pt").exists():
        try:
            ss.model = O.load_model(WORK / "ocr.pt")
        except Exception as e:
            st.warning(f"Could not load work/ocr.pt: {e}")
    ckpt_path, weights_path = WORK / "ocr_ckpt.pt", WORK / "ocr.pt"
    ckpt = None
    if ckpt_path.exists():
        try:
            ckpt = O.peek_checkpoint(ckpt_path)
        except Exception as e:
            st.warning(f"Could not read work/ocr_ckpt.pt: {e}")
    resumable = O.can_resume(ckpt, ss.dataset)
    done = int(ckpt["epoch"]) + 1 if resumable else 0
    if resumable and done < int(epochs):
        st.caption(
            f"Last run finished epoch {done} of {ckpt['epochs']}. "
            f"Continue last run trains from epoch {done + 1} through {int(epochs)}, "
            "with the same weights and the batch size and learning rate above."
        )
    elif resumable:
        st.caption(f"Last run finished epoch {done} of {ckpt['epochs']}. Raise Epochs above {done} to keep going from that checkpoint.")
    elif ckpt:
        st.caption("A checkpoint is on disk, but it belongs to a different dataset, so it cannot be continued.")
    else:
        st.caption("Train saves a checkpoint after every finished epoch.")
    b1, b2 = st.columns(2)
    start = b1.button("Train", type="primary")
    cont = b2.button("Continue last run", disabled=not (resumable and done < int(epochs)))

    def _fit(resume):
        bar, status, hist = st.progress(0.0), st.empty(), []
        chart = st.empty()
        def cb(ep, tot, loss, acc):
            bar.progress((ep + 1) / tot); hist.append(loss)
            status.write(f"epoch {ep + 1}/{tot} · loss {loss:.3f}" + (f" · held-out string acc (degraded) {acc:.0%}" if acc is not None else ""))
            chart.line_chart(hist)
        try:
            ss.model = O.train(
                ss.dataset, int(epochs), int(bs), float(lr), cb,
                ckpt_path=ckpt_path, weights_path=weights_path, resume=resume,
            )
        except Exception as e:
            if weights_path.exists():
                try:
                    ss.model = O.load_model(weights_path)
                except Exception:
                    pass
            st.error(f"Training stopped: {e}")
            st.info("Each finished epoch is already in work/ocr_ckpt.pt. Continue last run picks up from the last one.")
            return
        st.success(f"Trained through epoch {int(epochs)}. Saved work/ocr.pt and work/ocr_ckpt.pt.")

    if start:
        _fit(None)
    elif cont:
        _fit(O.load_checkpoint(ckpt_path))
    if ss.model:
        st.subheader("Try it")
        up = st.file_uploader("Upload an image of a word (ideally a bad scan)", type=["png", "jpg", "jpeg"], key="test")
        if up:
            g = O.to_gray(Image.open(up))
            st.image(g, width=300, alt="Uploaded word")
            st.metric("Prediction", O.predict(*ss.model, g))
            if st.button("Save model inputs"):
                up_t, clean_t = O.save_model_inputs(g, ss.dataset[0][0], WORK / "debug")
                st.caption(f"Wrote work/debug/poniatowskiego.npy and the training pair beside it.")
                st.write(
                    f"Upload tensor min {up_t.min():.3f}, max {up_t.max():.3f}, mean {up_t.mean():.3f}. "
                    f"Clean training tensor min {clean_t.min():.3f}, max {clean_t.max():.3f}, mean {clean_t.mean():.3f}."
                )
        if st.button("Degrade a random training image and read it"):
            img, txt = ss.dataset[np.random.randint(len(ss.dataset))]
            d = O.degrade(img, np.random.default_rng())
            st.image(d, width=300, alt="Degraded training image")
            st.write(f"truth: **{txt}** → predicted: **{O.predict(*ss.model, d)}**")
