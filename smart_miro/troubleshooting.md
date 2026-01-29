# Ollama Integration Troubleshooting Guide

## 🔍 Common Issues and Solutions

### 1. "Cannot Connect to Ollama"

#### Symptom:
```
❌ Cannot connect to Ollama. Make sure it's running.
```

#### Diagnosis Steps:

**Step 1: Check if Ollama is installed**
```bash
ollama --version
```

**Expected:** Version number (e.g., `ollama version is 0.1.17`)  
**If fails:** Ollama not installed

**Solution:**
```bash
# macOS/Linux
curl https://ollama.ai/install.sh | sh

# Windows
# Download from https://ollama.ai
```

---

**Step 2: Check if Ollama server is running**
```bash
# Check process
ps aux | grep ollama

# Or try to connect
curl http://localhost:11434/api/tags
```

**Expected:** JSON response with models list  
**If fails:** Server not running

**Solution:**
```bash
# Terminal 1 (keep this open)
ollama serve
```

---

**Step 3: Check the port**
```bash
# See what's using port 11434
lsof -i :11434

# Or on Windows
netstat -ano | findstr 11434
```

**Expected:** `ollama` process  
**If different process:** Port conflict

**Solution:**
```bash
# Kill conflicting process
# Find PID from above command
kill <PID>

# Then start Ollama
ollama serve
```

---

**Step 4: Check URL in app**

In Streamlit sidebar, verify:
```
Ollama URL: http://localhost:11434
```

**Not:** `https://` or different port

---

#### Quick Fix Summary:
```bash
# Kill any existing Ollama
pkill ollama

# Start fresh
ollama serve

# In another terminal, test
curl http://localhost:11434/api/tags

# Should return: {"models": [...]}
```

---

### 2. "Model Not Found"

#### Symptom:
```
Error: model 'llama2' not found
```

#### Diagnosis:

**Step 1: List installed models**
```bash
ollama list
```

**Expected:** List of models  
**If empty:** No models installed

**Solution:**
```bash
# Install recommended model
ollama pull llama2

# Wait for download (3-4 GB)
# Verify
ollama list
```

---

**Step 2: Check model name**

Common mistakes:
- ❌ `llama2:latest` vs ✅ `llama2`
- ❌ `Llama2` vs ✅ `llama2` (case sensitive)
- ❌ `llama-2` vs ✅ `llama2`

**Solution:** Use exact name from `ollama list`

---

**Step 3: Test model directly**
```bash
ollama run llama2
>>> Hello
```

**Expected:** Model responds  
**If fails:** Model corrupted

**Solution:**
```bash
# Remove and reinstall
ollama rm llama2
ollama pull llama2
```

---

### 3. Slow Responses (10+ seconds)

#### Symptom:
AI takes very long to respond

#### Causes and Solutions:

**Cause 1: Large Model**
```bash
# Check model size
ollama list
# Shows size column
```

**Solution:** Use smaller model
```bash
ollama pull llama2:7b-chat  # Smaller, faster
```

---

**Cause 2: First Query (Model Loading)**

**What's happening:**
- First query loads model into RAM
- Subsequent queries are faster

**Expected behavior:**
- First: 10-15 seconds
- After: 2-5 seconds

**No action needed** - this is normal

---

**Cause 3: Limited RAM**

**Check available RAM:**
```bash
# macOS/Linux
free -h

# macOS specific
vm_stat

# Windows
wmic OS get FreePhysicalMemory
```

**If < 4GB free:**
```bash
# Close other applications
# Or use smaller model
ollama pull llama2:7b-chat
```

---

**Cause 4: CPU-Only (No GPU)**

**Check GPU:**
```bash
# NVIDIA
nvidia-smi

# AMD
rocm-smi

# Apple Silicon (always has GPU)
system_profiler SPDisplaysDataType
```

**If no GPU:** Responses will be slower  
**Solution:** This is expected, or upgrade hardware

