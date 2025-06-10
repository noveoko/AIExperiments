# PDF Semantic Search with Ollama
#
# This script creates a local semantic search engine for your PDF files.
#
# Functionality:
# 1. Scans a directory for all .pdf files.
# 2. For each PDF, extracts the text.
# 3. Chunks the text into paragraphs.
# 4. Uses a local Ollama model to generate an embedding for each chunk.
# 5. Saves the file path, chunk, and its embedding into an index file.
# 6. Provides a search function to find the most relevant PDFs based on a query.
#
# Author: Gemini
# Date: June 10, 2025

import os
import fitz  # PyMuPDF
import json
import requests
import numpy as np
from tqdm import tqdm
import platform
import argparse
import sys # Added to handle potential encoding errors

# --- CONFIGURATION ---

# 1. Set the root directory to scan for PDFs.
#    For Windows, it might be 'C:\\Users\\YourUser\\Documents'
#    For macOS, it might be '/Users/YourUser/Documents'
#    For Linux, it might be '/home/YourUser/Documents'
#    WARNING: Scanning your entire root directory ('/' or 'C:\\') can take a very long time!
#    It's recommended to start with a more specific folder.
DEFAULT_SEARCH_DIR = os.path.expanduser("~") # Starts from the user's home directory by default

# 2. Ollama API configuration
OLLAMA_ENDPOINT = "http://localhost:11434/api/embeddings"
OLLAMA_MODEL = "mxbai-embed-large" # An excellent default embedding model.
                                  # Make sure you have pulled this model: `ollama pull mxbai-embed-large`

# 3. Index file path
#    This file will store your searchable data.
INDEX_FILE = "pdf_search_index.json"


def check_ollama_status():
    """Checks if the Ollama server is running and the model is available."""
    try:
        response = requests.get("http://localhost:11434")
        response.raise_for_status()
    except requests.exceptions.RequestException:
        print("\n[ERROR] Ollama server not found at http://localhost:11434.")
        print("Please make sure Ollama is installed and running.")
        return False

    try:
        response = requests.post("http://localhost:11434/api/show", json={"name": OLLAMA_MODEL})
        if response.status_code == 404:
            print(f"\n[ERROR] Ollama model '{OLLAMA_MODEL}' not found.")
            print(f"Please pull the model by running: ollama pull {OLLAMA_MODEL}")
            return False
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"\n[ERROR] Could not verify Ollama model: {e}")
        return False
        
    print(f"[INFO] Ollama server is running and model '{OLLAMA_MODEL}' is available.")
    return True


def find_pdf_files(root_dir):
    """Recursively finds all PDF files in a given directory."""
    pdf_files = []
    print(f"\n[INFO] Starting PDF scan in: {root_dir}")
    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_files.append(os.path.join(root, file))
    print(f"[INFO] Found {len(pdf_files)} PDF files.")
    return pdf_files


def extract_text_from_pdf(pdf_path):
    """Extracts all text from a single PDF file."""
    try:
        with fitz.open(pdf_path) as doc:
            text = "".join(page.get_text() for page in doc)
            return text
    except Exception as e:
        print(f"[WARNING] Could not read PDF {os.path.basename(pdf_path)}: {e}")
        return None


def chunk_text(text, min_chunk_size=50):
    """Splits text into paragraphs or meaningful chunks."""
    # Split by double newlines, which often separate paragraphs
    chunks = text.split('\n\n')
    # Filter out very small chunks and strip whitespace
    return [chunk.strip() for chunk in chunks if len(chunk.strip()) >= min_chunk_size]


def get_embedding(text_chunk):
    """Generates an embedding for a text chunk using the Ollama API."""
    try:
        response = requests.post(
            OLLAMA_ENDPOINT,
            json={"model": OLLAMA_MODEL, "prompt": text_chunk}
        )
        response.raise_for_status()
        return response.json()["embedding"]
    except requests.exceptions.RequestException as e:
        print(f"\n[ERROR] Failed to get embedding from Ollama: {e}")
        return None
    except KeyError:
        print(f"\n[ERROR] Unexpected response from Ollama: {response.text}")
        return None


