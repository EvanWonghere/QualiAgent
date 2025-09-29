# backend/services.py
import os
import json
from dotenv import load_dotenv
from openai import OpenAI
import numpy as np
from sqlalchemy.orm import Session
from docx import Document
import tempfile
from backend.models import SessionLocal, Dataset, Chunk, Code, Transcript, Memo

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_API_BASE_URL")
)
EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
LLM_MODEL = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
CHUNK_TOKENS = int(os.getenv("CHUNK_TOKENS", 400))


# --- Dataset and AI Analysis Services ---
def read_docx_bytes(file_bytes):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as f:
        f.write(file_bytes)
        path = f.name
    doc = Document(path)
    os.remove(path)
    return "\n".join(p.text for p in doc.paragraphs)


def normalize_text(s: str):
    return " ".join(s.strip().split())


def chunk_text(text, approx_tokens=CHUNK_TOKENS, overlap_ratio=0.1):
    # (此函数内容未变)
    avg_char_per_token = 4
    chunk_size = approx_tokens * avg_char_per_token
    overlap = int(chunk_size * overlap_ratio)
    chunks = []
    i = 0
    n = len(text)
    while i < n:
        end = min(n, i + chunk_size)
        chunk = text[i:end]
        chunks.append((i, end, normalize_text(chunk)))
        i = end - overlap
    return chunks


def get_embedding(text: str):
    resp = client.embeddings.create(model=EMBED_MODEL, input=text)
    return resp.data[0].embedding


def save_dataset(name: str, raw_text: str):
    # (此函数内容未变)
    db: Session = SessionLocal()
    ds = Dataset(name=name)
    db.add(ds)
    db.commit()
    db.refresh(ds)
    ds_id = ds.id
    chunks = chunk_text(raw_text)
    for start, end, chunk_text_ in chunks:
        emb = get_embedding(chunk_text_)
        c = Chunk(dataset_id=ds_id, text=chunk_text_, embedding=json.dumps(emb), start_pos=start, end_pos=end)
        db.add(c)
    db.commit()
    db.close()

    return ds_id


def save_dataset_from_path(name: str, file_path: str):
    """
    ✅ Creates a Dataset by reading from a file path in a memory-safe way.
    It streams the file content, creates chunks, gets embeddings, and saves them.
    Finally, it cleans up the temporary file(s).
    """
    db = SessionLocal()
    text_path_to_process = file_path
    is_converted_temp = False

    try:
        # Ensure unique dataset name
        base_name = name
        i = 1
        while db.query(Dataset).filter_by(name=name).first() is not None:
            name = f"{base_name}-{i}"
            i += 1

        ds = Dataset(name=name)
        db.add(ds)
        db.commit()
        db.refresh(ds)
        ds_id = ds.id

        # If the original file is a docx, convert it to a temporary text file first
        if file_path.lower().endswith(".docx"):
            text_path_to_process = read_docx_from_path(file_path)
            is_converted_temp = True

        # Stream chunks from the text file path, generate embeddings, and save
        counter = 0
        batch_commit = 16
        for start, end, txt in stream_chunks_from_file(text_path_to_process):
            emb = get_embedding(txt)
            c = Chunk(dataset_id=ds_id, text=txt, embedding=json.dumps(emb),
                      start_pos=start, end_pos=end)
            db.add(c)
            counter += 1
            if counter % batch_commit == 0:
                db.commit()  # Commit in batches to manage memory

        db.commit()  # Final commit for any remaining chunks
        return ds_id

    finally:
        # --- Crucial Cleanup Step ---
        # Delete the original temp file uploaded by FastAPI
        if os.path.exists(file_path):
            os.remove(file_path)
        # If a .docx was converted to a .txt, delete that temp file as well
        if is_converted_temp and os.path.exists(text_path_to_process):
            os.remove(text_path_to_process)
        db.close()


def stream_chunks_from_file(path, approx_tokens=CHUNK_TOKENS, overlap_ratio=0.1):
    """
    Reads a large text file from a path and yields its content in smaller,
    overlapping chunks without loading the whole file into memory.
    """
    avg_char_per_token = 4
    chunk_size = approx_tokens * avg_char_per_token
    overlap = int(chunk_size * overlap_ratio)

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        buffer = ""
        pos = 0
        while True:
            data = f.read(chunk_size)
            if not data:
                # emit remaining buffer if any
                if buffer.strip():
                    start = pos
                    end = pos + len(buffer)
                    yield start, end, normalize_text(buffer)
                break
            buffer += data
            # emit a chunk
            chunk = buffer[:chunk_size]
            start = pos
            end = pos + len(chunk)
            yield start, end, normalize_text(chunk)
            # Prepare buffer for next round with overlap
            buffer = buffer[chunk_size - overlap:]
            pos = end - overlap