---

**Cause 5: Large Board (1000+ items)**

**What's happening:**
- Large context sent to AI
- More to process

**Solution:** 
Edit `create_board_context()` in code:
```python
# Reduce from 50 to 20
for i, shape in enumerate(structure['shapes'][:20], 1):
```

---

### 4. "Out of Memory" Errors

#### Symptom:
```
Error: failed to allocate memory
```

#### Solutions:

**Solution 1: Close Other Apps**
```bash
# Free up RAM
# Close browser tabs, other apps
```

**Solution 2: Restart Ollama**
```bash
pkill ollama
ollama serve
```

**Solution 3: Use Smaller Model**
```bash
# Remove large model
ollama rm llama2:13b

# Use smaller
ollama pull llama2:7b-chat
```

**Solution 4: Limit Context**

In `create_board_context()`:
```python
# Reduce items sent to AI
for i, shape in enumerate(structure['shapes'][:10], 1):  # Was 50
for i, note in enumerate(structure['sticky_notes'][:10], 1):  # Was 50
```

---

### 5. Incorrect or Nonsensical Answers

#### Symptom:
AI gives wrong information about board

#### Causes and Solutions:

**Cause 1: Board Data Not Loaded**

**Check:** Look for "Load Board" button  
**Solution:** Click "Load Board" first

---

**Cause 2: Hallucination**

**What's happening:**
- AI invents information not on board
- Common with creative models

**Solutions:**
1. Be more specific in questions:
   - ❌ "Tell me about this"
   - ✅ "List the shape names on this board"

2. Ask fact-based questions:
   - ✅ "How many connectors?"
   - ✅ "What text is on sticky notes?"
   - ❌ "What do you think about this design?"

3. Try different model:
   ```bash
   ollama pull mistral  # Sometimes more accurate
   ```

---

**Cause 3: Context Too Long**

**What's happening:**
- Very large boards
- AI loses focus

**Solution:** Ask focused questions:
```
Instead of: "Tell me everything about this board"
Ask: "What shapes are in the 'Database' frame?"
```

---

### 6. App Crashes or Freezes

#### Solutions:

**Solution 1: Restart Everything**
```bash
# Kill Ollama
pkill ollama

# Kill Streamlit
pkill -f streamlit

# Restart
ollama serve
streamlit run miro_exporter_with_ollama.py
```

**Solution 2: Check System Resources**
```bash
# macOS/Linux
top

# Watch for 100% CPU or RAM
```

**Solution 3: Clear Browser Cache**
```
Chrome: Ctrl+Shift+Delete
Firefox: Ctrl+Shift+Delete
Safari: Cmd+Option+E
```

**Solution 4: Use Incognito/Private Mode**
- Eliminates extension conflicts
- Fresh session state

---

### 7. "403 Forbidden" from Miro API

#### Symptom:
```
403 Client Error: Forbidden
```

#### Not an Ollama Issue!

**Cause:** Miro token lacks permissions

**Solution:**
1. Go to Miro Developer Portal
2. Check app permissions
3. Ensure `boards:read` is enabled
4. Regenerate token

---

### 8. Chat History Issues

#### Symptom:
- Responses don't remember previous questions
- Context seems lost

#### Solutions:

**Solution 1: Don't Reload Page**
- Session state clears on reload
- Keep same browser tab open

**Solution 2: Clear and Restart**
```python
# In Streamlit, add button:
if st.button("Clear History"):
    st.session_state.chat_history = []
```

**Solution 3: Check Session State**
- Look at browser console
- Ensure no JavaScript errors

---

### 9. Ollama Takes Too Much Disk Space

#### Symptom:
```bash
ollama list
# Shows many models, using 50GB+
```

#### Solution:
```bash
# Remove unused models
ollama rm mistral
ollama rm codellama

# Keep only what you need
ollama list
```

---

### 10. Different Results Each Time

#### Symptom:
Same question, different answers