def build_index(root_dir):
    """Scans for PDFs, extracts text, chunks, embeds, and saves the index."""
    if not check_ollama_status():
        return

    pdf_files = find_pdf_files(root_dir)
    index_data = []

    with tqdm(total=len(pdf_files), desc="[Indexing PDFs]") as pbar_files:
        for pdf_path in pdf_files:
            pbar_files.set_postfix_str(os.path.basename(pdf_path), refresh=True)
            text = extract_text_from_pdf(pdf_path)

            if not text:
                pbar_files.update(1)
                continue

            chunks = chunk_text(text)
            for chunk in chunks:
                embedding = get_embedding(chunk)
                if embedding:
                    index_data.append({
                        "file_path": pdf_path,
                        "chunk": chunk,
                        "embedding": embedding
                    })
            pbar_files.update(1)

    print(f"\n[INFO] Saving index with {len(index_data)} chunks to {INDEX_FILE}...")
    with open(INDEX_FILE, "w", encoding='utf-8') as f:
        json.dump(index_data, f)
    print("[INFO] Indexing complete!")


def cosine_similarity(v1, v2):
    """Calculates cosine similarity between two vectors."""
    vec1 = np.array(v1)
    vec2 = np.array(v2)
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))


def search(query, top_n=5):
    """Searches the index for the most relevant documents."""
    if not os.path.exists(INDEX_FILE):
        print(f"[ERROR] Index file '{INDEX_FILE}' not found.")
        print("Please run the script with the '--index' flag first.")
        return

    if not check_ollama_status():
        return

    print(f"\n[INFO] Generating embedding for your query: '{query}'...")
    query_embedding = get_embedding(query)

    if not query_embedding:
        print("[ERROR] Could not generate query embedding. Aborting search.")
        return

    print("[INFO] Loading index and performing search...")
    with open(INDEX_FILE, "r", encoding='utf-8') as f:
        index_data = json.load(f)

    results = []
    for item in tqdm(index_data, desc="[Searching]"):
        similarity = cosine_similarity(query_embedding, item["embedding"])
        results.append({
            "similarity": similarity,
            "file_path": item["file_path"],
            "chunk": item["chunk"]
        })

    # Sort results by similarity
    results.sort(key=lambda x: x["similarity"], reverse=True)

    # Deduplicate results by file_path, keeping only the highest-scoring chunk for each file
    final_results = []
    seen_paths = set()
    for res in results:
        if res["file_path"] not in seen_paths:
            final_results.append(res)
            seen_paths.add(res["file_path"])
        if len(final_results) >= top_n:
            break

    print(f"\n--- Top {len(final_results)} Search Results ---")
    if not final_results:
        print("No relevant documents found.")
    else:
        for i, res in enumerate(final_results):
            # To prevent UnicodeEncodeError on some terminals, we get the console's encoding
            # and replace any characters that can't be displayed.
            output_encoding = sys.stdout.encoding or 'utf-8'
            printable_chunk = res['chunk'].encode(output_encoding, errors='replace').decode(output_encoding)
            
            print(f"\n{i+1}. File: {res['file_path']}")
            print(f"   Similarity: {res['similarity']:.4f}")
            print(f"   Relevant Context: \"...{printable_chunk}...\"")
    print("\n------------------------------")


def main():
    """Main function to handle command-line arguments."""
    parser = argparse.ArgumentParser(
        description="A local semantic search engine for your PDFs powered by Ollama.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--index",
        action="store_true",
        help="Build or rebuild the search index from your PDFs."
    )
    parser.add_argument(
        "--search",
        type=str,
        metavar='"QUERY"',
        help="Perform a semantic search using the specified query."
    )
    parser.add_argument(
        "--dir",
        type=str,
        metavar='PATH',
        default=DEFAULT_SEARCH_DIR,
        help=f"The directory to scan for PDFs. Defaults to your home directory:\n({DEFAULT_SEARCH_DIR})"
    )
    
    args = parser.parse_args()

    if args.index:
        print("[ACTION] Indexing mode selected.")
        # Ask for confirmation as this can be a long process
        confirm = input(f"This will scan for PDFs in '{args.dir}' and create an index. This may take a while. Continue? (y/n): ")
        if confirm.lower() == 'y':
            build_index(args.dir)
        else:
            print("Indexing cancelled.")
    
    elif args.search:
        print("[ACTION] Search mode selected.")
        search(args.search)
        
    else:
        print("No action specified. Use '--index' to build the database or '--search \"your query\"' to search.")
        print("Use '--help' for more information.")

if __name__ == "__main__":
    main()
