# Custom OCR

Streamlit studio that crops a word, splits the characters, learns one stroke style, and trains a CRNN on synthetic words.

## Run

From this directory:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

On Windows, activate with `.venv\Scripts\activate`.

With uv:

```bash
uv sync
uv run streamlit run app.py
```

Open the local URL Streamlit prints. Training uses the GPU when PyTorch can see CUDA. On an NVIDIA machine where `torch.cuda.is_available()` is false, install a CUDA build of PyTorch from https://pytorch.org/get-started/locally/ and start the app again.

Saved character crops are in `work/glyphs`. Step 6 continues the last finished epoch from `work/ocr_ckpt.pt` when that file is present and the dataset matches.
