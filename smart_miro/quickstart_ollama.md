# Quick Start Guide - AI-Enhanced Miro Exporter

## 🚀 Get AI Features Running in 10 Minutes

### Step 1: Install Ollama (3 minutes)

**macOS/Linux:**
```bash
curl https://ollama.ai/install.sh | sh
```

**Windows:**
Download from https://ollama.ai

**Verify:**
```bash
ollama --version
```

### Step 2: Get an AI Model (2 minutes)

```bash
# Recommended: Fast and capable
ollama pull llama2

# Alternative: Even faster
ollama pull llama2:7b-chat
```

**What's happening:**
- Downloads AI model to your computer (~4GB)
- Model runs locally - no internet needed after download
- Your data stays private on your machine

### Step 3: Start Ollama (30 seconds)

```bash
ollama serve
```

**Keep this terminal open!** The server must run in background.

### Step 4: Install Python App (1 minute)

```bash
pip install streamlit requests
```

### Step 5: Get Miro Credentials (2 minutes)

1. Visit: https://miro.com/app/settings/user-profile/apps
2. Create app → Copy **Access Token**
3. Open your board → Copy **Board ID** from URL

### Step 6: Run the App (30 seconds)

```bash
streamlit run miro_exporter_with_ollama.py
```

### Step 7: Configure & Load (1 minute)

In the web interface:
1. Sidebar → Paste Miro **Access Token**
2. Sidebar → Paste **Board ID**
3. Click "Test Ollama Connection" (should show ✅)
4. Tab: **AI Assistant** → Click "Load Board"

### Step 8: Ask Questions! (Instant)

Try these:
- "What's on this board?"
- "List all the components"
- "Summarize the workflow"
- "How do the elements connect?"

## 🎯 Understanding What Just Happened

### The Technology Stack:

```
┌─────────────────────────────────────┐
│  You (Browser)                      │
│  ↓                                  │
│  Streamlit App (Python)             │
│  ↓           ↓                      │
│  Miro API   Ollama (Local AI)      │
│  ↓           ↓                      │
│  Board      AI Model                │
└─────────────────────────────────────┘
```

**Step-by-step:**

1. **Streamlit** creates a web interface
2. You enter Miro credentials
3. App **fetches** your board data from Miro
4. App **converts** board to text description
5. You ask a question
6. App sends **question + board context** to Ollama
7. **Ollama** (running locally) processes with AI
8. AI **generates** answer based on your board
9. App **displays** answer to you

### Why This is Cool:

✅ **Private**: AI runs on YOUR computer, not cloud  
✅ **Fast**: Local processing, no network lag  
✅ **Free**: No API costs after initial setup  
✅ **Powerful**: Understands your board structure  
✅ **Interactive**: Natural conversation about your board  

## 📖 Common Questions

### "What models should I use?"

| Model | Size | Speed | Use Case |
|-------|------|-------|----------|
| `llama2:7b-chat` | 3.8GB | Fast | Quick answers |
| `llama2` | 3.8GB | Medium | Balanced |
| `mistral` | 4.1GB | Medium | Better reasoning |
| `codellama` | 7.4GB | Slow | Code-focused boards |

**Recommendation:** Start with `llama2:7b-chat`

### "How much does this cost?"

**$0** - Everything runs locally:
- Ollama: Free, open-source
- Models: Free to download
- Compute: Uses your computer

### "Will this work on my laptop?"

**Minimum Requirements:**
- 8GB RAM (16GB recommended)
- 10GB free disk space
- Modern CPU (any recent Intel/AMD/Apple Silicon)

**GPU (Optional):**
- Ollama auto-uses GPU if available
- Speeds up responses significantly
- Not required, but nice to have

### "Is my data safe?"

**Yes!**
- Ollama runs **locally** on your machine
- No data sent to external servers
- Board data stays in browser session
- Cleared when you close browser

### "What can I ask?"

**Great Questions:**
- "What are the main components?"
- "Summarize this workflow"
- "How many connections exist?"
- "What does [specific item] connect to?"
- "List all sticky notes"
- "Explain the architecture"

**Won't Work Well:**
- Questions about content NOT on board
- Opinions or preferences
- Future predictions
- External information

**Why:** AI only sees what's on your board!

## 🐛 Quick Troubleshooting

### ❌ "Cannot connect to Ollama"

**Problem:** Ollama server not running

**Solution:**
```bash
# Terminal 1: Start Ollama
ollama serve

# Terminal 2: Run app
streamlit run miro_exporter_with_ollama.py
```

### ❌ "Model not found"

**Problem:** Model not downloaded

**Solution:**
```bash
ollama pull llama2
```

### ❌ "401 Unauthorized" (Miro)

**Problem:** Wrong access token

**Solution:**
1. Go to Miro Developer Portal
2. Generate NEW token
3. Copy and paste again

### ❌ Slow responses

**Normal for:**
- Large models (13B+)
- First query (model loads)
- Large boards (1000+ items)

**Speed up:**
- Use smaller model: `ollama pull llama2:7b-chat`
- Close other apps
- Use GPU if available

### ❌ "Out of memory"

**Problem:** Board too large or model too big

**Solution:**
- Use smaller model: `llama2:7b-chat`
- Close other applications
- Restart Ollama: `pkill ollama && ollama serve`

## 💡 Pro Tips

### 1. Keep Ollama Running
```bash
# Leave this terminal open
ollama serve
```
Faster responses when server is already warm.

### 2. Pre-load Models
```bash
# Download while getting credentials
ollama pull llama2
```

### 3. Use Example Questions
The app has preset questions - click them to see how it works!

### 4. Ask Follow-ups
The chat remembers context:
```
You: "What are the main components?"
AI: [Lists components]
You: "Tell me more about the first one"
AI: [Explains based on context]
```

### 5. Export After Analysis
1. Use AI to understand board
2. Export to format you need
3. Include AI insights in documentation

## 🎓 Learning Path

### Level 1: Beginner (Day 1)
- ✅ Install and run
- ✅ Load a board
- ✅ Ask basic questions
- ✅ Try example queries

### Level 2: Regular User (Week 1)
- ✅ Understand model differences
- ✅ Write custom questions
- ✅ Combine AI + exports
- ✅ Use for real projects

### Level 3: Power User (Month 1)
- ✅ Customize prompts
- ✅ Try different models
- ✅ Optimize performance
- ✅ Create workflows

## 🔄 Typical Workflow

### Architecture Review:
```
1. Open Miro board
2. Load in app
3. Ask: "Give me an overview"
4. Ask: "What are potential issues?"
5. Export as PlantUML
6. Add to documentation
```

### Team Onboarding:
```
1. Load project board
2. Ask: "Explain each component"
3. Ask: "How do they interact?"
4. Export as Mermaid
5. Add to wiki
```

### Sprint Planning:
```
1. Load sprint board
2. Ask: "Summarize all tasks"
3. Ask: "What dependencies exist?"
4. Export as YAML
5. Import to project tracker
```

## 📞 Need Help?

1. Check full README_OLLAMA.md
2. Ollama docs: https://ollama.ai/docs
3. Test Ollama independently:
   ```bash
   ollama run llama2
   >>> Hello!
   ```

## 🎉 You're Ready!

Now you can:
- ✅ Ask questions about Miro boards
- ✅ Get AI-powered insights
- ✅ Export to multiple formats
- ✅ Keep everything private and local

**Next:** Try it with a real board!

---

Happy Analyzing! 🚀
