# backend/main.py
import tempfile
from backend.services import save_dataset_from_path, read_docx_from_path
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from backend.models import init_db
from backend.services import read_docx_bytes, save_dataset, search_similar, aggregate_codes
import uvicorn

from backend.services import generate_memo

init_db()
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/upload/")
async def upload_dataset(name: str = Form(...), file: UploadFile = File(...)):
    # write upload to a temp file on disk (avoid reading whole into memory)
    suffix = ".docx" if file.filename.lower().endswith(".docx") else ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
        temp_path = tf.name
        # read async in chunks and write
        while True:
            chunk = await file.read(1024 * 1024)  # 1 MB chunks
            if not chunk:
                break
            tf.write(chunk)

    # If docx: convert to plain text first (helper uses python-docx)
    if file.filename.lower().endswith(".docx"):
        # read_docx_from_path will return plain text from docx file path
        text_path = read_docx_from_path(temp_path)  # optional: you can have read_docx_from_path return a temp .txt path
        # The streaming saver will detect file path and process it
        ds_id = save_dataset_from_path(name, text_path)
    else:
        ds_id = save_dataset_from_path(name, temp_path)

    return {"dataset_id": ds_id}

@app.get("/datasets/")
def list_datasets():
    from backend.models import SessionLocal, Dataset
    db = SessionLocal()
    ds = db.query(Dataset).all()
    db.close()
    return [{"id": d.id, "name": d.name, "created_at": d.created_at.isoformat()} for d in ds]

@app.get("/search/")
def search(dataset_id: int, q: str, k: int = 5):
    return search_similar(dataset_id, q, top_k=k)

@app.post("/analyze/{dataset_id}")
def analyze(dataset_id: int):
    return aggregate_codes(dataset_id)


@app.post("/memo/{dataset_id}")
def memo(dataset_id: int):
    return generate_memo(dataset_id)


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
