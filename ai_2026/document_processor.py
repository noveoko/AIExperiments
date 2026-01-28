"""
Document loading and intelligent chunking for RAG system.
"""
import os
from pathlib import Path
from typing import List, Dict, Optional
import logging

# Document loaders
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    Docx2txtLoader,
    CSVLoader,
    UnstructuredExcelLoader
)

from config import (
    CHUNK_SIZE, 
    CHUNK_OVERLAP, 
    SUPPORTED_EXTENSIONS,
    is_supported_file
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Handles document loading and intelligent chunking."""
    
    def __init__(self, chunk_size: int = CHUNK_SIZE, 
                 chunk_overlap: int = CHUNK_OVERLAP):
        """
        Initialize document processor.
        
        Args:
            chunk_size: Size of text chunks in characters
            chunk_overlap: Overlap between chunks for context continuity
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Code-aware separators for better chunking
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=[
                "\n\n\n",  # Multiple blank lines (section breaks)
                "\n\n",    # Paragraph breaks
                "\n",      # Line breaks
                ". ",      # Sentences
                " ",       # Words
                ""         # Characters
            ]
        )
    
    def load_file(self, filepath: str) -> List[Document]:
        """
        Load a single file and return documents.
        
        Args:
            filepath: Path to the file
            
        Returns:
            List of Document objects
        """
        if not is_supported_file(filepath):
            logger.warning(f"Unsupported file type: {filepath}")
            return []
        
        try:
            extension = Path(filepath).suffix.lower()
            
            # Select appropriate loader based on file type
            if extension == '.pdf':
                loader = PyPDFLoader(filepath)
            elif extension == '.docx':
                loader = Docx2txtLoader(filepath)
            elif extension == '.csv':
                loader = CSVLoader(filepath)
            elif extension in ['.xlsx', '.xls']:
                loader = UnstructuredExcelLoader(filepath)
            else:
                # Default text loader for code and text files
                loader = TextLoader(filepath, encoding='utf-8')
            
            documents = loader.load()
            
            # Add metadata
            for doc in documents:
                doc.metadata.update({
                    'source': filepath,
                    'filename': os.path.basename(filepath),
                    'file_type': extension
                })
            
            return documents
            
        except Exception as e:
            logger.error(f"Error loading {filepath}: {e}")
            return []
    
    def load_directory(self, directory_path: str, 
                       recursive: bool = True) -> List[Document]:
        """
        Load all supported files from a directory.
        
        Args:
            directory_path: Path to directory
            recursive: Whether to search subdirectories
            
        Returns:
            List of all loaded documents
        """
        all_documents = []
        dir_path = Path(directory_path)
        
        if not dir_path.exists() or not dir_path.is_dir():
            logger.error(f"Invalid directory: {directory_path}")
            return []
        
        # Find all supported files
        pattern = '**/*' if recursive else '*'
        for filepath in dir_path.glob(pattern):
            if filepath.is_file() and is_supported_file(str(filepath)):
                docs = self.load_file(str(filepath))
                all_documents.extend(docs)
                logger.info(f"Loaded {len(docs)} documents from {filepath.name}")
        
        return all_documents
    
    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """
        Split documents into intelligent chunks.
        
        This method uses recursive character splitting to maintain context
        and coherence across chunks.
        
        Args:
            documents: List of Document objects to chunk
            
        Returns:
            List of chunked Document objects with preserved metadata
        """
        if not documents:
            return []
        
        chunked_docs = self.text_splitter.split_documents(documents)
        
        # Add chunk metadata
        for i, doc in enumerate(chunked_docs):
            doc.metadata['chunk_id'] = i
            doc.metadata['chunk_size'] = len(doc.page_content)
        
        logger.info(f"Created {len(chunked_docs)} chunks from {len(documents)} documents")
        return chunked_docs
    
    def process_directories(self, directories: List[str]) -> List[Document]:
        """
        Process multiple directories and return chunked documents.
        
        This is the main pipeline:
        1. Load all files from all directories
        2. Chunk them intelligently
        3. Return processed documents ready for embedding
        
        Args:
            directories: List of directory paths to process
            
        Returns:
            List of chunked, processed documents
        """
        all_documents = []
        
        for directory in directories:
            logger.info(f"Processing directory: {directory}")
            docs = self.load_directory(directory, recursive=True)
            all_documents.extend(docs)
        
        logger.info(f"Loaded {len(all_documents)} raw documents")
        
        # Chunk all documents
        chunked_documents = self.chunk_documents(all_documents)
        
        return chunked_documents
    
    def get_directory_stats(self, directory: str) -> Dict:
        """
        Get statistics about a directory.
        
        Args:
            directory: Path to directory
            
        Returns:
            Dictionary with file counts and types
        """
        stats = {
            'total_files': 0,
            'supported_files': 0,
            'file_types': {},
            'total_size': 0
        }
        
        dir_path = Path(directory)
        if not dir_path.exists():
            return stats
        
        for filepath in dir_path.rglob('*'):
            if filepath.is_file():
                stats['total_files'] += 1
                ext = filepath.suffix.lower()
                
                if is_supported_file(str(filepath)):
                    stats['supported_files'] += 1
                    stats['file_types'][ext] = stats['file_types'].get(ext, 0) + 1
                    stats['total_size'] += filepath.stat().st_size
        
        return stats
