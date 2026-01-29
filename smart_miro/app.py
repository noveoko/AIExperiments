import streamlit as st
import requests
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

# Page config
st.set_page_config(
    page_title="Miro Board Exporter with AI",
    page_icon="🎨",
    layout="wide"
)

class OllamaClient:
    """Handler for Ollama API interactions for natural language queries"""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        """
        Initialize Ollama client
        
        Args:
            base_url: The URL where Ollama is running (default: http://localhost:11434)
        """
        self.base_url = base_url
        self.api_url = f"{base_url}/api/generate"
    
    def query(self, prompt: str, model: str = "llama2", context: str = "") -> str:
        """
        Send a query to Ollama and get a response
        
        Args:
            prompt: The user's question
            model: The Ollama model to use (default: llama2)
            context: Additional context to provide to the model
        
        Returns:
            The model's response as a string
        """
        # Construct the full prompt with context
        full_prompt = f"{context}\n\nUser Question: {prompt}\n\nAnswer:"
        
        payload = {
            "model": model,
            "prompt": full_prompt,
            "stream": False
        }
        
        try:
            response = requests.post(self.api_url, json=payload)
            response.raise_for_status()
            return response.json().get('response', 'No response received')
        except Exception as e:
            raise Exception(f"Ollama query failed: {str(e)}")
    
    def test_connection(self) -> bool:
        """Test if Ollama is accessible"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def list_models(self) -> List[str]:
        """Get list of available models"""
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            models = response.json().get('models', [])
            return [model['name'] for model in models]
        except:
            return []


class MiroExporter:
    """Handler for Miro API interactions and board parsing"""
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.miro.com/v2"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    def get_board(self, board_id: str) -> Dict[str, Any]:
        """Fetch board metadata"""
        url = f"{self.base_url}/boards/{board_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def get_board_items(self, board_id: str) -> List[Dict[str, Any]]:
        """Fetch all items from a Miro board"""
        items = []
        url = f"{self.base_url}/boards/{board_id}/items"
        
        while url:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            items.extend(data.get('data', []))
            
            # Handle pagination
            url = data.get('links', {}).get('next')
        
        return items
    
    def parse_board_structure(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Parse board items into a structured format"""
        structure = {
            'shapes': [],
            'sticky_notes': [],
            'text': [],
            'connectors': [],
            'frames': [],
            'other': []
        }
        
        for item in items:
            item_type = item.get('type', 'unknown')
            
            if item_type == 'shape':
                structure['shapes'].append(item)
            elif item_type == 'sticky_note':
                structure['sticky_notes'].append(item)
            elif item_type == 'text':
                structure['text'].append(item)
            elif item_type == 'connector':
                structure['connectors'].append(item)
            elif item_type == 'frame':
                structure['frames'].append(item)
            else:
                structure['other'].append(item)
        
        return structure
    
    def create_board_context(self, board_info: Dict[str, Any], structure: Dict[str, Any], items: List[Dict[str, Any]]) -> str:
        """
        Create a text context describing the board for the AI
        
        This converts the board structure into a readable format that the AI can understand
        """
        context_parts = []
        
        # Board metadata
        context_parts.append(f"BOARD INFORMATION:")
        context_parts.append(f"- Name: {board_info.get('name', 'Untitled')}")
        context_parts.append(f"- Total Items: {len(items)}")
        context_parts.append(f"- Shapes: {len(structure['shapes'])}")
        context_parts.append(f"- Sticky Notes: {len(structure['sticky_notes'])}")
        context_parts.append(f"- Connectors: {len(structure['connectors'])}")
        context_parts.append(f"- Frames: {len(structure['frames'])}")
        context_parts.append("")
        
        # Shapes content
        if structure['shapes']:
            context_parts.append("SHAPES:")
            for i, shape in enumerate(structure['shapes'][:50], 1):  # Limit to first 50
                data = shape.get('data', {})
                content = data.get('content', '').strip()
                shape_type = data.get('shape', 'rectangle')
                if content:
                    context_parts.append(f"{i}. [{shape_type}] {content}")
            if len(structure['shapes']) > 50:
                context_parts.append(f"... and {len(structure['shapes']) - 50} more shapes")
            context_parts.append("")
        
        # Sticky notes content
        if structure['sticky_notes']:
            context_parts.append("STICKY NOTES:")
            for i, note in enumerate(structure['sticky_notes'][:50], 1):
                data = note.get('data', {})
                content = data.get('content', '').strip()
                if content:
                    context_parts.append(f"{i}. {content}")
            if len(structure['sticky_notes']) > 50:
                context_parts.append(f"... and {len(structure['sticky_notes']) - 50} more notes")
            context_parts.append("")
        
        # Relationships (connectors)
        if structure['connectors']:
            context_parts.append("CONNECTIONS:")
            for i, connector in enumerate(structure['connectors'][:30], 1):
                start_id = connector.get('startItem', {}).get('id')
                end_id = connector.get('endItem', {}).get('id')
                
                # Find the actual items
                start_item = next((item for item in items if item.get('id') == start_id), None)
                end_item = next((item for item in items if item.get('id') == end_id), None)
                
                if start_item and end_item:
                    start_content = start_item.get('data', {}).get('content', 'Unknown')[:30]
                    end_content = end_item.get('data', {}).get('content', 'Unknown')[:30]
                    context_parts.append(f"{i}. '{start_content}' --> '{end_content}'")
            if len(structure['connectors']) > 30:
                context_parts.append(f"... and {len(structure['connectors']) - 30} more connections")
            context_parts.append("")
        
        # Frames (logical groupings)
        if structure['frames']:
            context_parts.append("FRAMES (Logical Groups):")
            for i, frame in enumerate(structure['frames'][:20], 1):
                data = frame.get('data', {})
                title = data.get('title', 'Untitled Frame')
                context_parts.append(f"{i}. {title}")
            if len(structure['frames']) > 20:
                context_parts.append(f"... and {len(structure['frames']) - 20} more frames")
        
        return "\n".join(context_parts)


