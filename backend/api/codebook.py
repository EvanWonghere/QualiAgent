# backend/api/codebook.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text as sql # ✨ 导入 sql
from backend.db import SessionLocal
from backend.repositories import sql_repo as repo

router = APIRouter()

def get_db():
    db = SessionLocal(); 
    try: yield db
    finally: db.close()

@router.get("", response_model=List[dict])
def list_codebook(include_deprecated: bool = False, db: Session = Depends(get_db)):
    return repo.list_codebook(db, include_deprecated)

class MergeIn(BaseModel):
    from_id: str
    into_id: str

@router.post("/merge")
def merge_codebook(body: MergeIn, db: Session = Depends(get_db)):
    if body.from_id == body.into_id:
        raise HTTPException(400, "from_id and into_id cannot be the same")
    
    try:
        repo.merge_codebook(db, body.from_id, body.into_id)
        db.commit() # ✅ 关键修复：提交事务
        return {"ok": True}
    except Exception as e:
        db.rollback() # ✨ 良好实践：如果出错则回滚
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{codebook_id}/deprecate")
def deprecate_code(codebook_id: str, db: Session = Depends(get_db)):
    try:
        db.execute(sql("UPDATE codebook SET status='deprecated' WHERE id=:id"), {"id": codebook_id})
        db.commit() # ✅ 关键修复：提交事务
        return {"ok": True}
    except Exception as e:
        db.rollback() # ✨ 良好实践：如果出错则回滚
        raise HTTPException(status_code=500, detail=str(e))