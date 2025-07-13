To set up **FLUX.1 [Dev]** with the **FLUX Uncensored LoRA v2** as a local API in your Python project, you’ll create a simple REST API using a framework like **FastAPI** to serve image generation requests. This setup allows you to call the API locally to generate uncensored images using your 8GB VRAM GPU. Below is a step-by-step guide to configure the FLUX.1 [Dev] model with the uncensored LoRA and expose it as an API.

---

### Prerequisites
- **Hardware**:
  - GPU with 8GB VRAM (e.g., NVIDIA RTX 3060).
  - 16GB+ system RAM (32GB recommended).
  - ~50GB free storage for models and dependencies.
- **Software**:
  - Python 3.10 or later.
  - PyTorch with CUDA support (for GPU acceleration).
  - `diffusers` library for FLUX model handling.
  - `FastAPI` and `uvicorn` for the API server.
  - Hugging Face account and API token for model downloads.
- **Ethical Note**: The FLUX Uncensored LoRA v2 bypasses content restrictions, enabling NSFW or explicit outputs. Use responsibly and comply with local laws.

---

### Step-by-Step Setup

#### 1. **Install Dependencies**
Set up a Python environment and install the required libraries.

- **Create a Virtual Environment** (optional but recommended):
  ```bash
  python -m venv flux_api_env
  source flux_api_env/bin/activate  # Linux/Mac
  flux_api_env\Scripts\activate  # Windows
  ```

- **Install Required Libraries**:
  ```bash
  pip install torch torchvision --extra-index-url https://download.pytorch.org/whl/cu121
  pip install diffusers transformers fastapi uvicorn pillow
  pip install huggingface_hub
  ```

