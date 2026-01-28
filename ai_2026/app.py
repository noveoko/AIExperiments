"""
RAG System - Streamlit Application

A powerful Retrieval-Augmented Generation system with:
- Project-based directory management
- Intelligent document chunking
- Quality-assessed search results
- Query improvement using Ollama
- Easy copy-paste functionality
"""
import streamlit as st
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import time

from config import (
    ConfigManager, 
    Project, 
    format_size,
    get_quality_color,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_LLM_MODEL,
    SUPPORTED_EXTENSIONS
)
from document_processor import DocumentProcessor
from vector_store import VectorStoreManager
from query_improver import QueryImprover


# Page configuration
st.set_page_config(
    page_title="RAG System",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .result-card {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        border-left: 4px solid;
    }
    .high-quality {
        border-left-color: #28a745;
        background-color: #d4edda;
    }
    .medium-quality {
        border-left-color: #ffc107;
        background-color: #fff3cd;
    }
    .low-quality {
        border-left-color: #dc3545;
        background-color: #f8d7da;
    }
    .copy-button {
        background-color: #007bff;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 0.25rem;
        border: none;
        cursor: pointer;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


# Initialize session state
def init_session_state():
    """Initialize Streamlit session state variables."""
    if 'config_manager' not in st.session_state:
        st.session_state.config_manager = ConfigManager()
    
    if 'current_project' not in st.session_state:
        st.session_state.current_project = None
    
    if 'vector_store' not in st.session_state:
        st.session_state.vector_store = VectorStoreManager()
    
    if 'query_improver' not in st.session_state:
        st.session_state.query_improver = QueryImprover()
    
    if 'search_results' not in st.session_state:
        st.session_state.search_results = []
    
    if 'show_query_help' not in st.session_state:
        st.session_state.show_query_help = False


def main():
    """Main application function."""
    init_session_state()
    
    st.title("🔍 RAG System - Intelligent Document Search")
    st.markdown("*Search your documents with AI-powered relevance scoring*")
    
    # Sidebar for navigation
    with st.sidebar:
        st.header("Navigation")
        page = st.radio(
            "Select Page",
            ["🏠 Home", "📁 Projects", "🔎 Search", "⚙️ Settings"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        st.markdown("### 🚀 Quick Info")
        st.info(f"**Embedding Model:** {DEFAULT_EMBEDDING_MODEL}\n\n**LLM Model:** {DEFAULT_LLM_MODEL}")
    
    # Route to appropriate page
    if "Home" in page:
        show_home_page()
    elif "Projects" in page:
        show_projects_page()
    elif "Search" in page:
        show_search_page()
    elif "Settings" in page:
        show_settings_page()


def show_home_page():
    """Display home page with overview and quick start."""
    st.header("Welcome to RAG System")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📚 Features")
        st.markdown("""
        - **Project Management**: Organize documents by project
        - **Intelligent Chunking**: Smart document splitting for context
        - **Quality Assessment**: Know when results are relevant
        - **Query Improvement**: AI-powered query refinement
        - **Easy Export**: Copy results for use anywhere
        """)
    
    with col2:
        st.subheader("🚀 Quick Start")
        st.markdown("""
        1. Create a new project in **Projects** tab
        2. Add directories containing your documents
        3. Index the documents (may take a few minutes)
        4. Search your documents in **Search** tab
        5. Get quality-scored results you can copy
        """)
    
    st.markdown("---")
    
    # System status
    st.subheader("📊 System Status")
    
    col1, col2, col3 = st.columns(3)
    
    projects = st.session_state.config_manager.load_projects()
    
    with col1:
        st.metric("Total Projects", len(projects))
    
    with col2:
        total_docs = sum(p.document_count for p in projects.values())
        st.metric("Indexed Documents", total_docs)
    
    with col3:
        supported_types = len(SUPPORTED_EXTENSIONS)
        st.metric("Supported File Types", supported_types)
    
    # Supported file types
    with st.expander("📄 Supported File Types"):
        extensions_str = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        st.code(extensions_str)


def show_projects_page():
    """Display projects management page."""
    st.header("📁 Project Management")
    
    tab1, tab2 = st.tabs(["📋 My Projects", "➕ Create Project"])
    
    with tab1:
        show_projects_list()
    
    with tab2:
        show_create_project()


def show_projects_list():
    """Display list of existing projects."""
    projects = st.session_state.config_manager.load_projects()
    
    if not projects:
        st.info("No projects yet. Create your first project in the 'Create Project' tab!")
        return
    
    for project_name, project in projects.items():
        with st.expander(f"📁 {project_name}", expanded=False):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"**Description:** {project.description or 'No description'}")
                st.markdown(f"**Created:** {project.created_at}")
                st.markdown(f"**Documents Indexed:** {project.document_count}")
                st.markdown(f"**Last Indexed:** {project.last_indexed or 'Never'}")
                
                st.markdown("**Directories:**")
                for directory in project.directories:
                    st.code(directory)
            
            with col2:
                if st.button("🔎 Select", key=f"select_{project_name}"):
                    st.session_state.current_project = project_name
                    st.success(f"Selected: {project_name}")
                    st.rerun()
                
                if st.button("🔄 Re-index", key=f"reindex_{project_name}"):
                    reindex_project(project)
                
                if st.button("🗑️ Delete", key=f"delete_{project_name}"):
                    delete_project(project_name)


def show_create_project():
    """Display project creation form."""
    st.subheader("Create New Project")
    
    with st.form("create_project_form"):
        project_name = st.text_input(
            "Project Name*",
            placeholder="e.g., My API Documentation"
        )
        
        description = st.text_area(
            "Description",
            placeholder="Brief description of this project..."
        )
        
        st.markdown("**Directories to Index**")
        st.caption("Add one or more directories containing your documents")
        
        # Dynamic directory inputs
        num_dirs = st.number_input("Number of directories", min_value=1, max_value=10, value=1)
        
        directories = []
        for i in range(num_dirs):
            dir_path = st.text_input(
                f"Directory {i+1}*",
                key=f"dir_{i}",
                placeholder="/path/to/your/documents"
            )
            if dir_path:
                directories.append(dir_path)
        
        submitted = st.form_submit_button("Create and Index Project")
        
        if submitted:
            if not project_name:
                st.error("Please provide a project name")
            elif not directories:
                st.error("Please add at least one directory")
            else:
                create_and_index_project(project_name, description, directories)


def create_and_index_project(name: str, description: str, directories: List[str]):
    """
    Create a new project and index its documents.
    
    Args:
        name: Project name
        description: Project description
        directories: List of directory paths
    """
    # Validate directories
    invalid_dirs = [d for d in directories if not Path(d).exists()]
    if invalid_dirs:
        st.error(f"Invalid directories: {', '.join(invalid_dirs)}")
        return
    
    # Create project
    project = Project(
        name=name,
        directories=directories,
        description=description,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    
    if not st.session_state.config_manager.add_project(project):
        st.error("Project with this name already exists!")
        return
    
    # Index documents
    with st.spinner("Indexing documents... This may take a few minutes."):
        success = index_project_documents(project)
    
    if success:
        st.success(f"✅ Project '{name}' created and indexed successfully!")
        time.sleep(1)
        st.rerun()
    else:
        st.error("Failed to index documents. Please check the logs.")


def index_project_documents(project: Project) -> bool:
    """
    Index all documents for a project.
    
    Args:
        project: Project to index
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Process documents
        processor = DocumentProcessor()
        documents = processor.process_directories(project.directories)
        
        if not documents:
            st.warning("No supported documents found in the specified directories.")
            return False
        
        # Create vector store
        success = st.session_state.vector_store.create_or_load_vectorstore(
            project.name,
            documents
        )
        
        if success:
            # Update project metadata
            project.document_count = len(documents)
            project.last_indexed = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state.config_manager.update_project(project)
        
        return success
        
    except Exception as e:
        st.error(f"Error indexing documents: {e}")
        return False


def reindex_project(project: Project):
    """Re-index a project's documents."""
    with st.spinner(f"Re-indexing {project.name}..."):
        # Delete old collection
        st.session_state.vector_store.delete_collection(project.name)
        
        # Re-index
        success = index_project_documents(project)
        
        if success:
            st.success("✅ Project re-indexed successfully!")
            time.sleep(1)
            st.rerun()


def delete_project(project_name: str):
    """Delete a project."""
    if st.session_state.config_manager.delete_project(project_name):
        st.session_state.vector_store.delete_collection(project_name)
        st.success(f"Deleted project: {project_name}")
        time.sleep(1)
        st.rerun()


def show_search_page():
    """Display search interface."""
    st.header("🔎 Search Documents")
    
    # Project selection
    projects = st.session_state.config_manager.load_projects()
    
    if not projects:
        st.warning("No projects available. Please create a project first.")
        return
    
    project_names = list(projects.keys())
    
    # Auto-select if current_project is set
    default_index = 0
    if st.session_state.current_project in project_names:
        default_index = project_names.index(st.session_state.current_project)
    
    selected_project = st.selectbox(
        "Select Project",
        project_names,
        index=default_index
    )
    
    st.session_state.current_project = selected_project
    
    # Load project
    project = projects[selected_project]
    st.info(f"📁 Searching in: **{selected_project}** ({project.document_count} documents)")
    
    # Search interface
    col1, col2 = st.columns([3, 1])
    
    with col1:
        query = st.text_input(
            "Enter your search query",
            placeholder="e.g., How do I populate table X using data from source Y?",
            key="search_query"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        improve_query = st.button("🤖 Improve Query", use_container_width=True)
    
    # Query improvement
    if improve_query and query:
        show_query_improvement(query, project.description)
    
    # Number of results
    k = st.slider("Number of results", min_value=1, max_value=20, value=5)
    
    # Search button
    if st.button("🔍 Search", type="primary", use_container_width=True):
        if not query:
            st.error("Please enter a search query")
        else:
            perform_search(selected_project, query, k)
    
    # Display results
    if st.session_state.search_results:
        show_search_results()


def show_query_improvement(query: str, context: str):
    """Show query improvement suggestions."""
    with st.spinner("Analyzing query..."):
        result = st.session_state.query_improver.improve_query(query, context)
    
    st.markdown("### 🤖 Query Improvement Suggestions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Original Query:**")
        st.code(query)
    
    with col2:
        st.markdown("**Improved Query:**")
        st.code(result['improved_query'])
        if st.button("Use Improved Query"):
            st.session_state.search_query = result['improved_query']
            st.rerun()
    
    if result['suggestions']:
        st.markdown("**💡 Suggestions:**")
        for suggestion in result['suggestions']:
            st.markdown(f"- {suggestion}")
    
    if result['clarifying_questions']:
        st.markdown("**❓ Clarifying Questions:**")
        for question in result['clarifying_questions']:
            st.markdown(f"- {question}")
    
    if result['explanation']:
        with st.expander("📝 Explanation"):
            st.write(result['explanation'])


def perform_search(project_name: str, query: str, k: int):
    """
    Perform search and store results.
    
    Args:
        project_name: Name of project to search
        query: Search query
        k: Number of results
    """
    with st.spinner("Searching..."):
        # Load vector store
        st.session_state.vector_store.create_or_load_vectorstore(project_name)
        
        # Perform search
        results = st.session_state.vector_store.search(query, k)
        
        st.session_state.search_results = results


def show_search_results():
    """Display search results with quality assessment."""
    results = st.session_state.search_results
    
    if not results:
        st.info("No results found.")
        return
    
    # Overall quality assessment
    overall_quality, advice = st.session_state.vector_store.assess_overall_quality(results)
    
    quality_color = get_quality_color(overall_quality)
    
    st.markdown(f"""
    <div style='padding: 1rem; border-radius: 0.5rem; background-color: {quality_color}20; border-left: 4px solid {quality_color};'>
        <h3 style='color: {quality_color}; margin: 0;'>Overall Quality: {overall_quality.upper()}</h3>
        <p style='margin: 0.5rem 0 0 0;'>{advice}</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Results
    st.subheader(f"📄 Found {len(results)} Results")
    
    for i, result in enumerate(results, 1):
        quality = result['quality']
        score = result['score']
        content = result['content']
        metadata = result['metadata']
        
        quality_class = f"{quality}-quality"
        
        st.markdown(f"""
        <div class='result-card {quality_class}'>
            <h4>Result #{i} - Quality: {quality.upper()} (Score: {score:.3f})</h4>
            <p><strong>Source:</strong> {metadata.get('filename', 'Unknown')}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Content in expandable section
        with st.expander(f"📖 View Content #{i}"):
            st.markdown(content)
            
            # Copy button
            st.code(content, language=None)
            
            # Metadata
            st.markdown("**Metadata:**")
            st.json(metadata)


def show_settings_page():
    """Display settings page."""
    st.header("⚙️ Settings")
    
    st.subheader("🔧 System Information")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Embedding Model:**")
        st.code(DEFAULT_EMBEDDING_MODEL)
        
        st.markdown("**LLM Model:**")
        st.code(DEFAULT_LLM_MODEL)
    
    with col2:
        st.markdown("**Chunk Size:**")
        st.code("1000 characters")
        
        st.markdown("**Chunk Overlap:**")
        st.code("200 characters")
    
    st.markdown("---")
    
    st.subheader("📋 Usage Instructions")
    
    with st.expander("🚀 How to Use This System"):
        st.markdown("""
        ### Step-by-Step Guide
        
        1. **Install Ollama**
           - Download from: https://ollama.ai
           - Pull required models:
             ```bash
             ollama pull nomic-embed-text
             ollama pull llama3.2
             ```
        
        2. **Create a Project**
           - Go to Projects tab
           - Click "Create Project"
           - Add directories containing your documents
           - Wait for indexing to complete
        
        3. **Search Your Documents**
           - Go to Search tab
           - Select your project
           - Enter your query
           - Get quality-scored results
        
        4. **Improve Your Queries**
           - Click "Improve Query" for AI suggestions
           - Follow the recommendations
           - Ask clarifying questions
        
        5. **Use the Results**
           - Copy relevant chunks
           - Paste into your LLM chat
           - Get better answers with context
        """)
    
    with st.expander("💡 Tips for Better Results"):
        st.markdown("""
        - **Be specific**: Include technical terms, table names, function names
        - **Add context**: Mention the technology or framework
        - **Use examples**: "like X" or "similar to Y"
        - **Specify intent**: "how to", "why does", "example of"
        - **Iterate**: Refine based on quality scores
        """)


if __name__ == "__main__":
    main()
