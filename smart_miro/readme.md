# 🎨 Miro Board Exporter with AI Assistant

A Streamlit application that exports Miro boards to multiple formats **AND** lets you ask questions about your boards using natural language via Ollama.

## 🚀 New Features

### 🤖 AI-Powered Natural Language Queries
Ask questions about your Miro board in plain English:
- "What are the main components in this board?"
- "Summarize the workflow shown here"
- "How many connections are there between elements?"
- "List all the sticky notes"
- "What relationships exist between items?"

### 📊 Original Export Features
Export your Miro boards to:
- **PlantUML** - Text-based UML diagrams for version control
- **Mermaid.js** - Markdown-compatible diagrams (GitHub, GitLab, etc.)
- **XMI** - Standard UML interchange format
- **GraphQL Schema** - For API and data modeling
- **JSON Schema** - For data validation and documentation
- **YAML** - Human-readable configuration format

## 📋 Prerequisites

1. **Python 3.8+** installed on your system
2. **Miro Account** with access to the board you want to export
3. **Ollama** installed and running (for AI features)

## 🔧 Installation

### Step 1: Install Ollama

Ollama is a local AI runtime that lets you run large language models on your machine.

**macOS / Linux:**
```bash
curl https://ollama.ai/install.sh | sh
```

**Windows:**
Download from [ollama.ai](https://ollama.ai) and run the installer.

**Verify Installation:**
```bash
ollama --version
```

### Step 2: Download an AI Model

Ollama supports various models. Here are some recommendations:

```bash
# Recommended for general use (3.8GB)
ollama pull llama2

# Faster, smaller model (1.9GB)
ollama pull llama2:7b-chat

# Alternative: Mistral (4.1GB)
ollama pull mistral

# For code-focused queries (7.4GB)
ollama pull codellama
```

**How models work:**
- Each model has different capabilities and sizes
- Larger models (13B, 70B parameters) are more accurate but slower
- Smaller models (7B parameters) are faster but may be less detailed
- You can switch models in the app's sidebar

### Step 3: Start Ollama Server

```bash
ollama serve
```

This starts a local server at `http://localhost:11434` that the Streamlit app connects to.

**Keep this terminal open** while using the app.

### Step 4: Install Python Dependencies

```bash
cd path/to/miro-exporter
pip install -r requirements.txt
```

This installs:
- `streamlit` - Web framework
- `requests` - HTTP requests for Miro API and Ollama

### Step 5: Get Miro Credentials

1. Go to [Miro Developer Portal](https://miro.com/app/settings/user-profile/apps)
2. Click "Create new app" or select existing
3. Copy your **Access Token**
4. Find your **Board ID** from the URL:
   ```
   https://miro.com/app/board/uXjVKYYYYYY=/
                                ^^^^^^^^^ Board ID
   ```

## 🎯 Usage

### Step 1: Start the Application

```bash
streamlit run miro_exporter_with_ollama.py
```

This opens your browser automatically.

### Step 2: Configure Settings (Sidebar)

1. **Miro Settings:**
   - Paste your Access Token
   - Paste your Board ID

2. **Ollama Settings:**
   - URL (default: `http://localhost:11434`)
   - Click "Test Ollama Connection"
   - Select your AI model from dropdown

### Step 3: Load Board Data

1. Go to **"AI Assistant"** tab
2. Click **"Load Board"**
3. Wait for data to load (shows statistics)

### Step 4: Ask Questions!

Type natural language questions like:
- "What is this board about?"
- "List all the shapes and their connections"
- "What are the main sections or frames?"
- "Summarize the workflow"
- "How many items are connected to [specific item]?"

**The AI will:**
1. Read your board structure
2. Understand relationships between items
3. Answer based on actual board content
4. Use the selected Ollama model

### Step 5: Export (Optional)

1. Go to **"Export Formats"** tab
2. Select desired formats
3. Click "Generate Exports"
4. Download files

## 🧠 How the AI Integration Works

### The Process (Step-by-Step):

1. **Board Loading:**
   ```python
   # App fetches your Miro board data
   - Board metadata (name, description)
   - All items (shapes, notes, connectors)
   - Relationships between items
   ```

2. **Context Creation:**
   ```python
   # App creates a text summary of your board
   "BOARD INFORMATION:
   - Name: System Architecture
   - Shapes: 15
   - Connectors: 8
   
   SHAPES:
   1. [rectangle] User Interface
   2. [rectangle] Backend API
   ...
   
   CONNECTIONS:
   1. 'User Interface' --> 'Backend API'
   2. 'Backend API' --> 'Database'
   ..."
   ```

3. **Query Processing:**
   ```python
   # When you ask a question, the app:
   1. Takes your question
   2. Combines it with board context
   3. Sends to Ollama
   4. Returns AI-generated answer
   ```

4. **Response Generation:**
   - Ollama processes the combined prompt
   - Uses its language understanding
   - Generates human-readable answer
   - Returns to the app

### Example Interaction:

**Your Question:**
> "What are the main components and how do they connect?"

**Context Sent to AI:**
```
BOARD INFORMATION: [Board details...]
SHAPES: [List of all shapes...]
CONNECTIONS: [List of all connections...]

User Question: What are the main components and how do they connect?
```

**AI Response:**
> "Based on the board, the main components are:
> 1. User Interface - The front-end layer
> 2. Backend API - Handles business logic
> 3. Database - Stores data
> 
> They connect in this flow:
> User Interface → Backend API → Database
> 
> This represents a typical three-tier architecture..."

## 📊 Understanding the Code

### Key Components:

#### 1. OllamaClient Class
```python
class OllamaClient:
    """Handles communication with Ollama"""
    
    def query(prompt, model, context):
        # Combines your question with board context
        # Sends to Ollama API
        # Returns response
        pass
    
    def test_connection():
        # Checks if Ollama is running
        pass
    
    def list_models():
        # Gets available AI models
        pass
```

**Why this matters:**
- Abstracts Ollama communication
- Makes it easy to switch models
- Handles errors gracefully

#### 2. MiroExporter.create_board_context()
```python
def create_board_context(board_info, structure, items):
    """Converts board data into readable text for AI"""
    
    # Creates a text description like:
    # "BOARD INFORMATION:
    #  - Name: My Board
    #  - Shapes: 10
    #  
    #  SHAPES:
    #  1. [rectangle] Component A
    #  2. [circle] Component B
    #  
    #  CONNECTIONS:
    #  1. 'Component A' --> 'Component B'"
    
    return context_text
```

**Why this matters:**
- AI models work with text, not raw JSON
- Structured format helps AI understand relationships
- Limits token usage (first 50 items of each type)

#### 3. Session State
```python
# Streamlit maintains state between interactions
st.session_state.board_data      # Loaded board flag
st.session_state.board_info      # Board metadata
st.session_state.structure       # Parsed structure
st.session_state.items           # All items
st.session_state.chat_history    # Conversation history
```

**Why this matters:**
- Board data loads once, used multiple times
- Chat history persists during session
- No need to reload board for each question

### Data Flow Diagram:

```
┌──────────────┐
│ Miro API     │
└──────┬───────┘
       │ 1. Fetch board
       ↓
┌──────────────────┐
│ MiroExporter     │
│ - get_board()    │
│ - get_items()    │
│ - parse()        │
└──────┬───────────┘
       │ 2. Parse structure
       ↓
┌──────────────────────┐
│ Session State        │
│ - board_info         │
│ - structure          │
│ - items              │
└──────┬───────────────┘
       │ 3. On user question
       ↓
┌────────────────────────┐
│ create_board_context() │
│ (Converts to text)     │
└──────┬─────────────────┘
       │ 4. Context + Question
       ↓
┌──────────────────┐
│ OllamaClient     │
│ - Send to Ollama │
└──────┬───────────┘
       │ 5. AI Response
       ↓
┌──────────────────┐
│ Display to User  │
└──────────────────┘
```

## 🛠️ Customization

### Change AI Behavior

Modify the prompt in `create_board_context()`:

```python
def create_board_context(self, board_info, structure, items):
    # Add custom instructions
    context_parts = [
        "You are a Miro board analyst.",
        "Focus on architectural patterns and workflows.",
        "Be concise but detailed.",
        "",
        "BOARD INFORMATION:",
        # ... rest of context
    ]
```

### Add Custom Query Templates

```python
# In the UI section
preset_queries = {
    "Architecture": "Describe the system architecture",
    "Workflow": "Explain the workflow step by step",
    "Data Flow": "Trace how data flows through the system"
}

for name, query in preset_queries.items():
    if st.button(name):
        # Submit query automatically
```

### Use Different Models for Different Tasks

```python
# Map task types to optimal models
model_mapping = {
    "code": "codellama",      # For code-related boards
    "general": "llama2",      # For general boards
    "creative": "mistral"     # For brainstorming boards
}

# Auto-select based on board content
if "code" in board_name.lower():
    model = "codellama"
```

## 🐛 Troubleshooting

### Ollama Issues

**"Cannot connect to Ollama"**
```bash
# Check if Ollama is running
ollama list

# Start the server
ollama serve

# Verify it's listening
curl http://localhost:11434/api/tags
```

**"Model not found"**
```bash
# List installed models
ollama list

# Pull the model
ollama pull llama2

# Verify it downloaded
ollama list
```

**Slow responses**
- This is normal for large models (13B+)
- Try a smaller model: `ollama pull llama2:7b-chat`
- Check your system resources (RAM, CPU)

### Miro API Issues

**"401 Unauthorized"**
- Access token expired or invalid
- Generate new token from Miro Developer Portal

**"404 Not Found"**
- Board ID incorrect
- Verify ID from board URL

### Memory Issues

**"Out of memory" errors**
- Large boards create large contexts
- Limit context in `create_board_context()`:
  ```python
  for i, shape in enumerate(structure['shapes'][:20], 1):  # Reduced from 50
  ```

## 💡 Use Cases

### 1. Onboarding New Team Members
```
Question: "Give me an overview of this system architecture"
→ AI explains the main components and their relationships
→ New developer understands structure quickly
```

### 2. Documentation Generation
```
Question: "List all services and their responsibilities"
→ AI extracts and organizes information
→ Copy to documentation
```

### 3. Architecture Review
```
Question: "What potential issues do you see in this design?"
→ AI analyzes connections and patterns
→ Suggests improvements
```

### 4. Meeting Prep
```
Question: "Summarize the main decision points in this board"
→ AI identifies key topics
→ Use for meeting agenda
```

## 📝 Example Queries by Board Type

### System Architecture Boards
- "What microservices are shown?"
- "Describe the data flow"
- "What are the external dependencies?"
- "Which services communicate with each other?"

### Workflow/Process Boards
- "What are the main steps in this process?"
- "What happens after [step name]?"
- "Are there any decision points?"
- "What are the inputs and outputs?"

### Brainstorming Boards
- "What are the main themes or categories?"
- "Group similar ideas together"
- "What are the most connected concepts?"

### Project Planning Boards
- "What are the major milestones?"
- "List all tasks by phase"
- "What dependencies exist?"

## 🔒 Privacy & Security

### Data Handling
- **Miro data**: Stored in session, cleared when browser closes
- **AI processing**: Happens locally via Ollama
- **No external API calls**: All AI runs on your machine
- **Chat history**: Kept in browser session only

### Best Practices
- Don't share access tokens
- Use local Ollama (not cloud LLMs) for sensitive boards
- Clear session after working with confidential boards

## 🚀 Performance Tips

### For Large Boards (1000+ items)
1. Limit context in `create_board_context()` (already limited to 50 per type)
2. Use smaller AI models (llama2:7b-chat)
3. Ask specific questions rather than broad ones

### For Faster Responses
1. Keep Ollama server running
2. Use GPU if available (Ollama auto-detects)
3. Close other applications to free RAM

### For Better Answers
1. Load fresh board data before asking questions
2. Be specific in questions
3. Ask follow-up questions for deeper analysis

## 📚 Resources

- [Miro API Documentation](https://developers.miro.com/docs)
- [Ollama Documentation](https://ollama.ai/docs)
- [Ollama Model Library](https://ollama.ai/library)
- [Streamlit Documentation](https://docs.streamlit.io/)

## 🤝 Contributing

### Adding New Query Types
1. Add preset in AI Assistant tab
2. Create specialized prompt template
3. Add to example queries section

### Supporting More Models
1. Test with new Ollama model
2. Add to recommended list
3. Document any special requirements

## 🔄 Comparison: Original vs AI-Enhanced

| Feature | Original | AI-Enhanced |
|---------|----------|-------------|
| Export formats | ✅ | ✅ |
| Board statistics | ✅ | ✅ |
| Natural language queries | ❌ | ✅ |
| Workflow analysis | ❌ | ✅ |
| Interactive Q&A | ❌ | ✅ |
| Local AI processing | ❌ | ✅ |
| Chat history | ❌ | ✅ |
| Context-aware responses | ❌ | ✅ |

---

Built with ❤️ using Streamlit, Miro API, and Ollama
