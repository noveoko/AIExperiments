#!/bin/bash

# Advanced RAG System - Setup and Quick Start Script
# This script helps you get the RAG system up and running quickly

set -e  # Exit on error

echo "=========================================="
echo "Advanced RAG System - Setup Script"
echo "=========================================="
echo ""

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if Ollama is running
check_ollama_running() {
    curl -s http://localhost:11434/api/tags >/dev/null 2>&1
}

# Step 1: Check Python
echo "Step 1: Checking Python installation..."
if ! command_exists python3; then
    echo "❌ Error: Python 3 is not installed."
    echo "Please install Python 3.8+ from https://www.python.org/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d ' ' -f 2)
echo "✅ Python $PYTHON_VERSION found"
echo ""

# Step 2: Check Ollama
echo "Step 2: Checking Ollama installation..."
if ! command_exists ollama; then
    echo "❌ Ollama is not installed."
    echo ""
    echo "To install Ollama:"
    echo "  Linux:   curl -fsSL https://ollama.com/install.sh | sh"
    echo "  macOS:   brew install ollama"
    echo "  Windows: Download from https://ollama.com/download"
    echo ""
    read -p "Press Enter after installing Ollama to continue..."
fi

# Check if Ollama is running
echo "Checking if Ollama is running..."
if check_ollama_running; then
    echo "✅ Ollama is running"
else
    echo "⚠️  Ollama is not running."
    echo "Starting Ollama server..."
    
    # Try to start Ollama in the background
    ollama serve > /dev/null 2>&1 &
    OLLAMA_PID=$!
    
    # Wait a few seconds for it to start
    sleep 3
    
    if check_ollama_running; then
        echo "✅ Ollama started successfully (PID: $OLLAMA_PID)"
    else
        echo "❌ Could not start Ollama automatically."
        echo "Please run 'ollama serve' in a separate terminal and press Enter to continue..."
        read
    fi
fi
echo ""

# Step 3: Check and pull models
echo "Step 3: Checking required models..."

check_model() {
    local model=$1
    if ollama list | grep -q "$model"; then
        echo "✅ Model $model is installed"
        return 0
    else
        echo "⚠️  Model $model is not installed"
        return 1
    fi
}

MODELS_TO_INSTALL=()

if ! check_model "nomic-embed-text"; then
    MODELS_TO_INSTALL+=("nomic-embed-text")
fi

if ! check_model "llama3.2"; then
    MODELS_TO_INSTALL+=("llama3.2")
fi

if [ ${#MODELS_TO_INSTALL[@]} -gt 0 ]; then
    echo ""
    echo "The following models need to be installed:"
    for model in "${MODELS_TO_INSTALL[@]}"; do
        echo "  - $model"
    done
    echo ""
    
    if [ "$model" == "nomic-embed-text" ]; then
        echo "nomic-embed-text: ~274 MB (embeddings)"
    fi
    if [ "$model" == "llama3.2" ]; then
        echo "llama3.2: ~2 GB (query optimization)"
    fi
    echo ""
    
    read -p "Would you like to install these models now? (y/n): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        for model in "${MODELS_TO_INSTALL[@]}"; do
            echo "Installing $model..."
            ollama pull "$model"
        done
        echo "✅ All models installed"
    else
        echo "⚠️  Models not installed. You can install them later with:"
        for model in "${MODELS_TO_INSTALL[@]}"; do
            echo "  ollama pull $model"
        done
    fi
fi
echo ""

# Step 4: Setup Python environment
echo "Step 4: Setting up Python environment..."

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Step 5: Create sample project
echo "Step 5: Setup complete!"
echo ""
echo "=========================================="
echo "Quick Start Guide"
echo "=========================================="
echo ""
echo "1. Make sure Ollama is running:"
echo "   ollama serve"
echo ""
echo "2. Activate the virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "3. Start the RAG application:"
echo "   streamlit run rag_app.py"
echo ""
echo "4. Open your browser to:"
echo "   http://localhost:8501"
echo ""
echo "5. Create a project and add directories to index"
echo ""
echo "=========================================="
echo ""

read -p "Would you like to start the application now? (y/n): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Starting RAG application..."
    echo "Press Ctrl+C to stop the application"
    echo ""
    sleep 2
    streamlit run rag_app.py
else
    echo ""
    echo "Setup complete! Run 'streamlit run rag_app.py' when you're ready."
fi
