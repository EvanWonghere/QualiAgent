# backend/api/ai.py
from __future__ import annotations

import os
import json
import uuid
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc
from dotenv import load_dotenv

from backend.db import SessionLocal
from backend.models import Transcript, Segment, Event, EventLabel, Codebook, CodebookLibrary

load_dotenv()
router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _uuid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class SynthesisOut(BaseModel):
    themes: List[Dict]


# =============================================================================
# 1. Prompt Strategies: Three Agents Architecture
# =============================================================================

SYS_PROMPT = "You are an expert Qualitative Researcher. Return ONLY strict JSON."

# --- Agent 1: The Matcher ---
AGENT_MATCHER_TEMPLATE = """
=== EXISTING CODEBOOK ===
{codebook_json}

=== SEGMENTS TO ANALYZE ===
{segments_json}

=== MISSION ===
1. **Strategy**: {density_instruction}
2. **Matching**: 
   - Check "EXISTING CODEBOOK" for matches (>80% similarity).
   - If match found: Use existing `code_name`.
   - If meaningful but NO match: Set `code_name` to "NEED_NEW_CODE".
   - If noise: Ignore.

=== OUTPUT FORMAT ===
{{
  "matches": [
    {{ "id": "seg_xxx", "summary": "Raw extraction", "code_name": "Existing Code OR NEED_NEW_CODE" }}
  ]
}}
"""

# --- Agent 2: The Creator ---
AGENT_CREATOR_TEMPLATE = """
=== UNCODED ITEMS ===
{uncoded_json}

=== INSTRUCTIONS ===
Generate NEW codes for these items.
1. **Naming**: Concise, academic Noun Phrase.
2. **Language**: Same as the text content.

=== OUTPUT FORMAT ===
{{
  "new_codes": [
    {{ "id": "seg_xxx", "summary": "Raw extraction", "code_name": "New Code Name" }}
  ]
}}
"""

# --- Agent 3: The Refiner (极简电报体版) ---
AGENT_REFINER_TEMPLATE = """
=== DRAFT CODING RESULTS ===
{draft_json}

=== MISSION: QUALITY CONTROL & REFINEMENT ===
You are the final editor. Polish the results following these STRICT rules:

1. **LANGUAGE MIRRORING**: 
   - Identify the source language.
   - Output `summary` and `code_name` MUST be in the **EXACT SAME LANGUAGE**.
   - (e.g., If Chinese text -> Chinese summary & code).

2. **SUMMARY STYLE: TELEGRAPHIC & SUBJECT-LESS**:
   - **OMIT THE SUBJECT**: Do NOT use "The participant", "The respondent", "He", "She", or "受访者", "访谈对象".
   - **Start with Verb/Noun**: Go straight to the point.
   - **Concise**: Remove unnecessary filler words.
   - **Example (English)**: 
     - Bad: "The participant feels happy about the job." 
     - Good: "Satisfaction with current job role."
   - **Example (Chinese)**: 
     - Bad: "受访者表示对工资不满意。"
     - Good: "对现有薪资水平的不满。"

3. **FORMATTING**:
   - Keep `id` exactly the same.

=== OUTPUT FORMAT ===
{{
  "refined_results": [
    {{ "id": "seg_xxx", "summary": "Concise, subject-less summary", "code_name": "Polished Code" }}
  ]
}}
"""


def get_density_instruction(density: str) -> str:
    if density == "dense":
        return "Strategy: **DENSE**. Split segment into distinct thoughts. Output multiple items per segment ID if needed."
    elif density == "broad":
        return "Strategy: **BROAD**. Summarize the whole segment into ONE main theme."
    else:
        return "Strategy: **BALANCED**. Extract key insights."


# =============================================================================
# 2. Logic: The 3-Step Agentic Workflow
# =============================================================================

