#!/usr/bin/env python3
"""
System verification script for RAG System.
Run this to check if all components are working correctly.
"""
import sys
import subprocess
from pathlib import Path


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_status(check_name, passed, message=""):
    """Print status of a check."""
    status = "✓ PASS" if passed else "✗ FAIL"
    color = "\033[92m" if passed else "\033[91m"
    reset = "\033[0m"
    print(f"{color}{status}{reset} - {check_name}")
    if message:
        print(f"      {message}")


def check_python_version():
    """Check Python version."""
    print_header("Checking Python Version")
    version = sys.version_info
    required = (3, 9)
    passed = version >= required
    print_status(
        "Python Version",
        passed,
        f"Found: {version.major}.{version.minor}.{version.micro}, Required: >= 3.9"
    )
    return passed


def check_dependencies():
    """Check if required packages are installed."""
    print_header("Checking Python Dependencies")
    
    required_packages = [
        'streamlit',
        'chromadb',
        'langchain',
        'sentence_transformers',
        'ollama',
        'pypdf',
        'docx',
        'openpyxl',
        'pandas',
        'numpy'
    ]
    
    all_installed = True
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print_status(package, True)
        except ImportError:
            print_status(package, False, "Not installed")
            all_installed = False
    
    return all_installed


def check_ollama():
    """Check if Ollama is installed and running."""
    print_header("Checking Ollama")
    
    try:
        import ollama
        
        # Try to connect
        models = ollama.list()
        print_status("Ollama Connection", True, "Connected successfully")
        
        # Check for required models
        model_names = [m['name'] for m in models.get('models', [])]
        
        required_models = ['nomic-embed-text', 'llama3.2']
        all_models_present = True
        
        for model in required_models:
            present = any(model in name for name in model_names)
            print_status(
                f"Model: {model}",
                present,
                "Installed" if present else "Not installed - run 'ollama pull " + model + "'"
            )
            if not present:
                all_models_present = False
        
        return all_models_present
        
    except Exception as e:
        print_status("Ollama Connection", False, f"Error: {str(e)}")
        print("\n      Please ensure Ollama is installed and running.")
        print("      Install from: https://ollama.ai")
        return False


def check_file_structure():
    """Check if required files exist."""
    print_header("Checking File Structure")
    
    required_files = [
        'app.py',
        'config.py',
        'document_processor.py',
        'vector_store.py',
        'query_improver.py',
        'requirements.txt',
        'README.md'
    ]
    
    all_present = True
    
    for filename in required_files:
        filepath = Path(filename)
        present = filepath.exists()
        print_status(filename, present)
        if not present:
            all_present = False
    
    return all_present


def check_imports():
    """Check if main modules can be imported."""
    print_header("Checking Module Imports")
    
    modules = [
        'config',
        'document_processor',
        'vector_store',
        'query_improver'
    ]
    
    all_imported = True
    
    for module in modules:
        try:
            __import__(module)
            print_status(module, True)
        except Exception as e:
            print_status(module, False, f"Error: {str(e)}")
            all_imported = False
    
    return all_imported


def main():
    """Run all checks."""
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║         RAG System - Verification Script                  ║")
    print("╚════════════════════════════════════════════════════════════╝")
    
    checks = [
        ("Python Version", check_python_version),
        ("File Structure", check_file_structure),
        ("Python Dependencies", check_dependencies),
        ("Module Imports", check_imports),
        ("Ollama Setup", check_ollama),
    ]
    
    results = []
    for check_name, check_func in checks:
        try:
            results.append(check_func())
        except Exception as e:
            print_status(check_name, False, f"Unexpected error: {str(e)}")
            results.append(False)
    
    # Summary
    print_header("Summary")
    
    total = len(results)
    passed = sum(results)
    
    print(f"\nTotal Checks: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    
    if all(results):
        print("\n✓ All checks passed! Your system is ready to use.")
        print("\nTo start the application, run:")
        print("  streamlit run app.py")
    else:
        print("\n✗ Some checks failed. Please address the issues above.")
        print("\nFor installation help, see:")
        print("  - README.md")
        print("  - Run: ./setup.sh (Linux/Mac)")
    
    print("\n")
    
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
