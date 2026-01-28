"""
Query improvement using Ollama LLM.
"""
import logging
from typing import Dict, List, Optional
import ollama

from config import DEFAULT_LLM_MODEL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QueryImprover:
    """Improves user queries using Ollama LLM."""
    
    def __init__(self, model: str = DEFAULT_LLM_MODEL):
        """
        Initialize query improver.
        
        Args:
            model: Ollama model to use for query improvement
        """
        self.model = model
        self._test_connection()
    
    def _test_connection(self) -> bool:
        """Test connection to Ollama."""
        try:
            ollama.list()
            logger.info(f"Connected to Ollama, using model: {self.model}")
            return True
        except Exception as e:
            logger.warning(f"Could not connect to Ollama: {e}")
            return False
    
    def improve_query(self, query: str, context: Optional[str] = None) -> Dict:
        """
        Improve a user query for better RAG results.
        
        This method:
        1. Analyzes the query for ambiguity and vagueness
        2. Suggests specific improvements
        3. Generates an improved version
        4. Asks clarifying questions if needed
        
        Args:
            query: Original user query
            context: Optional context about the project/domain
            
        Returns:
            Dictionary containing:
                - improved_query: Enhanced version of the query
                - suggestions: List of specific improvement suggestions
                - clarifying_questions: Questions to ask the user
                - explanation: Why improvements were made
        """
        try:
            prompt = self._build_improvement_prompt(query, context)
            
            response = ollama.chat(
                model=self.model,
                messages=[
                    {
                        'role': 'system',
                        'content': 'You are a query optimization expert. Help users create better search queries for RAG systems.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            )
            
            result = self._parse_response(response['message']['content'])
            return result
            
        except Exception as e:
            logger.error(f"Error improving query: {e}")
            return {
                'improved_query': query,
                'suggestions': ['Error: Could not connect to Ollama. Please ensure it is running.'],
                'clarifying_questions': [],
                'explanation': 'Query improvement unavailable.'
            }
    
    def _build_improvement_prompt(self, query: str, context: Optional[str]) -> str:
        """
        Build the prompt for query improvement.
        
        Args:
            query: User's original query
            context: Optional context information
            
        Returns:
            Formatted prompt string
        """
        context_info = f"\n\nContext: {context}" if context else ""
        
        prompt = f"""Analyze this search query and provide improvements for a RAG (Retrieval-Augmented Generation) system.

Original Query: "{query}"{context_info}

Please provide:

1. IMPROVED_QUERY: A better version of the query with:
   - More specific technical terms
   - Clear intent
   - Relevant keywords
   - Proper structure

2. SUGGESTIONS: 3-5 specific tips for improving this query, such as:
   - Adding technical terms
   - Specifying file types, table names, or function names
   - Clarifying the goal (e.g., "how to", "definition of", "example of")
   - Including relevant context

3. CLARIFYING_QUESTIONS: 2-3 questions to ask the user to refine the query further

4. EXPLANATION: Brief explanation of why these improvements will help

Format your response EXACTLY like this:

IMPROVED_QUERY:
[your improved query here]

SUGGESTIONS:
- [suggestion 1]
- [suggestion 2]
- [suggestion 3]

CLARIFYING_QUESTIONS:
- [question 1]
- [question 2]

EXPLANATION:
[your explanation here]
"""
        return prompt
    
    def _parse_response(self, response: str) -> Dict:
        """
        Parse the LLM response into structured format.
        
        Args:
            response: Raw response from LLM
            
        Returns:
            Structured dictionary with parsed components
        """
        result = {
            'improved_query': '',
            'suggestions': [],
            'clarifying_questions': [],
            'explanation': ''
        }
        
        try:
            lines = response.strip().split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                
                if line.startswith('IMPROVED_QUERY:'):
                    current_section = 'improved_query'
                    continue
                elif line.startswith('SUGGESTIONS:'):
                    current_section = 'suggestions'
                    continue
                elif line.startswith('CLARIFYING_QUESTIONS:'):
                    current_section = 'clarifying_questions'
                    continue
                elif line.startswith('EXPLANATION:'):
                    current_section = 'explanation'
                    continue
                
                if not line:
                    continue
                
                if current_section == 'improved_query':
                    result['improved_query'] += line + ' '
                elif current_section == 'suggestions':
                    if line.startswith('-'):
                        result['suggestions'].append(line[1:].strip())
                elif current_section == 'clarifying_questions':
                    if line.startswith('-'):
                        result['clarifying_questions'].append(line[1:].strip())
                elif current_section == 'explanation':
                    result['explanation'] += line + ' '
            
            # Clean up
            result['improved_query'] = result['improved_query'].strip()
            result['explanation'] = result['explanation'].strip()
            
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
        
        return result
    
    def generate_query_variants(self, query: str, num_variants: int = 3) -> List[str]:
        """
        Generate multiple query variants for better recall.
        
        Args:
            query: Original query
            num_variants: Number of variants to generate
            
        Returns:
            List of query variants
        """
        try:
            prompt = f"""Generate {num_variants} different variations of this search query that would help find the same information in different ways:

Original Query: "{query}"

Provide {num_variants} alternative queries, each on a new line, without numbering or bullets.
"""
            
            response = ollama.chat(
                model=self.model,
                messages=[
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            )
            
            variants = [
                line.strip() 
                for line in response['message']['content'].strip().split('\n')
                if line.strip() and not line.strip().startswith(('#', '-', '*'))
            ]
            
            return variants[:num_variants]
            
        except Exception as e:
            logger.error(f"Error generating variants: {e}")
            return [query]
