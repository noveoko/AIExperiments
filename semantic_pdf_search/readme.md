Local PDF Semantic Search with Ollama
This project provides a Python script that scans a directory for PDF files, extracts their text content, and uses a local Ollama instance to create semantic embeddings. It builds a searchable index, allowing you to perform natural language queries to find the most relevant PDF documents on your computer.

Features
Recursive PDF Scanning: Automatically finds all .pdf files within a specified directory and its subdirectories.

Text Extraction: Uses the PyMuPDF library to efficiently extract text from each page of a PDF.

Intelligent Chunking: Splits extracted text into meaningful paragraphs to create focused embeddings.

Local Embeddings: Leverages your own Ollama instance to generate embeddings, ensuring your data remains completely private.

Semantic Search: Finds documents based on the meaning of your query, not just keyword matching.

Command-Line Interface: Easy-to-use CLI for both indexing your files and performing searches.

Prerequisites
Before you begin, ensure you have the following installed and running:

Python 3.8+: If you don't have it, download it from python.org.

Ollama: Download and install Ollama from ollama.com.

An Ollama Embedding Model: You need a model to generate the embeddings. We recommend mxbai-embed-large as it provides excellent performance. To pull the model, run the following command in your terminal:

ollama pull mxbai-embed-large

Running Ollama Instance: Make sure the Ollama application is running in the background before you execute the script.

Installation
Clone or Download:
Save the pdf_search.py script to a new directory on your computer.

Create requirements.txt:
In the same directory, create a file named requirements.txt and add the following content:

PyMuPDF
requests
numpy
tqdm

Install Dependencies:
Open a terminal or command prompt, navigate to your project directory, and run:

pip install -r requirements.txt

How to Use
The script operates in two main modes: indexing and searching.

1. Build the Search Index (--index)
This is the first step. The script needs to scan your PDFs and create the pdf_search_index.json file.

To index your entire home directory (default):

python pdf_search.py --index

To index a specific folder:
Use the --dir flag to specify a path. This is highly recommended to save time.

# Example for Windows
python pdf_search.py --index --dir "C:\Users\YourUser\Documents\Work"

# Example for macOS/Linux
python pdf_search.py --index --dir "/home/youruser/reports"

The script will ask for confirmation before starting. This process can be lengthy depending on the number of PDFs.

2. Search the Index (--search)
Once the index is built, you can perform searches.

Run the script with the --search flag, followed by your query in quotes:

python pdf_search.py --search "summary of the 2023 financial report"
```bash
python pdf_search.py --search "what were the key findings about machine learning models"

The script will return the top 5 most relevant PDF files, along with the specific text chunk that matched your query and a similarity score.

Configuration
You can modify the following constants at the top of the pdf_search.py script:

DEFAULT_SEARCH_DIR: Change the default directory to scan if the --dir flag isn't used.

OLLAMA_ENDPOINT: The URL for your Ollama API endpoint (defaults to http://localhost:11434/api/embeddings).

OLLAMA_MODEL: The name of the embedding model you want to use.

INDEX_FILE: The name of the file where the search index is stored.