#### Explanation:
**This is NORMAL** - AI models are non-deterministic

**What's happening:**
- Temperature setting adds randomness
- Ensures creative responses
- Not a bug!

**If you need consistency:**
- Ask more specific questions
- Rephrase to be more direct
- Use multiple responses and combine

---

## 🔧 Advanced Troubleshooting

### Enable Verbose Logging

**Ollama:**
```bash
OLLAMA_DEBUG=1 ollama serve
```

**Streamlit:**
```bash
streamlit run miro_exporter_with_ollama.py --logger.level debug
```

### Check Ollama Logs

**macOS/Linux:**
```bash
# Recent logs
journalctl -u ollama -f

# Or
tail -f ~/.ollama/logs/server.log
```

**Windows:**
```bash
# Check Event Viewer
# Application Logs > Ollama
```

### Test Ollama API Directly

```bash
# Test connection
curl http://localhost:11434/api/tags

# Test generation
curl http://localhost:11434/api/generate -d '{
  "model": "llama2",
  "prompt": "Hello",
  "stream": false
}'
```

### Network Issues

**Check if port is blocked:**
```bash
# Test locally
curl http://localhost:11434/api/tags

# Test network (if remote Ollama)
curl http://192.168.1.100:11434/api/tags
```

**Firewall:**
```bash
# Allow port (Linux)
sudo ufw allow 11434

# macOS
# System Preferences > Security > Firewall > Options
# Add Ollama
```

---

## 📋 Diagnostic Checklist

Before asking for help, verify:

- [ ] Ollama is installed: `ollama --version`
- [ ] Ollama is running: `ps aux | grep ollama`
- [ ] Model is installed: `ollama list`
- [ ] Port is open: `curl http://localhost:11434/api/tags`
- [ ] Miro token is valid
- [ ] Board ID is correct
- [ ] Python packages installed: `pip list | grep streamlit`
- [ ] Enough RAM available: `free -h` or Activity Monitor
- [ ] Disk space available: `df -h`

---

## 🆘 Still Not Working?

### Collect Information:

```bash
# System info
uname -a  # or systeminfo on Windows

# Ollama version
ollama --version

# Python version
python --version

# Package versions
pip list | grep -E "streamlit|requests"

# Test Ollama
curl http://localhost:11434/api/generate -d '{
  "model": "llama2",
  "prompt": "test",
  "stream": false
}'
```

### Common Patterns:

| Error Pattern | Likely Cause | Quick Fix |
|---------------|--------------|-----------|
| Connection refused | Ollama not running | `ollama serve` |
| Model not found | Model not installed | `ollama pull llama2` |
| Out of memory | Large model, small RAM | Use `llama2:7b-chat` |
| Slow first response | Model loading | Wait, it's normal |
| 401/403 Miro errors | Token issue | Regenerate token |

---

## 💡 Prevention Tips

1. **Keep Ollama Running**
   ```bash
   # Start on login (systemd example)
   sudo systemctl enable ollama
   ```

2. **Use Stable Models**
   ```bash
   # Stick with tested models
   ollama pull llama2:7b-chat
   ```

3. **Monitor Resources**
   ```bash
   # Watch RAM usage
   watch -n 2 free -h
   ```

4. **Regular Cleanup**
   ```bash
   # Remove old models monthly
   ollama list
   ollama rm <unused-model>
   ```

---

## 📚 Useful Commands Reference

```bash
# Ollama Management
ollama list                 # List models
ollama pull <model>        # Download model
ollama rm <model>          # Remove model
ollama serve               # Start server
ollama run <model>         # Test model interactively

# Process Management
ps aux | grep ollama       # Check if running
pkill ollama              # Stop Ollama
lsof -i :11434            # Check port usage

# System Monitoring
top                        # CPU/RAM usage
free -h                   # RAM available
df -h                     # Disk space
```

---

Happy troubleshooting! 🛠️
