"""
Vector store management and intelligent retrieval with quality assessment.
"""
from typing import List, Dict, Tuple, Optional
import logging
import numpy as np

import chromadb
from chromadb.config import Settings
from langchain.schema import Document
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma

from config import (
    DEFAULT_EMBEDDING_MODEL,
    CHROMA_DB_DIR,
    TOP_K_RESULTS,
    calculate_quality_score
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VectorStoreManager:
    """Manages vector store operations with quality assessment."""
    
    def __init__(self, embedding_model: str = DEFAULT_EMBEDDING_MODEL):
        """
        Initialize vector store manager.
        
        Args:
            embedding_model: Name of Ollama embedding model to use
        """
        self.embedding_model = embedding_model
        self.embeddings = None
        self.vectorstore = None
        self._initialize_embeddings()
    
    def _initialize_embeddings(self):
        """Initialize Ollama embeddings."""
        try:
            self.embeddings = OllamaEmbeddings(
                model=self.embedding_model,
                base_url="http://localhost:11434"
            )
            logger.info(f"Initialized embeddings with model: {self.embedding_model}")
        except Exception as e:
            logger.error(f"Error initializing embeddings: {e}")
            raise
    
    def create_or_load_vectorstore(self, project_name: str, 
                                   documents: Optional[List[Document]] = None) -> bool:
        """
        Create a new vector store or load an existing one.
        
        Args:
            project_name: Name of the project (used as collection name)
            documents: Optional list of documents to add (for new stores)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            collection_name = self._sanitize_collection_name(project_name)
            
            if documents:
                # Create new vectorstore with documents
                self.vectorstore = Chroma.from_documents(
                    documents=documents,
                    embedding=self.embeddings,
                    collection_name=collection_name,
                    persist_directory=str(CHROMA_DB_DIR)
                )
                logger.info(f"Created vectorstore with {len(documents)} documents")
            else:
                # Load existing vectorstore
                self.vectorstore = Chroma(
                    collection_name=collection_name,
                    embedding_function=self.embeddings,
                    persist_directory=str(CHROMA_DB_DIR)
                )
                logger.info(f"Loaded existing vectorstore: {collection_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating/loading vectorstore: {e}")
            return False
    
    def add_documents(self, documents: List[Document]) -> bool:
        """
        Add documents to the current vector store.
        
        Args:
            documents: List of documents to add
            
        Returns:
            True if successful, False otherwise
        """
        if not self.vectorstore:
            logger.error("No vectorstore initialized")
            return False
        
        try:
            self.vectorstore.add_documents(documents)
            logger.info(f"Added {len(documents)} documents to vectorstore")
            return True
        except Exception as e:
            logger.error(f"Error adding documents: {e}")
            return False
    
    def search(self, query: str, k: int = TOP_K_RESULTS) -> List[Dict]:
        """
        Search for relevant documents with quality assessment.
        
        This method:
        1. Performs similarity search
        2. Calculates quality scores
        3. Returns results with metadata and quality ratings
        
        Args:
            query: Search query
            k: Number of results to return
            
        Returns:
            List of dictionaries containing:
                - content: The chunk text
                - metadata: Source file, chunk info, etc.
                - score: Similarity score (0-1)
                - quality: Quality rating (high/medium/low)
        """
        if not self.vectorstore:
            logger.error("No vectorstore initialized")
            return []
        
        try:
            # Perform similarity search with scores
            results = self.vectorstore.similarity_search_with_score(query, k=k)
            
            # Process results and add quality assessment
            processed_results = []
            for doc, score in results:
                # Convert distance to similarity (ChromaDB returns L2 distance)
                # Lower distance = higher similarity
                similarity = 1 / (1 + score)
                
                quality = calculate_quality_score(similarity)
                
                result = {
                    'content': doc.page_content,
                    'metadata': doc.metadata,
                    'score': similarity,
                    'quality': quality
                }
                processed_results.append(result)
            
            return processed_results
            
        except Exception as e:
            logger.error(f"Error searching: {e}")
            return []
    
    def assess_overall_quality(self, results: List[Dict]) -> Tuple[str, str]:
        """
        Assess overall quality of search results.
        
        Args:
            results: List of search results
            
        Returns:
            Tuple of (overall_quality, advice_message)
        """
        if not results:
            return "low", "No results found. Please refine your query."
        
        # Calculate average quality
        quality_scores = []
        for result in results:
            if result['quality'] == 'high':
                quality_scores.append(3)
            elif result['quality'] == 'medium':
                quality_scores.append(2)
            else:
                quality_scores.append(1)
        
        avg_score = np.mean(quality_scores)
        
        # Determine overall quality
        if avg_score >= 2.5:
            overall_quality = "high"
            advice = "Results are highly relevant to your query."
        elif avg_score >= 1.5:
            overall_quality = "medium"
            advice = "Results are somewhat relevant. Consider refining your query for better results."
        else:
            overall_quality = "low"
            advice = "Results have low relevance. Please improve your query with more specific terms or context."
        
        return overall_quality, advice
    
    def get_collection_stats(self) -> Dict:
        """
        Get statistics about the current collection.
        
        Returns:
            Dictionary with collection statistics
        """
        if not self.vectorstore:
            return {}
        
        try:
            collection = self.vectorstore._collection
            count = collection.count()
            
            return {
                'document_count': count,
                'collection_name': collection.name
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}
    
    def delete_collection(self, project_name: str) -> bool:
        """
        Delete a collection from the vector store.
        
        Args:
            project_name: Name of the project/collection to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            collection_name = self._sanitize_collection_name(project_name)
            client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
            client.delete_collection(name=collection_name)
            logger.info(f"Deleted collection: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")
            return False
    
    @staticmethod
    def _sanitize_collection_name(name: str) -> str:
        """
        Sanitize collection name to meet ChromaDB requirements.
        
        Collection names must:
        - Be 3-63 characters long
        - Start and end with alphanumeric
        - Contain only alphanumeric, underscores, or hyphens
        
        Args:
            name: Original name
            
        Returns:
            Sanitized name
        """
        # Replace spaces and special chars with underscores
        sanitized = ''.join(c if c.isalnum() or c in '-_' else '_' for c in name)
        
        # Ensure starts with alphanumeric
        sanitized = sanitized.lstrip('-_')
        if not sanitized or not sanitized[0].isalnum():
            sanitized = 'p_' + sanitized
        
        # Ensure ends with alphanumeric
        sanitized = sanitized.rstrip('-_')
        
        # Ensure length constraints
        if len(sanitized) < 3:
            sanitized = sanitized + '_collection'
        elif len(sanitized) > 63:
            sanitized = sanitized[:63]
        
        return sanitized.lower()