def run_batch_ai_logic(transcript_id: str, library_id: str, target_speaker: Optional[str] = None,
                       density: str = "balanced"):
    print(f"🚀 [AI Start] {transcript_id} | Lib: {library_id} | {density}")
    db = SessionLocal()
    try:
        t = db.query(Transcript).filter(Transcript.id == transcript_id).first()
        if not t: return
        t.status = "processing"

        # 1. Clear old pending events
        events_to_delete = db.query(Event.id).filter(
            Event.transcript_id == transcript_id,
            Event.status == 'proposed'
        ).all()
        event_ids = [e.id for e in events_to_delete]

        if event_ids:
            print(f"🧹 Clearing {len(event_ids)} old pending events...")
            db.query(EventLabel).filter(EventLabel.event_id.in_(event_ids)).delete(synchronize_session=False)
            db.query(Event).filter(Event.id.in_(event_ids)).delete(synchronize_session=False)
            db.commit()

        # 2. Fallback Segmentation
        if db.query(Segment).filter(Segment.transcript_id == transcript_id).count() == 0 and t.content:
            raw = re.split(r'(?<=[.!?\n])\s+', t.content)
            db.add_all([Segment(id=_uuid("seg"), transcript_id=transcript_id, sentence_index=i, text=s.strip(),
                                speaker="Unknown", start_offset=0, end_offset=0) for i, s in enumerate(raw) if
                        len(s.strip()) > 1])
            db.commit()

        # 3. Filter Candidates
        existing_ids = db.query(Event.segment_id).filter(Event.transcript_id == transcript_id,
                                                         Event.status.in_(['accepted', 'proposed']))
        candidates = db.query(Segment).filter(Segment.transcript_id == transcript_id,
                                              Segment.id.not_in(existing_ids)).all()

        target_segments = []
        if target_speaker:
            ts_lower = target_speaker.lower()
            target_segments = [s for s in candidates if s.speaker and ts_lower in s.speaker.lower()]
        else:
            target_segments = candidates

        if not target_segments:
            print("🎉 No segments.")
            t.status = "completed"
            db.commit()
            return

        # Load Codebook
        cb_rows = db.query(Codebook).filter(Codebook.library_id == library_id, Codebook.status != 'deprecated').all()
        cb_for_ai = [f"{c.code}: {c.definition}" if c.definition else c.code for c in cb_rows]
        cb_map = {c.code: c.id for c in cb_rows}
        codebook_dump = "\n".join(cb_for_ai) if cb_for_ai else "(Empty Codebook)"

        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        client = OpenAI(api_key=api_key, base_url=os.getenv("OPENAI_BASE_URL"))

        # Chunking
        BATCH_SIZE = 15 if density == "dense" else 40
        total_segments = len(target_segments)
        print(f"📊 Processing {total_segments} segments in chunks of {BATCH_SIZE}...")

        # --- CHUNK LOOP ---
        for i in range(0, total_segments, BATCH_SIZE):
            chunk = target_segments[i: i + BATCH_SIZE]
            valid_seg_ids = {s.id for s in chunk}
            print(f"   🔄 Chunk {i // BATCH_SIZE + 1}...")

            # === STEP 1: MATCHER ===
            segments_payload = json.dumps([{"id": s.id, "text": s.text[:800]} for s in chunk], ensure_ascii=False)
            try:
                resp1 = client.chat.completions.create(
                    model=os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini"),
                    messages=[{"role": "system", "content": SYS_PROMPT}, {"role": "user",
                                                                          "content": AGENT_MATCHER_TEMPLATE.format(
                                                                              codebook_json=codebook_dump,
                                                                              segments_json=segments_payload,
                                                                              density_instruction=get_density_instruction(
                                                                                  density))}],
                    temperature=0.1
                )
                matches = json.loads(re.sub(r"^```json\s*|\s*```$", "", resp1.choices[0].message.content.strip())).get(
                    "matches", [])
            except Exception as e:
                print(f"❌ Step 1 Failed: {e}")
                continue

            # Separate
            draft_events = []
            to_be_created = []
            for item in matches:
                sid = item.get("id")
                # Fix ID
                if sid not in valid_seg_ids:
                    base_id = sid.split('_')[0] + '_' + sid.split('_')[1]
                    if base_id in valid_seg_ids:
                        sid = base_id
                    else:
                        continue

                if item.get("code_name") == "NEED_NEW_CODE":
                    to_be_created.append({"id": sid, "summary": item.get("summary")})
                else:
                    draft_events.append({"id": sid, "summary": item.get("summary"), "code_name": item.get("code_name")})

            # === STEP 2: CREATOR ===
            if to_be_created:
                try:
                    resp2 = client.chat.completions.create(
                        model=os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini"),
                        messages=[{"role": "system", "content": SYS_PROMPT}, {"role": "user",
                                                                              "content": AGENT_CREATOR_TEMPLATE.format(
                                                                                  uncoded_json=json.dumps(to_be_created,
                                                                                                          ensure_ascii=False))}],
                        temperature=0.4
                    )
                    new_codes = json.loads(
                        re.sub(r"^```json\s*|\s*```$", "", resp2.choices[0].message.content.strip())).get("new_codes",
                                                                                                          [])
                    draft_events.extend(new_codes)
                except Exception as e:
                    print(f"❌ Step 2 Failed: {e}")
                    for x in to_be_created: draft_events.append({**x, "code_name": "Pending"})

            if not draft_events: continue

            # === STEP 3: REFINER ===
            print(f"   ✨ Refining {len(draft_events)} events...")
            try:
                resp3 = client.chat.completions.create(
                    model=os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini"),
                    messages=[{"role": "system", "content": SYS_PROMPT}, {"role": "user",
                                                                          "content": AGENT_REFINER_TEMPLATE.format(
                                                                              draft_json=json.dumps(draft_events,
                                                                                                    ensure_ascii=False))}],
                    temperature=0.2
                )
                refined_data = json.loads(re.sub(r"^```json\s*|\s*```$", "", resp3.choices[0].message.content.strip()))
                final_events = refined_data.get("refined_results", [])
            except Exception as e:
                print(f"❌ Step 3 Failed: {e}")
                final_events = draft_events

            # === SAVE TO DB ===
            now_utc = datetime.now(timezone.utc)
            for evt_data in final_events:
                code_name = evt_data.get("code_name", "Unknown")

                cid = cb_map.get(code_name)
                if not cid:
                    new_cid = _uuid("cb")
                    db.add(Codebook(id=new_cid, code=code_name, definition="AI Generated", status="proposed",
                                    library_id=library_id, created_at=now_utc))
                    cb_map[code_name] = new_cid
                    cid = new_cid

                eid = _uuid("evt")
                db.add(Event(
                    id=eid, transcript_id=transcript_id, segment_id=evt_data["id"],
                    summary=evt_data["summary"], status="proposed", confidence=0.9, created_by=f"AI-{density}"
                ))
                db.add(EventLabel(event_id=eid, codebook_id=cid, code_name=code_name, rationale=f"AI ({density})",
                                  created_by="AI"))

            db.commit()

        t.status = "completed"
        db.commit()
        print(f"✅ AI Task Finished.")

    except Exception as e:
        print(f"❌ Critical Error: {e}")
        try:
            db.rollback(); t = db.query(Transcript).filter(
                Transcript.id == transcript_id).first(); t.status = "error"; db.commit()
        except:
            pass
    finally:
        db.close()


@router.post("/batch_ai/{transcript_id}")
async def trigger_batch_ai(
        transcript_id: str,
        background_tasks: BackgroundTasks,
        library_id: str,
        target_speaker: Optional[str] = None,
        density: str = "balanced",
        db: Session = Depends(get_db)
):
    t = db.query(Transcript).filter(Transcript.id == transcript_id).first()
    if not t: raise HTTPException(404, "Not found")
    lib = db.query(CodebookLibrary).filter(CodebookLibrary.id == library_id).first()
    if not lib: raise HTTPException(404, "Library not found")

    background_tasks.add_task(run_batch_ai_logic, transcript_id, library_id, target_speaker, density)
    return {"status": "queued", "library": lib.name}


@router.get("/synthesize_codebook", response_model=SynthesisOut)
def synthesize_codebook(db: Session = Depends(get_db)):
    return {"themes": []}