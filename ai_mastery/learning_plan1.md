# 📚 Information Science for AI — Learning Plan
### Based on: *"Information Theory for Language Models: Jack Morris"*
### Podcast: Latent Space — The AI Engineer Podcast (July 2, 2025)
### Guest: Jack Morris, PhD @ Cornell Tech (advised by Sasha Rush)

> Jack Morris is known for doing "underrated research" at the intersection of information theory, LLMs,
> and embeddings — and for being unusually good at explaining it clearly. This plan follows the
> structure of his research arc, from embeddings → inversion → contextual geometry → memorization → a
> new kind of information theory.

---

## 🗺️ The 5-Chapter Arc (following the episode)

```
Chapter 1: What Are Embeddings?
     ↓
Chapter 2: Inversion — How Much Do Embeddings Reveal?
     ↓
Chapter 3: Universal Geometry — Do All Embeddings Live in the Same Space?
     ↓
Chapter 4: Contextual Document Embeddings — Making Embeddings Smarter
     ↓
Chapter 5: A New Information Theory — How Much Does a Model Memorize?
```

---

## Chapter 1 — What Are Embeddings?

### The Core Idea

An **embedding** is a function $f: \text{text} \rightarrow \mathbb{R}^d$ that maps variable-length text
to a fixed-size vector, where semantic similarity corresponds to geometric proximity.

**Cosine similarity** is the standard distance for comparing embeddings:

$$\text{sim}(A, B) = \frac{A \cdot B}{\|A\| \|B\|} \in [-1, 1]$$

Two vectors pointing in the same direction score +1. Orthogonal vectors score 0. Opposite vectors score -1.

**Why $d$ matters:** Most modern embedding models use $d = 768$ or $d = 1536$ dimensions. Each dimension
is a learnable "axis of meaning" discovered during training on hundreds of millions of sentence pairs.

### 📄 Reading

- **Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks (2019)**
  - https://arxiv.org/abs/1908.10084
  - The foundational paper that made BERT-based sentence embeddings practical

- **MTEB: Massive Text Embedding Benchmark (2023)**
  - https://arxiv.org/abs/2210.07316
  - The standard leaderboard for comparing embedding models: https://huggingface.co/spaces/mteb/leaderboard

