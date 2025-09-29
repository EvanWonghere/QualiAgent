# backend/services.py
import os
import json
from dotenv import load_dotenv
from openai import OpenAI  # 缁熶竴瀵煎叆
import numpy as np
from sqlalchemy.orm import Session
from docx import Document
import tempfile

from backend.models import SessionLocal, Dataset, Chunk, Code, Transcript, Memo

# 鍔犺浇鐜鍙橀噺
load_dotenv()

# --- 1. 鍒濆鍖� OpenAI 瀹㈡埛绔� (杩欐槸姝ｇ‘鐨勭幇浠ｇ敤娉�) ---
# 纭繚浣犵殑 .env 鏂囦欢涓湁 OPENAI_API_KEY
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_API_BASE_URL")  # 濡傛灉浣跨敤浠ｇ悊锛屽垯淇濈暀姝ら」
)
EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
LLM_MODEL = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
CHUNK_TOKENS = int(os.getenv("CHUNK_TOKENS", 400))


def read_docx_bytes(file_bytes):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as f:
        f.write(file_bytes)
        path = f.name
    doc = Document(path)
    # 娓呯悊涓存椂鏂囦欢
    os.remove(path)
    return "\n".join(p.text for p in doc.paragraphs)


def normalize_text(s: str):
    return " ".join(s.strip().split())


def chunk_text(text, approx_tokens=CHUNK_TOKENS, overlap_ratio=0.1):
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
    # 浣犵殑 embedding 璋冪敤宸茬粡鏄渶鏂拌娉曪紝鏃犻渶淇敼
    resp = client.embeddings.create(
        model=EMBED_MODEL,
        input=text
    )
    return resp.data[0].embedding


def save_dataset(name: str, raw_text: str):
    db: Session = SessionLocal()
    ds = Dataset(name=name)
    db.add(ds)
    db.commit()
    db.refresh(ds)

    ds_id = ds.id

    chunks = chunk_text(raw_text)
    for start, end, chunk_text_ in chunks:
        emb = get_embedding(chunk_text_)
        c = Chunk(dataset_id=ds_id, text=chunk_text_, embedding=json.dumps(emb),
                  start_pos=start, end_pos=end)
        db.add(c)

    db.commit()
    db.close()
    return ds_id


def search_similar(dataset_id: int, query: str, top_k=5):
    db = SessionLocal()
    rows = db.query(Chunk).filter(Chunk.dataset_id == dataset_id).all()
    if not rows:
        return []
    q_emb = np.array(get_embedding(query), dtype=float)

    ids, texts, embs = [], [], []
    for r in rows:
        ids.append(r.id)
        texts.append(r.text)
        embs.append(np.array(json.loads(r.embedding), dtype=float))

    if not embs:
        return []

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


# --- 2. 鏇存柊 analyze_chunk_with_llm 鍑芥暟 ---
def analyze_chunk_with_llm(chunk_text: str):
    """浣跨敤 OpenAI v1.x.x SDK 鏇存柊浜嗘鍑芥暟"""
    system = "You are a qualitative research assistant. Produce a JSON object with keys: 'summary' (short), 'codes' (list of objects with 'code', 'definition', and 'quotes' list). Output JSON only."
    prompt = f"""Transcript chunk:
\"\"\"{chunk_text}\"\"\"
Please produce:
1) short summary (1-2 sentences)
2) list up to 5 codes. For each code give: 'code' (short label), 'definition' (one line), and 1-2 short quotes from the chunk that illustrate it.
Return JSON only. """

    try:
        # 浣跨敤 client.chat.completions.create 鏇夸唬鏃х殑 openai.ChatCompletion.create
        res = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            # --- 3. 娣诲姞 JSON 妯″紡浠ユ彁楂樺彲闈犳€� ---
            response_format={"type": "json_object"}
        )

        # 浣跨敤 res.choices[0].message.content 鏇夸唬瀛楀吀璁块棶
        content = res.choices[0].message.content
        return json.loads(content)

    except Exception as e:
        # 鏇村ソ鐨勯敊璇鐞嗭紝鍙互鎵撳嵃閿欒浠ヤ究璋冭瘯
        print(f"Error analyzing chunk with LLM: {e}")
        return {"error": str(e)}


def aggregate_codes(dataset_id: int, top_n=30):
    db = SessionLocal()
    chunks = db.query(Chunk).filter(Chunk.dataset_id == dataset_id).all()
    code_counts = {}
    for c in chunks:
        out = analyze_chunk_with_llm(c.text)
        # 妫€鏌ユ槸鍚︽湁閿欒锛屾垨杈撳嚭鏄惁涓哄瓧鍏�
        if not isinstance(out, dict): continue

        codes = out.get("codes", [])
        for cd in codes:
            label = cd.get("code")
            if not label: continue
            code_counts[label] = code_counts.get(label, 0) + 1

    items = sorted(code_counts.items(), key=lambda x: x[1], reverse=True)[:top_n]
    db.close()
    return [{"code": k, "count": v} for k, v in items]


# ----------------------------------------------------
# 浠ヤ笅鏄綘鎻愪緵鐨勯澶栧嚱鏁帮紝瀹冧滑鏈韩涓嶉渶瑕佷慨鏀�
# ----------------------------------------------------

