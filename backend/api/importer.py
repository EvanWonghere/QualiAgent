# backend/api/importer.py
import shutil
import uuid
import re
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile, File, Form, Depends
from sqlalchemy.orm import Session

from backend.db import SessionLocal
from backend.models import Transcript, Segment

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def robust_line_scan(text: str, split_mode: str = 'default', custom_pattern: str = None) -> list[dict]:
    """
    【逐行扫描法 - 终极抗干扰版】
    能抵抗：中文括号、英文括号、时间戳冒号干扰
    """
    if not text: return []

    # 1. 确定正则
    regex_pattern = None
    if split_mode == 'custom' and custom_pattern:
        regex_pattern = custom_pattern
    elif split_mode == 'speaker_time' or split_mode == 'speaker_simple':
        # ✨ 终极正则解释：
        # ^                   匹配行首
        # (?:                 非捕获组（开始循环匹配字符）
        #   [^:：\n\(\)（）]    1. 不是冒号、换行、且不是任何括号的普通字符
        #   |                 或者
        #   \([^)\n]*\)       2. 英文括号 (...)，里面可以包含冒号
        #   |                 或者
        #   \（[^）\n]*\）      3. 中文括号 （...），里面也可以包含冒号
        # )+                  重复一次或多次（组成名字+时间戳）
        # [:：]               最后以中文或英文冒号结尾
        regex_pattern = r'^(?:[^:：\n\(\)（）]|\([^)\n]*\)|\（[^）\n]*\）)+[:：]'

    # 默认模式退化处理
    if not regex_pattern or split_mode == 'default':
        raw_list = [s.strip() for s in re.split(r'(?<=[.!?。！？\n])\s+', text) if len(s.strip()) > 1]
        return [{"speaker": None, "text": t} for t in raw_list]

    # 2. 逐行扫描
    lines = text.split('\n')
    segments = []

    current_speaker = None
    current_text_buffer = []

    compiled_re = re.compile(regex_pattern)

    for line in lines:
        line = line.strip()
        if not line: continue

        match = compiled_re.match(line)

        if match:
            # === 发现新说话人 ===
            if current_text_buffer:
                full_text = "\n".join(current_text_buffer)
                segments.append({
                    "speaker": current_speaker,
                    "text": full_text
                })

            raw_header = match.group(0)
            # 去掉末尾冒号
            current_speaker = re.sub(r'[:：]$', '', raw_header).strip()

            # 提取内容
            content_part = line[len(raw_header):].strip()
            current_text_buffer = [content_part] if content_part else []

        else:
            # === 延续 ===
            if current_text_buffer is not None:
                current_text_buffer.append(line)
            else:
                current_text_buffer = [line]

    if current_text_buffer:
        full_text = "\n".join(current_text_buffer)
        segments.append({
            "speaker": current_speaker,
            "text": full_text
        })

    print(f"✅ Line-Scan Split: Got {len(segments)} segments.")
    return segments


@router.post("/upload")
async def upload_file(
        file: UploadFile = File(...),
        split_pattern: str = Form(None),
        split_mode: str = Form('speaker_simple'),
        db: Session = Depends(get_db)
):
    # 1. 保存文件
    upload_dir = Path("uploads")
    upload_dir.mkdir(exist_ok=True)
    file_id = f"t_{uuid.uuid4().hex[:8]}"
    file_path = upload_dir / f"{file_id}_{file.filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 2. 读取文本
    content = ""
    try:
        if file.filename.endswith(".docx"):
            import docx
            doc = docx.Document(file_path)
            content = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
    except Exception as e:
        content = "(Error reading file content)"

    # 3. 创建 Transcript
    new_transcript = Transcript(
        id=file_id,
        title=file.filename,
        content=content,
        created_at=datetime.now(timezone.utc),
        status="ready"
    )
    db.add(new_transcript)

    # 4. 执行切分
    final_segments = robust_line_scan(content, split_mode, split_pattern)

    new_segments = []
    for idx, seg_data in enumerate(final_segments):
        new_segments.append(Segment(
            id=f"seg_{uuid.uuid4().hex[:8]}",
            transcript_id=file_id,
            sentence_index=idx,
            text=seg_data["text"],
            speaker=seg_data["speaker"],
            start_offset=0,
            end_offset=0
        ))

    if new_segments:
        db.add_all(new_segments)

    db.commit()

    return {
        "id": file_id,
        "filename": file.filename,
        "segments_count": len(new_segments),
        "split_mode": split_mode
    }