- **Nomic Embed: Training a Reproducible Long Context Text Embedder**
  - (Jack Morris's co-authored open-source embedding model — Zach Nussbaum et al.)
  - https://arxiv.org/abs/2402.01613
  - Model: https://huggingface.co/nomic-ai/nomic-embed-text-v1

- **cde-small-v2 (Jack Morris's SOTA BERT-scale model, 2025)**
  - https://huggingface.co/jxm/cde-small-v2
  - 140M parameters, #1 on MTEB at that scale

### 🐍 Python Exercise 1 — Build intuition for embedding geometry

```python
# pip install sentence-transformers numpy matplotlib scikit-learn
from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer("all-MiniLM-L6-v2")  # fast 384-dim model

# These sentence groups should cluster together
sentences = [
    # Group A: Information theory
    "Shannon entropy measures the uncertainty in a probability distribution",
    "Cross-entropy is the loss function used to train classifiers",
    "KL divergence quantifies how one distribution differs from another",
    # Group B: Embeddings
    "Text embeddings map sentences to high-dimensional vectors",
    "Cosine similarity measures the angle between embedding vectors",
    "Semantic search uses embeddings to find related documents",
    # Group C: Unrelated
    "The stock market rose sharply yesterday",
    "She baked a chocolate cake for the party",
]

embeddings = model.encode(sentences, normalize_embeddings=True)

# Compute full similarity matrix
sim_matrix = embeddings @ embeddings.T  # cosine sim since normalized

print("Similarity Matrix (rounded):")
print(np.round(sim_matrix, 2))

# Key insight: sentences 0-2 should score ~0.6-0.8 with each other
# and ~0.1-0.3 with sentences 6-7
print("\nIntra-group (A[0] vs A[1]):", round(sim_matrix[0, 1], 3))
print("Cross-group (A[0] vs C[6]):", round(sim_matrix[0, 6], 3))
```

---

## Chapter 2 — Inversion: How Much Do Embeddings Reveal?

### The Startling Finding

Jack Morris's 2023 EMNLP **outstanding paper** showed something alarming:
**you can recover text almost exactly from its embedding** — without access to the original model weights.

This has serious privacy implications. Embeddings stored in a vector database are *not* a safe
anonymisation of text.

### How Vec2Text Works (step by step)

1. Start with a random hypothesis text $\hat{x}_0$
2. Embed it: $\hat{e}_0 = f(\hat{x}_0)$
3. Compute the error in embedding space: $\delta = e_{\text{target}} - \hat{e}_0$
4. Train a **corrector model** (T5-based) that takes $(\hat{x}_t, \delta_t)$ and outputs a refined text $\hat{x}_{t+1}$
5. Iterate until $f(\hat{x}_T) \approx e_{\text{target}}$

The objective at each step is to minimise:

$$\mathcal{L} = \|f(\hat{x}_{t+1}) - e_{\text{target}}\|_2^2$$

### The Follow-up: Inverting LLM *Outputs* (Not Just Embeddings)

The follow-on paper **Language Model Inversion (ICLR 2024)** showed you can reconstruct a *prompt*
given only the LLM's output probability distribution. No embedding needed — just the next-token logits.

Key trick: to get a full probability distribution from an API that only returns top-K tokens,
the paper exploits the `logit_bias` parameter to iteratively expose all token probabilities.

### 📄 Papers

1. **Vec2Text — Text Embeddings Reveal (Almost) As Much As Text (EMNLP 2023, Outstanding Paper)**
   - https://arxiv.org/abs/2310.06816
   - Code: https://github.com/jxmorris12/vec2text

2. **Language Model Inversion (ICLR 2024)**
   - https://arxiv.org/abs/2311.13647
   - Shows prompts can be recovered from LLM output distributions alone

3. **Extracting Prompts by Inverting LLM Outputs (2024)**
   - https://arxiv.org/abs/2405.15012
   - System prompt extraction using only 15 Q&A pairs — no token probs required

### 🐍 Python Exercise 2 — Try Vec2Text yourself

```python
# pip install vec2text torch transformers
# Note: requires ~4GB VRAM or will run slowly on CPU
import vec2text
import torch
from transformers import AutoModel, AutoTokenizer

# Load the inversion corrector (trained against text-embedding-ada-002)
corrector = vec2text.load_pretrained_corrector("text-embedding-ada-002")

# Target text to invert (in practice this would be an anonymous embedding)
target_text = "Jack Morris works on information theory and text embeddings"

# To run a full demo, you need OpenAI embeddings API access.
# Here is the conceptual loop showing what vec2text does:
def conceptual_inversion_loop(target_embedding, n_steps=20):
    """
    Vec2Text iterative correction loop (pseudocode).
    In practice, use vec2text.invert_embeddings().
    """
    # Step 1: initialise with a random starting hypothesis
    hypothesis = "random starting text"
    
    for step in range(n_steps):
        # Step 2: embed current hypothesis
        h_embedding = embed(hypothesis)  # e.g. OpenAI ada-002
        
        # Step 3: compute residual in embedding space
        residual = target_embedding - h_embedding
        
        # Step 4: corrector model proposes an updated hypothesis
        hypothesis = corrector(hypothesis, residual)
        
        # Step 5: measure how close we are
        distance = np.linalg.norm(embed(hypothesis) - target_embedding)
        print(f"Step {step}: embedding distance = {distance:.4f}")
    
    return hypothesis

# For a real demo, see: https://github.com/jxmorris12/vec2text
print("Vec2Text repo: https://github.com/jxmorris12/vec2text")
print("Key insight: embeddings are NOT a privacy-safe representation.")
print("If you store raw ada-002 embeddings, the text can be reconstructed.")
```

### ⚠️ Privacy Implications for Engineers

If you're building a RAG system or vector database:
- **Don't** treat embeddings as anonymised representations of sensitive text
- Consider using **differential privacy** or **embedding perturbation** for PII
- For deidentification, see Jack's earlier paper: *Unsupervised Text Deidentification* (EMNLP 2022)
  - https://arxiv.org/abs/2210.11528

---

## Chapter 3 — Universal Geometry of Embeddings

### The Question

Different embedding models (OpenAI, Cohere, Nomic, BGE, etc.) all map text into vectors.
Do they all learn the *same* structure? Or fundamentally different representations?

### The Finding (NeurIPS 2025)

The paper **Harnessing the Universal Geometry of Embeddings** shows:

**Embeddings from different models are linearly mappable onto each other — without paired data.**

This means there exists an approximately universal latent geometry of language that all embedding
models discover. The mapping $M: \mathbb{R}^{d_1} \rightarrow \mathbb{R}^{d_2}$ can be found with:

$$\min_{M} \mathbb{E}_{x} \left[ \| M \cdot f_1(x) - f_2(x) \|_2^2 \right]$$

...using only *unpaired* embeddings from each model — similar in spirit to CycleGAN (mentioned in the
episode: https://junyanz.github.io/CycleGAN/).

### Why This Matters for AI Engineers

1. **Model portability**: you can migrate your vector DB from one embedding model to another
   *without* re-embedding all your data
2. **Privacy**: if embeddings share a universal geometry, inversion attacks may generalise across models
3. **Theory**: suggests language models are all discovering the same underlying structure of language

### 📄 Papers

1. **Harnessing the Universal Geometry of Embeddings (NeurIPS 2025)**
   - https://arxiv.org/abs/2505.12540

2. **CycleGAN (the inspiration for unpaired mapping)**
   - https://arxiv.org/abs/1703.10593
   - Demo: https://junyanz.github.io/CycleGAN/

3. **Platonic Representation Hypothesis (2024)** — closely related
   - https://arxiv.org/abs/2405.07987
   - Argues that larger models converge to the same representations across modalities

### 🐍 Python Exercise 3 — Measure cross-model embedding alignment

```python
# pip install sentence-transformers numpy scipy
from sentence_transformers import SentenceTransformer
import numpy as np
from scipy.spatial.distance import cosine

# Two completely different embedding models
model_a = SentenceTransformer("all-MiniLM-L6-v2")      # 384-dim
model_b = SentenceTransformer("all-mpnet-base-v2")      # 768-dim

sentences = [
    "Information theory and entropy",
    "Text embeddings and vector spaces",
    "Language model inversion attacks",
    "Contextual document embeddings",
    "Universal geometry of representations",
]

# Step 1: embed with both models
embs_a = model_a.encode(sentences, normalize_embeddings=True)  # (5, 384)
embs_b = model_b.encode(sentences, normalize_embeddings=True)  # (5, 768)

# Step 2: compute pairwise similarity within each model
def sim_matrix(embs):
    return embs @ embs.T

sim_a = sim_matrix(embs_a)
sim_b = sim_matrix(embs_b)

# Step 3: do the two models agree on which sentences are similar?
# Flatten upper triangle and correlate
from scipy.stats import pearsonr
idx = np.triu_indices(len(sentences), k=1)
corr, p = pearsonr(sim_a[idx], sim_b[idx])
print(f"Cross-model rank correlation: r = {corr:.3f} (p = {p:.4f})")
# High correlation = models agree on similarity structure
# This is evidence for the Universal Geometry Hypothesis

# Step 4: find a linear mapping from model_a space to model_b space
# Using least squares (requires paired data — shows the easy case)
# For the *unpaired* case, see the actual paper
from numpy.linalg import lstsq
M, _, _, _ = lstsq(embs_a, embs_b, rcond=None)  # (384, 768)
embs_a_projected = embs_a @ M                    # projected into model_b space

# How well does the projection preserve similarity structure?
sim_projected = sim_matrix(embs_a_projected / np.linalg.norm(embs_a_projected, axis=1, keepdims=True))
corr_after, _ = pearsonr(sim_projected[idx], sim_b[idx])
print(f"After linear projection: r = {corr_after:.3f}")
```

---

## Chapter 4 — Contextual Document Embeddings (CDE)

### The Problem with Standard Embeddings

Standard embedding models embed each document *in isolation*. But the meaning of a document is
partly relative to its corpus. "Python" means something different in a biology paper collection
vs. a software engineering corpus.

### The CDE Solution (ICLR 2025)

**Contextual Document Embeddings** add a two-stage process:

**Stage 1** — Encode a batch of "context documents" from the corpus:
$$c = \text{ContextEncoder}(d_1, d_2, ..., d_k)$$

**Stage 2** — Encode each target document *conditioned on* the corpus context:
$$e(d) = \text{DocEncoder}(d \mid c)$$

The key innovation is **contextual batching** during training: instead of random document
pairs, you batch documents that are topically similar together, so the model learns to
discriminate within a topic, not just across topics.

Result: **cde-small-v2** (140M params) achieves SOTA on MTEB, beating models 10x its size.

### 📄 Papers

1. **Contextual Document Embeddings (ICLR 2025)**
   - https://arxiv.org/abs/2410.02525
   - Code: https://github.com/jxmorris12/cde

2. **cde-small-v2 — SOTA 140M embedding model**
   - https://huggingface.co/jxm/cde-small-v2

3. **Do Language Models Plan Ahead? (COLM 2024)**
   - https://arxiv.org/abs/2404.00859
   - Related: whether models "cache" future-useful info in hidden states (myopic training)

### 🐍 Python Exercise 4 — Use CDE for context-aware retrieval

```python
# pip install sentence-transformers torch
from sentence_transformers import SentenceTransformer
import torch
import numpy as np

# Load CDE model
model = SentenceTransformer("jxm/cde-small-v2", trust_remote_code=True)

# Simulate two different corpora — same query, different context
# Corpus A: Machine learning papers
corpus_ml = [
    "Stochastic gradient descent optimizes neural network weights",
    "Attention mechanisms allow transformers to focus on relevant tokens",
    "Python libraries like PyTorch enable efficient tensor computation",
    "Backpropagation computes gradients through a computational graph",
]

# Corpus B: Biology papers
corpus_bio = [
    "Python snakes are found in tropical regions of Africa and Asia",
    "Anacondas are the largest snakes by weight in the world",
    "Reptiles regulate their body temperature through external heat sources",
    "The venom of some pythons contains digestive enzymes",
]

query = "Python computational efficiency"

def embed_with_context(model, corpus, query):
    """CDE-style contextual embedding: encode docs with corpus context."""
    # Stage 1: get a corpus summary embedding (mean of corpus)
    corpus_embs = model.encode(corpus, normalize_embeddings=True)
    context = corpus_embs.mean(axis=0, keepdims=True)  # simplified context

    # Stage 2: encode query (in real CDE, context is passed to model directly)
    query_emb = model.encode([query], normalize_embeddings=True)
    
    # Score query against each doc
    scores = corpus_embs @ query_emb.T
    return scores.flatten()

scores_ml  = embed_with_context(model, corpus_ml, query)
scores_bio = embed_with_context(model, corpus_bio, query)

print("In ML corpus:")
for doc, score in sorted(zip(corpus_ml, scores_ml), key=lambda x: -x[1]):
    print(f"  [{score:.3f}] {doc[:60]}...")

print("\nIn Biology corpus:")
for doc, score in sorted(zip(corpus_bio, scores_bio), key=lambda x: -x[1]):
    print(f"  [{score:.3f}] {doc[:60]}...")
```

---

## Chapter 5 — A New Type of Information Theory

### The Central Question Jack Is Working On

> *"Where is information stored in a language model? What even IS information in the context of modern AI?"*
>
> — Jack Morris, jxmo.io

Classical Shannon information theory measures information content in **data** (bits per symbol).
Jack's research extends this to measure information stored in **model parameters**.

### Key Result: How Much Do Models Memorize? (2025)

The paper **"How Much Do Language Models Memorize?"** proposes a new formal definition of
memorization grounded in information theory.

**Definition**: A model $\theta$ memorizes training example $x$ if:

$$I(\theta; x) > \epsilon$$

where $I(\theta; x)$ is the mutual information between the model weights and the training example —
how much knowing $\theta$ tells you about $x$.

**Empirical finding**: GPT-2-scale models memorize approximately **3.6–3.9 bits per parameter**
(in 32-bit precision).

This gives a new way to measure **model capacity**:

$$\text{Capacity}(\theta) = \sum_{x \in \mathcal{D}} I(\theta; x) \approx 3.7 \times |\theta|_{32\text{-bit}}$$

### Why This Matters

- Explains why scaling laws work: more parameters = more bits of memorization capacity
- Gives a theoretical upper bound on what a model can know
- Connects to privacy: memorized examples can be extracted via membership inference

### The "New Information Theory" Thread

Jack posted a thread (April 2025) proposing that classical Shannon entropy is insufficient for
modern AI because it measures *signal complexity* — not *learnability*.

His proposed reframe: information in AI should measure **"how much of this signal can be
compressed by gradient descent?"** — which is different from Shannon entropy.

This connects to research on the **Information Bottleneck** principle in deep learning:

$$\min_{Z} I(X; Z) - \beta I(Z; Y)$$

...where $Z$ is a learned representation that compresses input $X$ while retaining task-relevant
information $Y$.

### 📄 Papers & Threads

1. **How Much Do Language Models Memorize? (arXiv 2025)**
   - https://arxiv.org/abs/2505.24832
   - Tweet thread: https://x.com/jxmnop/status/1929903028372459909

2. **A New Type of Information Theory (tweet thread, April 2025)**
   - https://x.com/jxmnop/status/1904238408899101014

3. **Approximating Language Model Training Data from Weights (2025)**
   - https://arxiv.org/abs/2506.15553
   - Inverting the weights themselves to recover training data

4. **The Information Bottleneck Method (Tishby et al., 2000)**
   - https://arxiv.org/abs/physics/0004057
   - The foundational theory connecting compression and representation learning

5. **Opening the Black Box of Deep Neural Networks via Information (Tishby & Schwartz-Ziv, 2017)**
   - https://arxiv.org/abs/1703.00810
   - Applies the information bottleneck to explain why deep networks generalise

6. **Blog: "There Are No New Ideas In AI, Only New Datasets" — Jack Morris**
   - https://blog.jxmo.io/p/there-are-no-new-ideas-in-ai-only
   - A counterintuitive essay: summarises LLM history as 4 data breakthroughs, not algorithm breakthroughs

### 🐍 Python Exercise 5 — Measure memorization via membership inference

```python
# A simplified demonstration of the *concept* behind memorization measurement
# Full vec2text-style inversion requires GPU + OpenAI API key
# This demo shows the perplexity-gap approach (simpler proxy)
from transformers import GPT2LMHeadModel, GPT2TokenizerFast
import torch
import numpy as np

model_name = "gpt2"
tokenizer = GPT2TokenizerFast.from_pretrained(model_name)
model = GPT2LMHeadModel.from_pretrained(model_name)
model.eval()

def perplexity(text: str) -> float:
    """
    Perplexity = exp(cross-entropy loss per token).
    Low perplexity = model assigns high probability to this text.
    Low perplexity is a signal that the model may have memorized the text.
    """
    tokens = tokenizer(text, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**tokens, labels=tokens["input_ids"])
    return float(torch.exp(outputs.loss))

# Well-known text (likely in GPT-2 training data)
known = "The quick brown fox jumps over the lazy dog"

# Random nonsense (not in training data)
unknown = "xlq mwp grtr vxz jqk fpl bbn ywt zzz aaa"

# Novel meaningful sentence (probably not memorized verbatim)
novel = "Jack Morris invented a new definition of LLM memorization in 2025"

print(f"Perplexity of known text:   {perplexity(known):.1f}")
print(f"Perplexity of novel text:   {perplexity(novel):.1f}")
print(f"Perplexity of gibberish:    {perplexity(unknown):.1f}")
print()
print("Key: lower perplexity = model has more 'knowledge' of this text")
print("Memorization detection uses this gap to identify training examples.")
print(