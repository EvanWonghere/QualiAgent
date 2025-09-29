# backend/main.py
import json
import os
import tempfile
from typing import List
from backend import services, schemas
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from backend.models import init_db
import uvicorn

init_db()
app = FastAPI(title="Qualitative Research Agent API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- Dataset & AI Analysis Routes ---
@app.post("/upload/")
async def upload_dataset(name: str = Form(...), file: UploadFile = File(...)):
    """
    ✅ Memory-safe file upload. Streams the file to a temporary location on disk
    before processing, preventing memory overload.
    """
    suffix = ".docx" if file.filename.lower().endswith(".docx") else ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        # Stream file to disk in chunks
        while chunk := await file.read(1024 * 1024):  # Read in 1MB chunks
            temp_file.write(chunk)
        temp_path = temp_file.name

    try:
        # The service function will handle reading from the path and cleanup
        ds_id = services.save_dataset_from_path(name, temp_path)
        return {"id": ds_id, "name": name, "created_at": "now"}
    except Exception as e:
        # Ensure cleanup even if service fails
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"Failed to process dataset: {e}")

@app.get("/datasets/", response_model=List[schemas.Dataset])
def list_datasets():
    db = services.SessionLocal()
    datasets = db.query(services.Dataset).all()
    db.close()
    return datasets

@app.get("/search/")
def search(dataset_id: int, q: str, k: int = 5):
    return services.search_similar(dataset_id, q, top_k=k)

@app.post("/analyze/{dataset_id}")
def analyze(dataset_id: int):
    return services.aggregate_codes(dataset_id)

@app.post("/memo/{dataset_id}", response_model=schemas.Memo)
def get_ai_memo_preview(dataset_id: int):
    # This just returns the AI content without saving
    memo_json = services.generate_memo(dataset_id)
    if "error" in memo_json:
        raise HTTPException(status_code=500, detail=memo_json["error"])
    return {"id": 0, "title": "AI Generated Preview", "content": json.dumps(memo_json)}

# ✨ --- 新增和修改的路由 ---
@app.post("/memos/ai-generate", response_model=schemas.Memo)
def generate_and_save_memo(dataset_id: int):
    """ ✨ 根据dataset_id生成并保存AI Memo """
    memo = services.create_memo_from_ai(dataset_id)
    if not memo:
        raise HTTPException(status_code=500, detail="Failed to generate or save AI memo.")
    return memo

@app.post("/codes/ai-generate/{dataset_id}")
def generate_and_save_ai_codes(dataset_id: int):
    """ ✨ 根据dataset_id生成并保存AI Codes """
    result = services.generate_and_save_codes(dataset_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

# --- Manual CRUD Routes ---
@app.post("/transcripts/upload", response_model=schemas.Transcript)
async def handle_transcript_upload(file: UploadFile = File(...)):
    """
    ✅ Memory-safe transcript upload. Streams the file to a temporary location on disk.
    """
    suffix = ".docx" if file.filename.lower().endswith(".docx") else ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        # Stream file to disk in chunks
        while chunk := await file.read(1024 * 1024):  # Read in 1MB chunks
            temp_file.write(chunk)
        temp_path = temp_file.name

    try:
        # The service function will handle reading, creating the DB entry, and cleanup
        return services.create_transcript_from_path(temp_path)
    except Exception as e:
        # The service function should handle its own cleanup, but we double-check
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"Failed to create transcript: {e}")


@app.get("/transcripts", response_model=List[schemas.Transcript])
def get_transcripts():
    return services.list_transcripts()

@app.post("/memos", response_model=schemas.Memo)
def create_manual_memo(memo: schemas.MemoCreate):
    return services.create_memo(title=memo.title, content=memo.content)

@app.get("/memos", response_model=List[schemas.Memo])
def get_memos():
    return services.list_memos()

@app.post("/codes", response_model=schemas.Code)
def create_manual_code(code: schemas.CodeCreate):
    try:
        return services.create_code(code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/codes", response_model=List[schemas.Code])
def get_codes():
    return services.list_codes()

@app.delete("/codes/{code_id}")
def remove_code(code_id: int):
    result = services.delete_code(code_id)
    if not result["deleted"]:
        raise HTTPException(status_code=404, detail="Code not found")
    return result

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)