import streamlit as st
import spacy
import skweak
import requests
import json
from skweak import heuristics, aggregation

# --- INITIALIZATION ---
nlp = spacy.load("en_core_web_sm")

if 'docs' not in st.session_state:
    raw_texts = [
        "Elon Musk visited the factory.",
        "The CEO of Apple, Tim Cook, spoke today.",
        "Microsoft Corp announced new features.", # False positive test
        "Jensen Huang is leading NVIDIA.",
        "Yesterday, Monday Morning was very cold." # False positive test
    ]
    st.session_state.docs = [nlp(t) for t in raw_texts]
    st.session_state.verified_names = set()

# --- LABELING FUNCTIONS ---

def ollama_verify(name, context):
    """The LLM acts as a 'High-Reasoning' Labeling Function."""
    try:
        res = requests.post("http://localhost:11434/api/generate", 
            json={
                "model": "llama3",
                "prompt": f"In context: '{context}', is '{name}' a person? Answer JSON: {{'is_person': bool}}",
                "format": "json", "stream": False
            }, timeout=5)
        return json.loads(res.json()['response']).get('is_person', False)
    except: return False

def heuristic_lf(doc):
    """Fast, weak signal: Title Case words."""
    for ent in doc.noun_chunks:
        if ent.text[0].isupper():
            yield ent.start, ent.end, "PERSON"

# --- STREAMLIT UI ---
st.title("🧬 skweak + Ollama Bootstrapper")

# 1. Human in the Loop (Manual Check for specific 'hard' cases)
st.subheader("1. Human Audit (Gold Labels)")
for i, doc in enumerate(st.session_state.docs):
    if doc.text not in st.session_state.verified_names:
        col1, col2 = st.columns([3, 1])
        col1.write(f"**Sentence:** {doc.text}")
        if col2.button("Verify Person", key=f"btn_{i}"):
            # We treat human input as a special "gold" layer
            st.session_state.verified_names.add(doc.text)
            st.rerun()

# 2. Run skweak Aggregation
if st.button("🔄 Run skweak Aggregation"):
    # Apply heuristics
    lf1 = heuristics.FunctionAnnotator("heuristic", heuristic_lf)
    docs = list(lf1.pipe(st.session_state.docs))
    
    # Apply Ollama as a second LF (only on non-verified to save time)
    def ollama_lf(doc):
        for start, end, label in heuristic_lf(doc):
            if ollama_verify(doc[start:end].text, doc.text):
                yield start, end, "PERSON"
    
    lf2 = heuristics.FunctionAnnotator("ollama", ollama_lf)
    docs = list(lf2.pipe(docs))
    
    # AGGREGATION: The HMM learns which LF is best
    hmm = aggregation.HMM("hmm", ["PERSON"])
    # We tell the HMM that Ollama is generally more trustworthy than the heuristic
    docs = hmm.fit_and_aggregate(docs)
    
    st.session_state.docs = docs
    st.success("Model evolved! Check the extracted entities below.")

# 3. Display Results
st.subheader("2. Final Model Predictions")
for doc in st.session_state.docs:
    ents = doc.spans.get("hmm", [])
    st.write(f"Text: {doc.text}")
    st.write(f"Entities: {[(e.text, e.label_) for e in ents]}")
    st.divider()
