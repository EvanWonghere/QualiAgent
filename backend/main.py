# backend/main.py
import tempfile

from backend import services
from backend.services import save_dataset_from_path, read_docx_from_path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
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


@app.post("/transcripts/upload")
async def handle_transcript_upload(file: UploadFile = File(...)):
    """
    澶勭悊 transcript 鏂囦欢涓婁紶鐨勮矾鐢便€�
    瀹冧細鑷姩浠庢枃浠跺悕涓彁鍙� title锛屽苟鏍规嵁鏂囦欢绫诲瀷 (.txt 鎴� .docx) 璇诲彇 content銆�
    """
    title = file.filename
    content_bytes = await file.read()
    content = ""

    try:
        if title.lower().endswith(".docx"):
            # 浣跨敤 services.py 涓凡鏈夌殑杈呭姪鍑芥暟鏉ヨ鍙� docx 瀛楄妭
            content = services.read_docx_bytes(content_bytes)
        else:
            # 榛樿鎸� utf-8 瑙ｇ爜
            content = content_bytes.decode("utf-8")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"鏂囦欢瑙ｆ瀽澶辫触: {e}")

    # 璋冪敤 service 鍑芥暟灏嗗唴瀹瑰瓨鍏ユ暟鎹簱
    return services.create_transcript(title=title, content=content)


@app.get("/transcripts")
def get_transcripts():
    return services.list_transcripts()

@app.get("/transcripts")
def get_transcripts():
    return services.list_transcripts()

@app.post("/memos")
def upload_memo(title: str, content: str):
    return services.create_memo(title, content)

@app.get("/memos")
def get_memos():
    return services.list_memos()


@app.post("/codes")
def create_code(code: str, excerpt: str, transcript_id: int = None, memo_id: int = None):
    try:
        return services.create_code(code, excerpt, transcript_id, memo_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/codes")
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