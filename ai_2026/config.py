"""
Configuration and utility functions for the RAG system.

PRIVACY & LOCAL-ONLY OPERATION:
- All data stored locally on your machine
- No cloud services or external APIs
- ChromaDB: Local embedded database
- Ollama: Local LLM inference (localhost:11434)
- No telemetry or tracking
- Complete data privacy
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import hashlib


# ============================================================================
# LOCAL-ONLY CONFIGURATION
# ============================================================================
# All services run locally - no cloud dependencies!

# Ollama Configuration (Local LLM)
OLLAMA_BASE_URL = "http://localhost:11434"  # Local Ollama server
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"  # SOTA CPU-friendly embedding model
DEFAULT_LLM_MODEL = "llama3.2"  # For query improvement

# Document Processing
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
TOP_K_RESULTS = 5

# Quality Thresholds
SIMILARITY_THRESHOLD_HIGH = 0.75
SIMILARITY_THRESHOLD_MEDIUM = 0.60
SIMILARITY_THRESHOLD_LOW = 0.45

# Local Storage Paths (Everything stored in ~/.rag_system/)
CONFIG_DIR = Path.home() / ".rag_system"
PROJECTS_FILE = CONFIG_DIR / "projects.json"  # Local project configurations
CHROMA_DB_DIR = CONFIG_DIR / "chroma_db"      # Local vector database

# Supported file extensions
SUPPORTED_EXTENSIONS = {
    '.txt', '.md', '.py', '.js', '.java', '.cpp', '.c', '.h',
    '.html', '.css', '.json', '.xml', '.yaml', '.yml',
    '.pdf', '.docx', '.csv', '.xlsx'
}


@dataclass
class Project:
    """Represents a project with its associated directories."""
    name: str
    directories: List[str]
    description: str = ""
    created_at: str = ""
    last_indexed: Optional[str] = None
    document_count: int = 0
    
    def to_dict(self) -> Dict:
        """Convert project to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Project':
        """Create project from dictionary."""
        return cls(**data)
    
    def get_hash(self) -> str:
        """Generate unique hash for the project based on name."""
        return hashlib.md5(self.name.encode()).hexdigest()


class ConfigManager:
    """Manages application configuration and project persistence."""
    
    def __init__(self):
        """Initialize configuration manager."""
        self._ensure_config_dir()
    
    def _ensure_config_dir(self):
        """Ensure configuration directory exists."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)
    
    def load_projects(self) -> Dict[str, Project]:
        """Load all projects from disk."""
        if not PROJECTS_FILE.exists():
            return {}
        
        try:
            with open(PROJECTS_FILE, 'r') as f:
                data = json.load(f)
            return {name: Project.from_dict(proj_data) 
                    for name, proj_data in data.items()}
        except Exception as e:
            print(f"Error loading projects: {e}")
            return {}
    
    def save_projects(self, projects: Dict[str, Project]):
        """Save all projects to disk."""
        try:
            data = {name: proj.to_dict() 
                    for name, proj in projects.items()}
            with open(PROJECTS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving projects: {e}")
    
    def add_project(self, project: Project) -> bool:
        """Add a new project."""
        projects = self.load_projects()
        if project.name in projects:
            return False
        projects[project.name] = project
        self.save_projects(projects)
        return True
    
    def update_project(self, project: Project):
        """Update an existing project."""
        projects = self.load_projects()
        projects[project.name] = project
        self.save_projects(projects)
    
    def delete_project(self, project_name: str) -> bool:
        """Delete a project."""
        projects = self.load_projects()
        if project_name not in projects:
            return False
        del projects[project_name]
        self.save_projects(projects)
        return True
    
    def get_project(self, project_name: str) -> Optional[Project]:
        """Get a specific project."""
        projects = self.load_projects()
        return projects.get(project_name)


def validate_directory(path: str) -> bool:
    """Validate that a directory exists and is readable."""
    p = Path(path)
    return p.exists() and p.is_dir()


def get_file_extension(filepath: str) -> str:
    """Get file extension in lowercase."""
    return Path(filepath).suffix.lower()


def is_supported_file(filepath: str) -> bool:
    """Check if file type is supported."""
    return get_file_extension(filepath) in SUPPORTED_EXTENSIONS


def format_size(bytes_size: int) -> str:
    """Format byte size to human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"


def calculate_quality_score(similarity_score: float) -> str:
    """
    Calculate quality rating based on similarity score.
    
    Args:
        similarity_score: Cosine similarity score (0-1)
    
    Returns:
        Quality rating: 'high', 'medium', or 'low'
    """
    if similarity_score >= SIMILARITY_THRESHOLD_HIGH:
        return "high"
    elif similarity_score >= SIMILARITY_THRESHOLD_MEDIUM:
        return "medium"
    else:
        return "low"


def get_quality_color(quality: str) -> str:
    """Get color code for quality rating."""
    colors = {
        "high": "#28a745",    # Green
        "medium": "#ffc107",  # Yellow/Orange
        "low": "#dc3545"      # Red
    }
    return colors.get(quality, "#6c757d")