def search_similar(dataset_id: int, query: str, top_k=5):
    # (此函数内容未变)
    db = SessionLocal()
    rows = db.query(Chunk).filter(Chunk.dataset_id == dataset_id).all()
    if not rows: return []
    q_emb = np.array(get_embedding(query), dtype=float)
    ids, texts, embs = [], [], []
    for r in rows:
        ids.append(r.id);
        texts.append(r.text);
        embs.append(np.array(json.loads(r.embedding), dtype=float))
    if not embs: return []
    embs = np.vstack(embs)

    def cos_sim(a, B):
        a_norm = a / np.linalg.norm(a)
        B_norm = B / np.linalg.norm(B, axis=1, keepdims=True)
        return B_norm @ a_norm

    sims = cos_sim(q_emb, embs)
    top_idx = np.argsort(sims)[-top_k:][::-1]
    results = [{"chunk_id": ids[i], "text": texts[i], "score": float(sims[i])} for i in top_idx]
    db.close()
    return results


def analyze_chunk_with_llm(chunk_text: str):
    # (此函数内容未变)
    system = "You are a qualitative research assistant. Produce a JSON object with keys: 'summary' (short), 'codes' (list of objects with 'code', 'definition', and 'quotes' list). Output JSON only."
    prompt = f"Transcript chunk:\n\"\"\"{chunk_text}\"\"\"\nPlease produce:\n1) short summary (1-2 sentences)\n2) list up to 5 codes. For each code give: 'code' (short label), 'definition' (one line), and 1-2 short quotes from the chunk that illustrate it.\nReturn JSON only. "
    try:
        res = client.chat.completions.create(model=LLM_MODEL, messages=[{"role": "system", "content": system},
                                                                        {"role": "user", "content": prompt}],
                                             temperature=0.0, response_format={"type": "json_object"})
        content = res.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"Error analyzing chunk with LLM: {e}");
        return {"error": str(e)}


def aggregate_codes(dataset_id: int, top_n=30):
    # (此函数内容未变)
    db = SessionLocal()
    chunks = db.query(Chunk).filter(Chunk.dataset_id == dataset_id).all()
    code_counts = {}
    for c in chunks:
        out = analyze_chunk_with_llm(c.text)
        if not isinstance(out, dict): continue
        codes = out.get("codes", [])
        for cd in codes:
            label = cd.get("code")
            if not label: continue
            code_counts[label] = code_counts.get(label, 0) + 1
    items = sorted(code_counts.items(), key=lambda x: x[1], reverse=True)[:top_n]
    db.close()
    return [{"code": k, "count": v} for k, v in items]


def generate_memo(dataset_id: int):
    # (此函数内容未变)
    db = SessionLocal()
    chunks = db.query(Chunk).filter(Chunk.dataset_id == dataset_id).limit(15).all()
    texts = [c.text for c in chunks]
    db.close()
    if not texts: return {"summary": "No data to generate memo.", "contradictions": [], "followups": []}
    full_text_sample = "\n---\n".join(texts)
    system_prompt = "You are a qualitative research analyst. Your task is to write an analytic memo based on interview excerpts. Your output must be a valid JSON object."
    user_prompt = f"Based on the following excerpts...\n---\n{full_text_sample}\n---\nWrite an analytic memo with three sections... JSON object with the keys 'summary', 'contradictions', and 'followups'..."
    try:
        res = client.chat.completions.create(model=LLM_MODEL, messages=[{"role": "system", "content": system_prompt},
                                                                        {"role": "user", "content": user_prompt}],
                                             temperature=0.7, response_format={"type": "json_object"})
        content = res.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"Error generating memo: {e}");
        return {"error": "API call to generate memo failed."}