- **Log in to Hugging Face**:
  - Generate a Hugging Face API token from your [Hugging Face profile](https://huggingface.co/settings/tokens).
  - Log in using the CLI:
    ```bash
    huggingface-cli login
    ```

#### 2. **Download FLUX.1 [Dev] and FLUX Uncensored LoRA v2**
- **Download FLUX.1 [Dev]**:
  - Use the FP8 version for 8GB VRAM compatibility to save memory:
    ```bash
    huggingface-cli download black-forest-labs/FLUX.1-dev flux1-dev.safetensors --local-dir ./flux1-dev
    ```
  - Alternatively, download the `flux1-dev-bnb-nf4-v2` quantized model for lower memory usage:
    ```bash
    huggingface-cli download lllyasviel/flux1-dev-bnb-nf4-v2 flux1-dev-bnb-nf4-v2.safetensors --local-dir ./flux1-dev
    ```

- **Download FLUX Uncensored LoRA v2**:
  ```bash
  huggingface-cli download enhanceaiteam/Flux-uncensored-v2 lora.safetensors --local-dir ./flux-uncensored-v2
  ```

- **Organize Files**:
  - Place `flux1-dev.safetensors` (or `flux1-dev-bnb-nf4-v2.safetensors`) in a directory like `./models/flux1-dev/`.
  - Place `lora.safetensors` in `./models/flux-uncensored-v2/`.

#### 3. **Create the FastAPI Application**
Create a Python script (e.g., `flux_api.py`) to set up the local API using FastAPI and the `diffusers` library.

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from diffusers import AutoPipelineForText2Image
import torch
from PIL import Image
import io
import base64
import os

# Initialize FastAPI app
app = FastAPI(title="FLUX.1 Uncensored API")

# Define request model
class ImageRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    width: int = 512
    height: int = 512
    num_inference_steps: int = 20
    guidance_scale: float = 2.0
    lora_weight: float = 1.0

# Global variable to hold the pipeline
pipeline = None

@app.on_event("startup")
def load_model():
    global pipeline
    try:
        # Load FLUX.1 [Dev] model with FP8 precision for 8GB VRAM
        model_path = "./models/flux1-dev/flux1-dev.safetensors"  # Update with your path
        print(f"Loading model from {model_path}...")
        pipeline = AutoPipelineForText2Image.from_pretrained(
            "black-forest-labs/FLUX.1-dev",
            torch_dtype=torch.bfloat16,
            use_safetensors=True,
            local_files_only=True,  # Use local model files
        ).to("cuda")

        # Load FLUX Uncensored LoRA v2
        lora_path = "./models/flux-uncensored-v2/lora.safetensors"  # Update with your path
        print(f"Loading LoRA from {lora_path}...")
        pipeline.load_lora_weights(lora_path, adapter_name="uncensored")

        # Set LoRA weight
        pipeline.set_adapters(["uncensored"], adapter_weights=[1.0])
        print("Model and LoRA loaded successfully.")
    except Exception as e:
        print(f"Error loading model: {e}")
        raise HTTPException(status_code=500, detail=f"Model loading failed: {str(e)}")

@app.post("/generate")
async def generate_image(request: ImageRequest):
    try:
        # Validate input
        if not pipeline:
            raise HTTPException(status_code=500, detail="Model not loaded")
        if request.width * request.height > 512 * 512:
            raise HTTPException(status_code=400, detail="Resolution too high for 8GB VRAM. Use 512x512 or lower.")

        # Generate image
        image = pipeline(
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            width=request.width,
            height=request.height,
            num_inference_steps=request.num_inference_steps,
            guidance_scale=request.guidance_scale
        ).images[0]

        # Convert image to base64 for API response
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

        return {"image": f"data:image/png;base64,{img_str}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")

@app.get("/health")
def health_check():
    return {"status": "API is running", "model_loaded": pipeline is not None}
```

#### 4. **Run the API**
- Save the script as `flux_api.py`.
- Ensure the model and LoRA paths in the script match your local file locations.
- Start the FastAPI server:
  ```bash
  uvicorn flux_api:app --host 0.0.0.0 --port 8000
  ```
- The API will be available at `http://localhost:8000`.

#### 5. **Test the API**
Use a tool like `curl`, Postman, or a Python script to send requests to the API.

- **Example Python Client**:
Create a script (e.g., `test_api.py`) to call the API:
```python
import requests
import base64
from PIL import Image
import io

url = "http://localhost:8000/generate"
payload = {
    "prompt": "nsfw nude woman on beach, sunset, long flowing hair, sensual pose",
    "negative_prompt": "blurry, low quality, distorted",
    "width": 512,
    "height": 512,
    "num_inference_steps": 20,
    "guidance_scale": 2.0,
    "lora_weight": 1.0
}

response = requests.post(url, json=payload)
if response.status_code == 200:
    img_data = response.json()["image"]
    img_data = img_data.split(",")[1]  # Remove "data:image/png;base64," prefix
    img_bytes = base64.b64decode(img_data)
    img = Image.open(io.BytesIO(img_bytes))
    img.save("output.png")
    print("Image saved as output.png")
else:
    print(f"Error: {response.status_code} - {response.json()}")
```

- Run the client:
  ```bash
  python test_api.py
  ```

- **Example cURL Command**:
```bash
curl -X POST "http://localhost:8000/generate" -H "Content-Type: application/json" -d '{
    "prompt": "nsfw nude woman on beach, sunset, long flowing hair, sensual pose",
    "negative_prompt": "blurry, low quality, distorted",
    "width": 512,
    "height": 512,
    "num_inference_steps": 20,
    "guidance_scale": 2.0,
    "lora_weight": 1.0
}' > response.json
```

- **Check API Health**:
  ```bash
  curl http://localhost:8000/health
  ```

#### 6. **Optimize for 8GB VRAM**
- **Use FP8 Model**: Ensure you’re using the FP8 version of FLUX.1 [Dev] (`flux1-dev-bnb-nf4-v2.safetensors`) to fit within 8GB VRAM.
- **Limit Resolution**: Stick to 512x512 or lower to avoid memory errors.
- **Single Instance**: Run only one instance of the API to prevent VRAM exhaustion.
- **Clear Memory**: If you encounter memory errors, restart the API server and close other GPU-intensive applications.
- **Batch Size**: The API is configured for single-image generation. Avoid batch processing to stay within memory limits.

#### 7. **Troubleshooting**
- **Error: Model not found**:
  - Verify the model and LoRA file paths in `flux_api.py`.
  - Ensure `local_files_only=True` only if models are downloaded locally.
- **Out of Memory Error**:
  - Use the FP8 model or reduce resolution to 256x256 for testing.
  - Check VRAM usage with `nvidia-smi` and free up memory if needed.
- **LoRA Not Applied**:
  - Confirm the LoRA is loaded correctly by checking the console output during startup.
  - Ensure the `lora_weight` in the request is set to 1.0 for full effect.
  - Use NSFW-specific prompts with trigger words like `nsfw` to test uncensored output.
- **API Not Responding**:
  - Check if `uvicorn` is running (`ps aux | grep uvicorn` or Task Manager).
  - Verify the port (8000) is not blocked by another process.
- **Slow Generation**:
  - Expect ~1–3 minutes per image on 8GB VRAM at 512x512.
  - Optimize by reducing `num_inference_steps` to 10–15 for faster results with slightly lower quality.

#### 8. **Security and Deployment Notes**
- **Local Use Only**: The API is configured for local access (`0.0.0.0:8000`). For production or remote access, add authentication and HTTPS (e.g., using a reverse proxy like Nginx).
- **Rate Limiting**: To prevent GPU overload, consider adding rate limiting with `slowapi`:
  ```bash
  pip install slowapi
  ```
  Add to `flux_api.py`:
  ```python
  from slowapi import Limiter, _rate_limit_exceeded_handler
  from slowapi.util import get_remote_address

  limiter = Limiter(key_func=get_remote_address)
  app.state.limiter = limiter
  app.add_exception_handler(429, _rate_limit_exceeded_handler)

  @app.post("/generate")
  @limiter.limit("5/minute")  # Limit to 5 requests per minute
  async def generate_image(request: ImageRequest):
      ...
  ```
- **Ethical Use**: The uncensored LoRA enables explicit content. Ensure compliance with legal and ethical standards in your region.

#### 9. **Extending the API**
- **Add More Parameters**: Extend the `ImageRequest` model to include options like `seed` for reproducible results or `scheduler` for different diffusion schedulers.
- **Save Images to Disk**: Modify the API to save images to a directory instead of returning base64:
  ```python
  output_dir = "./outputs"
  os.makedirs(output_dir, exist_ok=True)
  image.save(os.path.join(output_dir, f"image_{int(time.time())}.png"))
  return {"status": "Image saved", "path": os.path.join(output_dir, f"image_{int(time.time())}.png")}
  ```
- **Multiple LoRAs**: Support multiple LoRAs by loading additional adapters and allowing the client to specify which LoRA to use.

---

### Example API Call
```python
import requests

payload = {
    "prompt": "nsfw nude woman on beach, sunset, long flowing hair, sensual pose",
    "negative_prompt": "blurry, low quality, distorted",
    "width": 512,
    "height": 512,
    "num_inference_steps": 20,
    "guidance_scale": 2.0,
    "lora_weight": 1.0
}

response = requests.post("http://localhost:8000/generate", json=payload)
if response.status_code == 200:
    print("Image generated successfully!")
else:
    print(f"Error: {response.json()}")
```

---

### Additional Resources
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Diffusers: FLUX.1 Guide](https://huggingface.co/docs/diffusers/main/en/api/pipelines/flux)
- [Hugging Face: FLUX.1 [Dev]](https://huggingface.co/black-forest-labs/FLUX.1-dev)
- [Hugging Face: FLUX Uncensored LoRA v2](https://huggingface.co/enhanceaiteam/Flux-uncensored-v2)

If you run into specific errors (e.g., memory issues, model loading failures), share the error message, and I’ll help troubleshoot further. Let me know if you need additional features like authentication or specific API endpoints!