# backend/main.py
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import List

from sqlalchemy.orm import Session

from backend import services, schemas
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from backend.db import Base, engine, SessionLocal


# ✨ Create all database tables on startup
Base.metadata.create_all(bind=engine)
# ✨ --- 使用绝对路径来定义上传目录 ---
# 获取当前文件(main.py)的目录，然后回到上一级，即项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
UPLOAD_DIR = PROJECT_ROOT / "uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)
# ---
app = FastAPI(title="Qualitative Research Agent API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- Dataset & AI Analysis Routes ---

# ✨ --- The Database Session Dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/search/")
def search(payload: schemas.AISearchRequest, db: Session = Depends(get_db)):
    return services.search_similar(
        db=db,
        transcript_id=payload.transcript_id,
        query=payload.query,
        top_k=payload.top_k,
        config=payload.config
    )


@app.post("/memo/preview") # No longer needs ID in path
def get_ai_memo_preview(payload: schemas.AIGenerateRequest, db: Session = Depends(get_db)):
    formatted_content, memo_json = services.get_formatted_memo_content(
        db, payload.transcript_id, config=payload.config
    )

    if "error" in memo_json:
        raise HTTPException(500, memo_json["error"])

    return {"id": 0, "title": "AI Generated Preview", "content": formatted_content}


# ✨ --- 新增和修改的路由 ---
@app.post("/memos/ai-generate", response_model=schemas.Memo)
def generate_and_save_memo(payload: schemas.AIGenerateRequest, db: Session = Depends(get_db)):
    memo = services.create_memo_from_ai(
        db=db, transcript_id=payload.transcript_id, config=payload.config
    )
    if not memo:
        raise HTTPException(500, "Failed to save AI memo.")
    return memo

@app.post("/codes/ai-generate", response_model=schemas.CodeGenerationResponse) # Assume you create this simple response schema
def generate_and_save_ai_codes(payload: schemas.AIGenerateRequest, db: Session = Depends(get_db)):
    return services.generate_and_save_codes(
        db=db, transcript_id=payload.transcript_id, config=payload.config
    )

# --- Manual CRUD Routes ---
@app.post("/transcripts/upload", response_model=schemas.Transcript)
async def handle_transcript_upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    file_extension = Path(file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    permanent_file_path = UPLOAD_DIR / unique_filename
    try:
        with open(permanent_file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)
        return services.create_transcript_entry(db=db, title=file.filename, file_path=str(permanent_file_path))
    except Exception as e:
        if os.path.exists(permanent_file_path):
            os.remove(permanent_file_path)
        raise HTTPException(status_code=500, detail=f"Failed to upload and process transcript: {e}")


@app.post("/transcripts/process-ai/{transcript_id}")
def process_transcript_for_ai_endpoint(transcript_id: int, db: Session = Depends(get_db)):
    try:
        return services.process_transcript_for_ai(db=db, transcript_id=transcript_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/transcripts", response_model=List[schemas.Transcript])
def get_transcripts(db: Session = Depends(get_db)):
    return services.list_transcripts(db=db)

@app.post("/memos", response_model=schemas.Memo)
def create_manual_memo(memo: schemas.MemoCreate, db: Session = Depends(get_db)):
    return services.create_memo(db=db, title=memo.title, content=memo.content)


@app.get("/memos", response_model=List[schemas.Memo])
def get_memos(db: Session = Depends(get_db)):
    return services.list_memos(db=db)

@app.post("/codes", response_model=schemas.Code)
def create_manual_code(code: schemas.CodeCreate, db: Session = Depends(get_db)):
    try:
        return services.create_code(db=db, payload=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/codes", response_model=List[schemas.Code])
def get_codes(db: Session = Depends(get_db)):
    return services.list_codes(db=db)

@app.delete("/codes/{code_id}")
def remove_code(code_id: int, db: Session = Depends(get_db)):
    result = services.delete_code(db, code_id)
    if not result["deleted"]:
        raise HTTPException(status_code=404, detail="Code not found")
    return result

# ✨ 新增删除路由
@app.delete("/transcripts/{transcript_id}")
def remove_transcript(transcript_id: int, db: Session = Depends(get_db)):
    return services.delete_transcript(db, transcript_id)

@app.delete("/memos/{memo_id}")
def remove_memo(memo_id: int, db: Session = Depends(get_db)):
    return services.delete_memo(db, memo_id)

# ✨ --- NEW: Endpoints to get a single item ---

@app.get("/transcripts/{transcript_id}", response_model=schemas.TranscriptDetail)
def get_single_transcript(transcript_id: int, db: Session = Depends(get_db)):
    transcript = services.get_transcript_by_id(db=db, transcript_id=transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return transcript

@app.get("/memos/{memo_id}", response_model=schemas.MemoDetail)
def get_single_memo(memo_id: int, db: Session = Depends(get_db)):
    memo = services.get_memo_by_id(db=db, memo_id=memo_id)
    if not memo:
        raise HTTPException(status_code=404, detail="Memo not found")
    return memo

# ✨ --- NEW: Endpoint to provide default configs to the frontend ---
@app.get("/config/defaults", response_model=schemas.AIConfigDefaults)
def get_defaults():
    return services.get_default_config()


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)