def stream_chunks_from_file(path, approx_tokens=CHUNK_TOKENS, overlap_ratio=0.1):
    avg_char_per_token = 4
    chunk_size = approx_tokens * avg_char_per_token
    overlap = int(chunk_size * overlap_ratio)

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        buffer = ""
        pos = 0
        while True:
            data = f.read(chunk_size)
            if not data:
                if buffer.strip():
                    start = pos
                    end = pos + len(buffer)
                    yield start, end, normalize_text(buffer)
                break
            buffer += data
            chunk = buffer[:chunk_size]
            start = pos
            end = pos + len(chunk)
            yield start, end, normalize_text(chunk)
            buffer = buffer[chunk_size - overlap:]
            pos = end - overlap


def save_dataset_from_path(name: str, file_path: str, batch_commit=16):
    db = SessionLocal()

    base = name
    i = 1
    while db.query(Dataset).filter_by(name=name).first() is not None:
        name = f"{base}-{i}"
        i += 1

    ds = Dataset(name=name)
    db.add(ds)
    db.commit()
    db.refresh(ds)

    ds_id = ds.id

    counter = 0
    for start, end, txt in stream_chunks_from_file(file_path):
        emb = get_embedding(txt)
        c = Chunk(dataset_id=ds.id, text=txt, embedding=json.dumps(emb),
                  start_pos=start, end_pos=end)
        db.add(c)
        counter += 1
        if counter % batch_commit == 0:
            db.commit()
    db.commit()
    db.close()
    return ds_id


def read_docx_from_path(path):
    doc = Document(path)
    text = "\n".join(p.text for p in doc.paragraphs)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
    tmp.write(text)
    tmp.close()
    return tmp.name


def generate_memo(dataset_id: int):
    """
    鏍规嵁鏁版嵁闆嗕腑鐨勬枃鏈潡鏍锋湰鐢熸垚涓€浠藉垎鏋愬蹇樺綍 (analytic memo)銆�
    """
    db = SessionLocal()
    # 鍙栨牱鍓� 15 涓枃鏈潡浠ユ帶鍒舵垚鏈拰閫熷害
    chunks = db.query(Chunk).filter(Chunk.dataset_id == dataset_id).limit(15).all()
    texts = [c.text for c in chunks]
    db.close()

    if not texts:
        return {"summary": "娌℃湁瓒冲鐨勬暟鎹潵鐢熸垚澶囧繕褰曘€�", "contradictions": [], "followups": []}

    # 灏嗘枃鏈潡鎷兼帴鎴愪竴涓繛璐殑鏍锋湰
    full_text_sample = "\n---\n".join(texts)

    system_prompt = "You are a qualitative research analyst. Your task is to write an analytic memo based on interview excerpts. Your output must be a valid JSON object."

    user_prompt = f"""Based on the following excerpts from an interview dataset:

---
{full_text_sample}
---

Write an analytic memo with three sections. The output must be a JSON object with the keys "summary", "contradictions", and "followups".
1.  **summary**: A 2-3 paragraph analysis of the main patterns and themes.
2.  **contradictions**: An array of strings, listing 3 points where the data shows tensions or unexpected insights.
3.  **followups**: An array of strings, listing 3-5 follow-up interview questions to probe further."""

    try:
        res = client.chat.completions.create(
            model=LLM_MODEL,  # 浣跨敤鍦ㄦ枃浠堕《閮ㄥ畾涔夌殑妯″瀷鍙橀噺
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            # 鉁� 寮哄埗浣跨敤 JSON 杈撳嚭妯″紡
            response_format={"type": "json_object"}
        )
        # 鉁� 閫氳繃瀵硅薄灞炴€ц闂粨鏋�
        content = res.choices[0].message.content
        return json.loads(content)

    except Exception as e:
        print(f"鉂� 鐢熸垚澶囧繕褰曟椂鍑洪敊: {e}")
        return {"error": "璋冪敤 API 鐢熸垚澶囧繕褰曞け璐ャ€�"}


# Transcripts
def create_transcript(title: str, content: str):
    db = SessionLocal()
    transcript = Transcript(title=title, content=content)
    db.add(transcript)
    db.commit()
    db.refresh(transcript)
    db.close()
    return transcript

def list_transcripts():
    db = SessionLocal()
    transcripts = db.query(Transcript).all()
    db.close()
    return transcripts

# Memos
def create_memo(title: str, content: str):
    db = SessionLocal()
    memo = Memo(title=title, content=content)
    db.add(memo)
    db.commit()
    db.refresh(memo)
    db.close()
    return memo

def list_memos():
    db = SessionLocal()
    memos = db.query(Memo).all()
    db.close()
    return memos


def create_code(code: str, excerpt: str, transcript_id: int = None, memo_id: int = None):
    db = SessionLocal()

    if not transcript_id and not memo_id:
        db.close()
        raise ValueError("Code must reference either a transcript or a memo")

    new_code = Code(code=code, excerpt=excerpt,
                    transcript_id=transcript_id, memo_id=memo_id)
    db.add(new_code)
    db.commit()
    db.refresh(new_code)
    db.close()
    return new_code

def list_codes():
    db = SessionLocal()
    codes = db.query(Code).all()
    results = []
    for c in codes:
        results.append({
            "id": c.id,
            "code": c.code,
            "excerpt": c.excerpt,
            "source": c.transcript.title if c.transcript else c.memo.title,
            "created_at": c.created_at
        })
    db.close()
    return results

def delete_code(code_id: int):
    db = SessionLocal()
    code = db.query(Code).filter(Code.id == code_id).first()
    if code:
        db.delete(code)
        db.commit()
        db.close()
        return {"deleted": True}
    db.close()
    return {"deleted": False}

