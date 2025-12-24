# backend/repositories/sql_repo.py
from typing import List, Optional, Dict, Any
from sqlalchemy import text as sql
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
import json


# --- Codebook Operations ---

def list_codebook(db: Session, include_deprecated: bool = False) -> List[Dict[str, Any]]:
    # ✨ 升级查询：使用子查询统计每个 Code 在 event_labels 表中出现的次数
    base_q = """
    SELECT c.*, 
           (SELECT COUNT(*) FROM event_labels el WHERE el.codebook_id = c.id) as n_uses
    FROM codebook c
    """

    where_clause = " WHERE c.status != 'deprecated'" if not include_deprecated else ""
    order_clause = " ORDER BY c.name"

    q = base_q + where_clause + order_clause

    try:
        return [dict(r) for r in db.execute(sql(q)).mappings().all()]
    except OperationalError:
        return []


def get_codebook_by_name(db: Session, name: str) -> Optional[Dict[str, Any]]:
    # ✨ 新增：用于根据名字查找 ID
    try:
        r = db.execute(sql("SELECT * FROM codebook WHERE name=:name"), {"name": name}).mappings().first()
        return dict(r) if r else None
    except OperationalError:
        return None


def create_codebook_item(db: Session, item: Dict[str, Any]):
    # ✨ 新增：用于 AI 自动创建新代码
    stmt = """
    INSERT INTO codebook (id, name, definition, status, created_at)
    VALUES (:id, :name, :definition, :status, :created_at)
    """
    db.execute(sql(stmt), item)


def merge_codebook(db: Session, from_id: str, into_id: str):
    db.execute(sql("UPDATE event_labels SET codebook_id=:into WHERE codebook_id=:frm"),
               {"into": into_id, "frm": from_id})
    db.execute(sql("UPDATE codebook SET status='deprecated' WHERE id=:frm"), {"frm": from_id})


# --- Segments Operations ---

def list_segments(db: Session, transcript_id: str) -> List[Dict[str, Any]]:
    q = ("SELECT id, transcript_id, [index], speaker, text "
         "FROM segments WHERE transcript_id=:tid ORDER BY [index]")
    try:
        return [dict(r) for r in db.execute(sql(q), {"tid": transcript_id}).mappings().all()]
    except OperationalError:
        return []