class FormatConverter:
    """Convert Miro board data to various output formats"""
    
    @staticmethod
    def to_plantuml(structure: Dict[str, Any], board_info: Dict[str, Any]) -> str:
        """Convert to PlantUML format"""
        output = ["@startuml"]
        output.append(f"title {board_info.get('name', 'Miro Board')}")
        output.append("")
        
        # Add shapes as classes or components
        for shape in structure['shapes']:
            data = shape.get('data', {})
            shape_id = shape.get('id', 'unknown')
            content = data.get('content', '').replace('\n', ' ')
            shape_type = data.get('shape', 'rectangle')
            
            if content:
                output.append(f"rectangle \"{content}\" as {shape_id}")
        
        # Add sticky notes as notes
        for note in structure['sticky_notes']:
            data = note.get('data', {})
            content = data.get('content', '').replace('\n', '\\n')
            if content:
                output.append(f"note \"{content}\" as note_{note.get('id', 'unknown')}")
        
        output.append("")
        
        # Add connectors as relationships
        for connector in structure['connectors']:
            start = connector.get('startItem', {}).get('id')
            end = connector.get('endItem', {}).get('id')
            
            if start and end:
                output.append(f"{start} --> {end}")
        
        output.append("@enduml")
        return "\n".join(output)
    
    @staticmethod
    def to_mermaid(structure: Dict[str, Any], board_info: Dict[str, Any]) -> str:
        """Convert to Mermaid.js format"""
        output = ["graph TD"]
        output.append(f"    %% {board_info.get('name', 'Miro Board')}")
        output.append("")
        
        # Add shapes as nodes
        for shape in structure['shapes']:
            data = shape.get('data', {})
            shape_id = shape.get('id', 'unknown').replace('-', '_')
            content = data.get('content', '').replace('\n', ' ').replace('"', "'")
            
            if content:
                output.append(f"    {shape_id}[\"{content}\"]")
        
        # Add sticky notes
        for note in structure['sticky_notes']:
            data = note.get('data', {})
            note_id = note.get('id', 'unknown').replace('-', '_')
            content = data.get('content', '').replace('\n', ' ').replace('"', "'")
            
            if content:
                output.append(f"    {note_id}{{\"{content}\"}}")
        
        output.append("")
        
        # Add connectors as edges
        for connector in structure['connectors']:
            start = connector.get('startItem', {}).get('id', '').replace('-', '_')
            end = connector.get('endItem', {}).get('id', '').replace('-', '_')
            
            if start and end:
                output.append(f"    {start} --> {end}")
        
        return "\n".join(output)
    
    @staticmethod
    def to_xmi(structure: Dict[str, Any], board_info: Dict[str, Any]) -> str:
        """Convert to XMI format (simplified UML XML)"""
        output = ['<?xml version="1.0" encoding="UTF-8"?>']
        output.append('<XMI xmi.version="2.1" xmlns:uml="http://schema.omg.org/spec/UML/2.1">')
        output.append(f'  <uml:Model name="{board_info.get("name", "MiroBoard")}">')
        
        # Add shapes as classes
        for shape in structure['shapes']:
            data = shape.get('data', {})
            shape_id = shape.get('id', 'unknown')
            content = data.get('content', '').replace('<', '&lt;').replace('>', '&gt;')
            
            output.append(f'    <packagedElement xmi:type="uml:Class" xmi:id="{shape_id}" name="{content}"/>')
        
        output.append('  </uml:Model>')
        output.append('</XMI>')
        return "\n".join(output)
    
    @staticmethod
    def to_graphql(structure: Dict[str, Any], board_info: Dict[str, Any]) -> str:
        """Convert to GraphQL Schema format"""
        output = [f"# GraphQL Schema generated from: {board_info.get('name', 'Miro Board')}"]
        output.append(f"# Generated: {datetime.now().isoformat()}")
        output.append("")
        
        # Convert shapes to types
        for shape in structure['shapes']:
            data = shape.get('data', {})
            content = data.get('content', '').strip()
            
            if content:
                # Simple heuristic: treat content as type name
                type_name = content.replace(' ', '').replace('\n', '')
                output.append(f"type {type_name} {{")
                output.append(f"  id: ID!")
                output.append(f"  name: String")
                output.append("}")
                output.append("")
        
        return "\n".join(output)
    
    @staticmethod
    def to_json_schema(structure: Dict[str, Any], board_info: Dict[str, Any]) -> str:
        """Convert to JSON Schema format"""
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": board_info.get('name', 'Miro Board'),
            "type": "object",
            "properties": {},
            "required": []
        }
        
        # Add shapes as properties
        for shape in structure['shapes']:
            data = shape.get('data', {})
            content = data.get('content', '').strip()
            
            if content:
                prop_name = content.replace(' ', '_').replace('\n', '_').lower()
                schema['properties'][prop_name] = {
                    "type": "string",
                    "description": content
                }
        
        return json.dumps(schema, indent=2)
    
    @staticmethod
    def to_yaml_schema(structure: Dict[str, Any], board_info: Dict[str, Any]) -> str:
        """Convert to YAML format"""
        output = [f"# {board_info.get('name', 'Miro Board')}"]
        output.append(f"# Generated: {datetime.now().isoformat()}")
        output.append("")
        output.append("board:")
        output.append(f"  name: {board_info.get('name', 'Untitled')}")
        output.append("  elements:")
        
        # Add shapes
        if structure['shapes']:
            output.append("    shapes:")
            for shape in structure['shapes']:
                data = shape.get('data', {})
                content = data.get('content', '').strip()
                if content:
                    output.append(f"      - content: \"{content}\"")
                    output.append(f"        id: {shape.get('id')}")
        
        # Add sticky notes
        if structure['sticky_notes']:
            output.append("    sticky_notes:")
            for note in structure['sticky_notes']:
                data = note.get('data', {})
                content = data.get('content', '').strip()
                if content:
                    output.append(f"      - content: \"{content}\"")
                    output.append(f"        id: {note.get('id')}")
        
        return "\n".join(output)