# ✨ --- File-based Transcript Creation (Memory Safe) ---
def create_transcript_from_path(file_path: str):
    """
    ✅ Reads a file from a given path, creates a transcript, and cleans up the file.
    This is memory-safe as it operates on files on disk.
    """
    title = os.path.basename(file_path)
    content = ""

    try:
        if title.lower().endswith(".docx"):
            # read_docx_from_path converts docx to a new temp .txt file and returns its path
            text_file_path = read_docx_from_path(file_path)
            with open(text_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            os.remove(text_file_path)  # Clean up the converted .txt file
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
    finally:
        # Ensure the original uploaded temp file is always deleted
        if os.path.exists(file_path):
            os.remove(file_path)

    db = SessionLocal()
    # Check if a transcript with this title already exists to avoid unique constraint errors
    existing_transcript = db.query(Transcript).filter(Transcript.title == title).first()
    if existing_transcript:
        db.close()
        # You can decide how to handle this: error, rename, or update.
        # For now, we'll just return the existing one.
        return existing_transcript

    transcript = Transcript(title=title, content=content)
    db.add(transcript)
    db.commit()
    db.refresh(transcript)
    db.close()
    return transcript


def read_docx_from_path(path):
    # (This function is unchanged)
    doc = Document(path)
    text = "\n".join(p.text for p in doc.paragraphs)
    # Create a new temp file for the text content
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8") as tmp:
        tmp.write(text)
    return tmp.name

# ✨ --- 新增和修改的函数 ---

def create_memo_from_ai(dataset_id: int):
    """ ✨ 调用AI生成Memo，并将其保存到数据库 """
    db = SessionLocal()
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        db.close()
        return None

    memo_json = generate_memo(dataset_id)
    if "error" in memo_json:
        db.close()
        return None  # Or return the error

    # 将JSON中的各个部分组合成一个完整的content字符串
    summary = memo_json.get("summary", "N/A")
    contradictions = "\n".join(f"- {c}" for c in memo_json.get("contradictions", []))
    followups = "\n".join(f"- {q}" for q in memo_json.get("followups", []))

    full_content = f"## Summary\n{summary}\n\n## Contradictions or Surprises\n{contradictions}\n\n## Follow-up Questions\n{followups}"

    new_memo = Memo(
        title=f"AI Memo for Dataset: '{dataset.name}'",
        content=full_content
    )
    db.add(new_memo)
    db.commit()
    db.refresh(new_memo)
    db.close()
    return new_memo


def generate_and_save_codes(dataset_id: int):
    """ ✨ 分析数据集的每个chunk，并将AI生成的codes保存到数据库 """
    db = SessionLocal()
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        db.close()
        return {"error": "Dataset not found"}

    chunks = db.query(Chunk).filter(Chunk.dataset_id == dataset_id).all()
    saved_codes_count = 0
    for chunk in chunks:
        analysis = analyze_chunk_with_llm(chunk.text)
        if "codes" in analysis and isinstance(analysis["codes"], list):
            for code_data in analysis["codes"]:
                # AI返回的quotes是一个列表，我们将其合并
                excerpt = "\n".join(code_data.get("quotes", []))
                if not excerpt:  # 如果没有引文，使用部分chunk文本
                    excerpt = chunk.text[:250] + "..."

                new_code = Code(
                    code=code_data.get("code", "Untitled"),
                    excerpt=excerpt,
                    dataset_id=dataset_id  # 关联到Dataset
                )
                db.add(new_code)
                saved_codes_count += 1

    db.commit()
    db.close()
    return {"message": f"Successfully generated and saved {saved_codes_count} codes."}


# --- Manual CRUD Services ---

def create_transcript(title: str, content: str):
    db = SessionLocal()
    transcript = Transcript(title=title, content=content)
    db.add(transcript);
    db.commit();
    db.refresh(transcript);
    db.close()
    return transcript


def list_transcripts():
    db = SessionLocal()
    transcripts = db.query(Transcript).all()
    db.close()
    return transcripts


def create_memo(title: str, content: str):
    db = SessionLocal()
    memo = Memo(title=title, content=content)
    db.add(memo);
    db.commit();
    db.refresh(memo);
    db.close()
    return memo


def list_memos():
    db = SessionLocal()
    memos = db.query(Memo).all()
    db.close()
    return memos


def create_code(payload):
    db = SessionLocal()
    new_code = Code(**payload.dict())
    if not new_code.transcript_id and not new_code.memo_id and not new_code.dataset_id:
        raise ValueError("Code must reference a transcript, a memo, or a dataset")
    db.add(new_code);
    db.commit();
    db.refresh(new_code);
    db.close()
    return new_code


def list_codes():
    """ ✨ 更新以正确显示所有来源 """
    db = SessionLocal()
    codes = db.query(Code).all()
    results = []
    for c in codes:
        source_title = "N/A"
        if c.transcript:
            source_title = f"Transcript: {c.transcript.title}"
        elif c.memo:
            source_title = f"Memo: {c.memo.title}"
        elif c.dataset:
            source_title = f"AI Analysis of Dataset: {c.dataset.name}"

        results.append({
            "id": c.id, "code": c.code, "excerpt": c.excerpt, "source": source_title,
            "created_at": c.created_at, "transcript_id": c.transcript_id,
            "memo_id": c.memo_id, "dataset_id": c.dataset_id
        })
    db.close()
    return results


def delete_code(code_id: int):
    db = SessionLocal()
    code = db.query(Code).filter(Code.id == code_id).first()
    if code:
        db.delete(code);
        db.commit();
        db.close()
        return {"deleted": True}
    db.close()
    return {"deleted": False}