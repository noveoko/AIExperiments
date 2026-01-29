import streamlit as st
import requests
import json
from typing import Dict, List, Any
from datetime import datetime

# Page config
st.set_page_config(
    page_title="Miro Board Exporter",
    page_icon="🎨",
    layout="wide"
)

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


# Streamlit UI
st.title("🎨 Miro Board Exporter")
st.markdown("Export your Miro boards to various formats for documentation and version control")

# Sidebar for configuration
with st.sidebar:
    st.header("🔐 Configuration")
    
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
    st.markdown("### 📚 How to get your credentials:")
    st.markdown("""
    1. Go to [Miro Developer Portal](https://miro.com/app/settings/user-profile/apps)
    2. Create a new app or use existing
    3. Copy the Access Token
    4. Find Board ID in URL: `miro.com/app/board/{BOARD_ID}/`
    """)

# Main content area
if access_token and board_id:
    st.header("📊 Export Options")
    
    # Format selection
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Select Export Formats")
        export_plantuml = st.checkbox("PlantUML", value=True, help="Text-based UML diagrams")
        export_mermaid = st.checkbox("Mermaid.js", value=True, help="Markdown-compatible diagrams")
        export_xmi = st.checkbox("XMI", help="Standard UML interchange format")
    
    with col2:
        st.write("")  # Spacing
        st.write("")
        export_graphql = st.checkbox("GraphQL Schema", help="For API modeling")
        export_json = st.checkbox("JSON Schema", help="For data validation")
        export_yaml = st.checkbox("YAML", help="For configuration files")
    
    # Fetch and process button
    if st.button("🚀 Fetch and Export Board", type="primary"):
        try:
            with st.spinner("Connecting to Miro API..."):
                # Initialize exporter
                exporter = MiroExporter(access_token)
                converter = FormatConverter()
                
                # Fetch board data
                st.info("Fetching board metadata...")
                board_info = exporter.get_board(board_id)
                
                st.info("Fetching board items...")
                items = exporter.get_board_items(board_id)
                
                st.success(f"✅ Found {len(items)} items on board: {board_info.get('name', 'Untitled')}")
                
                # Parse structure
                structure = exporter.parse_board_structure(items)
                
                # Display statistics
                st.subheader("📈 Board Statistics")
                stat_cols = st.columns(4)
                with stat_cols[0]:
                    st.metric("Shapes", len(structure['shapes']))
                with stat_cols[1]:
                    st.metric("Sticky Notes", len(structure['sticky_notes']))
                with stat_cols[2]:
                    st.metric("Connectors", len(structure['connectors']))
                with stat_cols[3]:
                    st.metric("Total Items", len(items))
                
                st.markdown("---")
                st.subheader("📄 Exported Formats")
                
                # Generate exports
                if export_plantuml:
                    with st.expander("🔷 PlantUML", expanded=True):
                        plantuml_output = converter.to_plantuml(structure, board_info)
                        st.code(plantuml_output, language="plantuml")
                        st.download_button(
                            "💾 Download PlantUML",
                            plantuml_output,
                            file_name="miro_export.puml",
                            mime="text/plain"
                        )
                
                if export_mermaid:
                    with st.expander("🔷 Mermaid.js", expanded=True):
                        mermaid_output = converter.to_mermaid(structure, board_info)
                        st.code(mermaid_output, language="mermaid")
                        st.download_button(
                            "💾 Download Mermaid",
                            mermaid_output,
                            file_name="miro_export.mmd",
                            mime="text/plain"
                        )
                
                if export_xmi:
                    with st.expander("🔷 XMI", expanded=False):
                        xmi_output = converter.to_xmi(structure, board_info)
                        st.code(xmi_output, language="xml")
                        st.download_button(
                            "💾 Download XMI",
                            xmi_output,
                            file_name="miro_export.xmi",
                            mime="application/xml"
                        )
                
                if export_graphql:
                    with st.expander("🔷 GraphQL Schema", expanded=False):
                        graphql_output = converter.to_graphql(structure, board_info)
                        st.code(graphql_output, language="graphql")
                        st.download_button(
                            "💾 Download GraphQL",
                            graphql_output,
                            file_name="miro_export.graphql",
                            mime="text/plain"
                        )
                
                if export_json:
                    with st.expander("🔷 JSON Schema", expanded=False):
                        json_output = converter.to_json_schema(structure, board_info)
                        st.code(json_output, language="json")
                        st.download_button(
                            "💾 Download JSON Schema",
                            json_output,
                            file_name="miro_export.json",
                            mime="application/json"
                        )
                
                if export_yaml:
                    with st.expander("🔷 YAML", expanded=False):
                        yaml_output = converter.to_yaml_schema(structure, board_info)
                        st.code(yaml_output, language="yaml")
                        st.download_button(
                            "💾 Download YAML",
                            yaml_output,
                            file_name="miro_export.yaml",
                            mime="text/yaml"
                        )
        
        except requests.exceptions.HTTPError as e:
            st.error(f"❌ API Error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

else:
    st.info("👈 Please enter your Miro Access Token and Board ID in the sidebar to get started")
    
    st.markdown("---")
    st.subheader("🎯 Supported Export Formats")
    
    format_info = {
        "PlantUML": "Text-based UML diagrams, perfect for version control and documentation",
        "Mermaid.js": "Markdown-compatible diagrams that render in GitHub, GitLab, and many docs platforms",
        "XMI": "Standard UML interchange format for importing into modeling tools",
        "GraphQL Schema": "Ideal for modeling APIs and data structures",
        "JSON Schema": "For data validation and API documentation",
        "YAML": "Human-readable configuration format"
    }
    
    for format_name, description in format_info.items():
        st.markdown(f"**{format_name}**: {description}")

# Footer
st.markdown("---")
st.markdown("Built with Streamlit • [Miro API Docs](https://developers.miro.com/docs)")