# Initialize session state for storing board data
if 'board_data' not in st.session_state:
    st.session_state.board_data = None
if 'board_info' not in st.session_state:
    st.session_state.board_info = None
if 'structure' not in st.session_state:
    st.session_state.structure = None
if 'items' not in st.session_state:
    st.session_state.items = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# Streamlit UI
st.title("🎨 Miro Board Exporter with AI")
st.markdown("Export your Miro boards to various formats and ask questions about them using natural language!")

# Sidebar for configuration
with st.sidebar:
    st.header("🔐 Configuration")
    
    # Miro credentials
    st.subheader("Miro Settings")
    access_token = st.text_input(
        "Miro Access Token",
        type="password",
        help="Get your token from https://miro.com/app/settings/user-profile/apps"
    )
    
    board_id = st.text_input(
        "Board ID",
        help="The ID from your Miro board URL"
    )
    
    st.markdown("---")
    
    # Ollama settings
    st.subheader("🤖 Ollama Settings")
    ollama_url = st.text_input(
        "Ollama URL",
        value="http://localhost:11434",
        help="URL where Ollama is running"
    )
    
    # Test Ollama connection
    if st.button("Test Ollama Connection"):
        ollama = OllamaClient(ollama_url)
        if ollama.test_connection():
            models = ollama.list_models()
            st.success("✅ Connected to Ollama!")
            if models:
                st.info(f"Available models: {', '.join(models)}")
            else:
                st.warning("No models found. Install one with: `ollama pull llama2`")
        else:
            st.error("❌ Cannot connect to Ollama. Make sure it's running.")
            st.info("Start Ollama with: `ollama serve`")
    
    # Model selection
    ollama = OllamaClient(ollama_url)
    available_models = ollama.list_models()
    
    if available_models:
        selected_model = st.selectbox(
            "Select Model",
            available_models,
            help="Choose which Ollama model to use for queries"
        )
    else:
        selected_model = st.text_input(
            "Model Name",
            value="llama2",
            help="Enter the model name (e.g., llama2, mistral, codellama)"
        )
    
    st.markdown("---")
    st.markdown("### 📚 Quick Guide")
    st.markdown("""
    **Miro Setup:**
    1. Get token from [Miro Portal](https://miro.com/app/settings/user-profile/apps)
    2. Find Board ID in URL
    
    **Ollama Setup:**
    1. Install: [ollama.ai](https://ollama.ai)
    2. Pull model: `ollama pull llama2`
    3. Start: `ollama serve`
    """)

