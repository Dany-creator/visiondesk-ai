from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import mss
import mss.tools
from PIL import Image
import io
import base64
import os
from dotenv import load_dotenv
import requests

load_dotenv()

app = FastAPI()

#CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#IBM Configuration

ORCHESTRATE_API_KEY = os.getenv("ORCHESTRATE_API_KEY")
ORCHESTRATE_ENDPOINT = os.getenv("ORCHESTRATE_ENDPOINT")

class ScreenshotRequest(BaseModel):
    monitor: int=1

class CodeAnalysisRequest(BaseModel):
    code: str
    file_path: str = ""
    context: str = ""

@app.get("/")
def read_root():
    return {"Status": "VisionDesk AI Backend is running."}

@app.post("/capture-screenshot/")
def capture_screenshot(request: ScreenshotRequest):
    """Screenshot and get image in base64"""
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[request.monitor]
            screenshot = sct.grab(monitor)
            
            # PIL Image conversion
            img = Image.frombytes("RGB", screenshot.size, screenshot.brgb, "raw", "BGRX")

            #compress image
            img.thumbnail((1280, 720), Image.Resampling.LANCZOS)

            #Base64
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            img_str = base64.b64encode(buffer.getvalue()).decode()

            return {
                "success": True,
                "image": img_str,
                "dimensions": {"width": img.width, "height": img.height}
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.post("/analyze-code/")
def analyze_code(request: CodeAnalysisRequest):
    """Send the code to the watsonx Orchestrate"""
    try:
        #Call watsonx Orchestrate agent
        headers = {
            "Authorization": f"Bearer {ORCHESTRATE_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "input": {
                "code": request.code,
                "context": request.context,
                "file_path": request.file_path
            },
            "agent_id": "code-analyser"
        }

        response = requests.post(
            f"{ORCHESTRATE_ENDPOINT}/v1/agents/run",
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            result = response.json()
            return {
                "success": True,
                "analysis": result.get("output", {}).get("text", "No analysis available.")
            }
        else:
            return {
                "success": False,
                "error": f"Orchestrate API error: {response.status_code}"

            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyse-screen")
async def analyse_screen(file: UploadFile = File(...)):
    """Analyse screenshot with OCR and the context"""
    try:
        # Read Image
        contents = await file.read()
        img = Image.open(io.BytesIO(contents))

        text = pytesseract.image_to_string(img)

        headers = {
            "Authorization": f"Bearer {ORCHESTRATE_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "input": {
                "extracted_text": text,
                "image_context": "Screenshot of the user workspace."
            },
            "agent_id": "screen-interpreter"
        }

        response = requests.post(
            f"{ORCHESTRATE_ENDPOINT}/v1/agents/run",
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            return {
                "success": True,
                "interpretation": result.get("output", {}).get("text", ""),
                "extracted_text": text
            }
        else:
            return {
                "success": False,
                "error": f"API error: {response.status_code}"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)