def list_unlabeled_segments(db: Session, transcript_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    # ✨ 新增：用于 AI 批量获取未编码片段
    q = """
    SELECT s.id, s.text, s.[index]
    FROM segments s
    LEFT JOIN events e ON e.segment_id = s.id AND e.status IN ('accepted','proposed')
    WHERE s.transcript_id=:tid AND e.id IS NULL
    ORDER BY s.[index] ASC
    LIMIT :limit
    """
    return [dict(r) for r in db.execute(sql(q), {"tid": transcript_id, "limit": limit}).mappings().all()]


# --- Events Operations ---

def get_event(db: Session, event_id: str) -> Optional[Dict[str, Any]]:
    try:
        r = db.execute(sql("SELECT * FROM events WHERE id=:id"), {"id": event_id}).mappings().first()
        return dict(r) if r else None
    except OperationalError:
        return None


def get_recent_accepted_events(db: Session, transcript_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    # ✨ 新增：用于 AI 获取 Context (Few-Shot Learning)
    q = """
    SELECT e.summary, cb.name as code_name
    FROM events e
    LEFT JOIN event_labels el ON e.id = el.event_id
    LEFT JOIN codebook cb ON el.codebook_id = cb.id
    WHERE e.transcript_id = :tid AND e.status = 'accepted'
    ORDER BY e.created_at DESC
    LIMIT :limit
    """
    return [dict(r) for r in db.execute(sql(q), {"tid": transcript_id, "limit": limit}).mappings().all()]


def create_event(db: Session, event: Dict[str, Any]):
    # ✨ 新增：用于 AI 批量插入
    stmt = """
    INSERT OR REPLACE INTO events(id, transcript_id, segment_id, summary, created_by, status, confidence, created_at, raw_excerpt)
    VALUES(:id, :transcript_id, :segment_id, :summary, :created_by, :status, :confidence, :created_at, :raw_excerpt)
    """
    db.execute(sql(stmt), event)


def update_event_status(db: Session, event_id: str, status: str) -> int:
    return db.execute(sql("UPDATE events SET status=:s WHERE id=:id"), {"s": status, "id": event_id}).rowcount


def patch_event(db: Session, event_id: str, fields: Dict[str, Any]) -> int:
    if not fields:
        return 0
    # 安全处理：仅允许特定的列
    allowed_cols = {"summary", "status", "confidence", "created_by"}
    safe_fields = {k: v for k, v in fields.items() if k in allowed_cols}

    if not safe_fields:
        return 0

    sets = ", ".join([f"{k}=:{k}" for k in safe_fields.keys()])
    safe_fields["id"] = event_id
    return db.execute(sql(f"UPDATE events SET {sets} WHERE id=:id"), safe_fields).rowcount


# --- Label Operations ---

def add_event_label(db: Session, event_id: str, codebook_id: str, created_by: str, rationale: Optional[str] = None):
    # ✨ 兼容：INSERT OR REPLACE
    db.execute(sql(
        "INSERT OR REPLACE INTO event_labels(id,event_id,codebook_id,created_by,rationale,created_at) "
        "VALUES(:id,:e,:c,:by,:ra,CURRENT_TIMESTAMP)"
    ), {"id": f"l.{event_id}.{codebook_id}", "e": event_id, "c": codebook_id, "by": created_by, "ra": rationale})


def delete_event_labels(db: Session, event_id: str):
    # ✨ 新增：用于 Review 时更换标签（先删后加）
    db.execute(sql("DELETE FROM event_labels WHERE event_id=:id"), {"id": event_id})


def insert_label_review(db: Session, label_id: str, reviewer: str, decision: str, notes: Optional[str]):
    db.execute(sql(
        "INSERT INTO label_reviews(id,event_label_id,reviewer,decision,notes,created_at) "
        "VALUES(:id,:lid,:r,:d,:n,CURRENT_TIMESTAMP)"
    ), {"id": f"r.{label_id}", "lid": label_id, "r": reviewer, "d": decision, "n": notes})


# --- Queue Operations ---

# backend/repositories/sql_repo.py (局部替换 list_review_queue 函数)

def list_review_queue(db: Session, transcript_id: Optional[str] = None) -> List[Dict[str, Any]]:
    # ✨ 关键修改：在子查询中 JOIN codebook 表，获取 code_name
    base = """
    SELECT e.*, 
    (
        SELECT json_group_array(json_object(
            'id', el.id,
            'event_id', el.event_id,
            'codebook_id', el.codebook_id,
            'code_name', cb.name,  -- ✨ 这里！把名字取出来
            'created_by', el.created_by,
            'created_at', el.created_at,
            'rationale', el.rationale
        )) 
        FROM event_labels el 
        LEFT JOIN codebook cb ON el.codebook_id = cb.id -- ✨ 关联查表
        WHERE el.event_id = e.id
    ) AS labels_json 
    FROM events e 
    WHERE e.status='proposed'
    """

    try:
        params = {}
        if transcript_id:
            base += " AND e.transcript_id=:tid"
            params["tid"] = transcript_id

        # 按时间倒序，新生成的在前面
        base += " ORDER BY e.created_at DESC"

        rows = db.execute(sql(base), params).mappings().all()
    except OperationalError:
        rows = []

    out = []
    import json
    for r in rows:
        labels_str = r.get("labels_json")
        labels = []
        if labels_str:
            try:
                labels = json.loads(labels_str)
                # 过滤掉 null 的情况（如果 label 没关联上 codebook）
                if labels and labels[0] is None: labels = []
            except:
                pass

        e = dict(r)
        e.pop("labels_json", None)
        out.append({"event": e, "labels": labels})
    return out

def get_events_with_labels_sorted(db: Session, transcript_id: str) -> List[Dict[str, Any]]:
    # ✨ 新增：用于 events_v2 的列表展示
    rows = db.execute(sql("""
        SELECT
            e.id              AS event_id,
            e.transcript_id   AS transcript_id,
            e.segment_id      AS segment_id,
            e.summary         AS summary,
            e.status          AS status,
            e.created_by      AS created_by,
            e.created_at      AS created_at,
            l.id              AS event_label_id,
            l.codebook_id     AS codebook_id,
            cb.name           AS code_name
        FROM events e
        LEFT JOIN event_labels l ON l.event_id = e.id
        LEFT JOIN codebook cb ON cb.id = l.codebook_id
        WHERE e.transcript_id = :tid
        ORDER BY CAST(
            (SELECT [index] FROM segments s WHERE s.id = e.segment_id) AS INTEGER
        ) ASC
    """), {"tid": transcript_id}).mappings().all()

    by_event: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        eid = r["event_id"]
        if eid not in by_event:
            by_event[eid] = {
                "event": {
                    "id": r["event_id"],
                    "transcript_id": r["transcript_id"],
                    "segment_id": r["segment_id"],
                    "summary": r["summary"],
                    "status": r["status"],
                    "created_by": r["created_by"],
                    "created_at": r["created_at"],
                },
                "labels": []
            }
        if r["event_label_id"]:
            by_event[eid]["labels"].append({
                "id": r["event_label_id"],
                "code_name": r["code_name"],
            })

    return list(by_event.values())