# backend/importers/docx_importer.py
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Dict, Any, List, Tuple
from docx import Document
from backend.contracts.models import Segment, Event, CodebookItem, EventLabel

LABEL_PATTERNS = [
    re.compile(r"\((?P<label>[^():（）]{1,40})\s*[:：]\s*(?P<summary>[^()（）]{1,200})\)"),
    re.compile(r"（(?P<label>[^():（）]{1,40})\s*[:：]\s*(?P<summary>[^()（）]{1,200})）"),
]
SPEAKER_PREFIXES = [
    "受访者：", "访谈者：", "主持人：", "学生：", "老师：", "被访者：", "来访者：", "咨询师："
]

def _uuid(prefix: str) -> str:
    return f"{prefix}.{uuid.uuid4().hex[:12]}"

def _detect_speaker(text: str) -> Tuple[str | None, str]:
    for pre in SPEAKER_PREFIXES:
        if text.startswith(pre):
            return pre[:-1], text[len(pre):].strip()
    return None, text

def parse_docx(path: Path, transcript_id: str) -> Dict[str, List[Dict[str, Any]]]:
    doc = Document(str(path))
    segments: List[Segment] = []
    events: List[Event] = []
    codebook: Dict[str, CodebookItem] = {}  # keyed by normalized label
    labels: List[EventLabel] = []

    created_at = datetime.now(timezone.utc)
    for p_idx, p in enumerate(doc.paragraphs):
        raw = p.text.strip()
        if not raw:
            continue
        speaker, text_wo_speaker = _detect_speaker(raw)

        seg = Segment(
            id=_uuid("s"),
            transcript_id=transcript_id,
            index=p_idx,
            speaker=speaker,
            text=text_wo_speaker,
            start_char=None,
            end_char=None,
        )
        # store paragraph index in importer output; DB column is added by migration 0002
        seg_dict = seg.model_dump()
        seg_dict["paragraph_index"] = p_idx
        segments.append(Segment(**seg_dict))

        # extract inline codes
        matches = []
        for pat in LABEL_PATTERNS:
            matches.extend(pat.finditer(text_wo_speaker))
        for m in matches:
            label = m.group("label").strip()
            summary = m.group("summary").strip()
            norm = label.lower().strip()

            # upsert codebook item
            if norm not in codebook:
                codebook[norm] = CodebookItem(
                    id=_uuid("cb"),
                    name=label,
                    display_name=None,
                    definition=f"(auto-import) Derived from transcript {transcript_id}",
                    parent_id=None,
                    status="active",
                    created_at=created_at,
                )

            # create event
            ev = Event(
                id=_uuid("e"),
                transcript_id=transcript_id,
                segment_id=seg.id,
                start_char=None, end_char=None,
                summary=summary,
                created_by="human",
                status="accepted",
                confidence=None,
                created_at=created_at,
            )
            ev_dict = ev.model_dump()
            ev_dict["event_kind"] = label      # denormalized convenience
            ev_dict["raw_excerpt"] = summary   # store raw summary as excerpt
            events.append(Event(**ev_dict))

            # link event→code
            labels.append(EventLabel(
                id=_uuid("l"),
                event_id=ev.id,
                codebook_id=codebook[norm].id,
                created_by="human",
                rationale=None,
                created_at=created_at,
            ))
    return {
        "segments": [s.model_dump() for s in segments],
        "events":   [e.model_dump() for e in events],
        "codebook": [c.model_dump() for c in codebook.values()],
        "labels":   [l.model_dump() for l in labels],
    }
