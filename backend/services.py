# backend/services.py
import os
import json
from dotenv import load_dotenv
from openai import OpenAI  # 统一导入
import numpy as np
from sqlalchemy.orm import Session
from docx import Document
import tempfile

from backend.models import SessionLocal, Dataset, Chunk

# 加载环境变量
load_dotenv()

# --- 1. 初始化 OpenAI 客户端 (这是正确的现代用法) ---
# 确保你的 .env 文件中有 OPENAI_API_KEY
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_API_BASE_URL")  # 如果使用代理，则保留此项
)
EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
LLM_MODEL = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
CHUNK_TOKENS = int(os.getenv("CHUNK_TOKENS", 400))


def read_docx_bytes(file_bytes):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as f:
        f.write(file_bytes)
        path = f.name
    doc = Document(path)
    # 清理临时文件
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
    # 你的 embedding 调用已经是最新语法，无需修改
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


# --- 2. 更新 analyze_chunk_with_llm 函数 ---
def analyze_chunk_with_llm(chunk_text: str):
    """使用 OpenAI v1.x.x SDK 更新了此函数"""
    system = "You are a qualitative research assistant. Produce a JSON object with keys: 'summary' (short), 'codes' (list of objects with 'code', 'definition', and 'quotes' list). Output JSON only."
    prompt = f"""Transcript chunk:
\"\"\"{chunk_text}\"\"\"
Please produce:
1) short summary (1-2 sentences)
2) list up to 5 codes. For each code give: 'code' (short label), 'definition' (one line), and 1-2 short quotes from the chunk that illustrate it.
Return JSON only. """

    try:
        # 使用 client.chat.completions.create 替代旧的 openai.ChatCompletion.create
        res = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            # --- 3. 添加 JSON 模式以提高可靠性 ---
            response_format={"type": "json_object"}
        )

        # 使用 res.choices[0].message.content 替代字典访问
        content = res.choices[0].message.content
        return json.loads(content)

    except Exception as e:
        # 更好的错误处理，可以打印错误以便调试
        print(f"Error analyzing chunk with LLM: {e}")
        return {"error": str(e)}


def aggregate_codes(dataset_id: int, top_n=30):
    db = SessionLocal()
    chunks = db.query(Chunk).filter(Chunk.dataset_id == dataset_id).all()
    code_counts = {}
    for c in chunks:
        out = analyze_chunk_with_llm(c.text)
        # 检查是否有错误，或输出是否为字典
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
# 以下是你提供的额外函数，它们本身不需要修改
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
    根据数据集中的文本块样本生成一份分析备忘录 (analytic memo)。
    """
    db = SessionLocal()
    # 取样前 15 个文本块以控制成本和速度
    chunks = db.query(Chunk).filter(Chunk.dataset_id == dataset_id).limit(15).all()
    texts = [c.text for c in chunks]
    db.close()

    if not texts:
        return {"summary": "没有足够的数据来生成备忘录。", "contradictions": [], "followups": []}

    # 将文本块拼接成一个连贯的样本
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
            model=LLM_MODEL,  # 使用在文件顶部定义的模型变量
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            # ✅ 强制使用 JSON 输出模式
            response_format={"type": "json_object"}
        )
        # ✅ 通过对象属性访问结果
        content = res.choices[0].message.content
        return json.loads(content)

    except Exception as e:
        print(f"❌ 生成备忘录时出错: {e}")
        return {"error": "调用 API 生成备忘录失败。"}