# Create tabs for different features
tab1, tab2, tab3 = st.tabs(["🤖 AI Assistant", "📊 Export Formats", "📈 Board Stats"])

# Tab 1: AI Assistant (Natural Language Queries)
with tab1:
    st.header("Ask Questions About Your Board")
    
    if access_token and board_id:
        # Load board data button
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info("Load your board data first to enable AI queries")
        with col2:
            load_button = st.button("🔄 Load Board", type="primary")
        
        if load_button or st.session_state.board_data:
            if load_button:
                try:
                    with st.spinner("Loading board data..."):
                        exporter = MiroExporter(access_token)
                        
                        # Fetch data
                        st.session_state.board_info = exporter.get_board(board_id)
                        st.session_state.items = exporter.get_board_items(board_id)
                        st.session_state.structure = exporter.parse_board_structure(st.session_state.items)
                        st.session_state.board_data = True
                        
                        st.success(f"✅ Loaded: {st.session_state.board_info.get('name', 'Untitled')}")
                except Exception as e:
                    st.error(f"❌ Error loading board: {str(e)}")
            
            if st.session_state.board_data:
                st.markdown("---")
                
                # Display chat history
                for chat in st.session_state.chat_history:
                    with st.chat_message("user"):
                        st.write(chat['question'])
                    with st.chat_message("assistant"):
                        st.write(chat['answer'])
                
                # Query input
                user_query = st.chat_input("Ask a question about your Miro board...")
                
                if user_query:
                    # Add 