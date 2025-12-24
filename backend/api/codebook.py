# backend/api/codebook.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid

from backend.db import SessionLocal
from backend.models import Codebook, EventLabel, Event, CodebookLibrary

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Models ---
class LibraryOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    code_count: int


class LibraryCreate(BaseModel):
    name: str
    description: Optional[str] = None


class CodebookOut(BaseModel):
    id: str
    code: str
    definition: Optional[str]
    usage_count: int
    status: str
    library_id: Optional[str]  # ✨


# --- API ---

# 1. 获取所有 Libraries
@router.get("/libraries", response_model=List[LibraryOut])
def get_libraries(db: Session = Depends(get_db)):
    libs = db.query(CodebookLibrary).all()
    out = []
    for lib in libs:
        count = db.query(Codebook).filter(Codebook.library_id == lib.id).count()
        out.append(LibraryOut(id=lib.id, name=lib.name, description=lib.description, code_count=count))
    return out


# 2. 创建 Library
@router.post("/libraries")
def create_library(payload: LibraryCreate, db: Session = Depends(get_db)):
    new_id = f"lib_{uuid.uuid4().hex[:8]}"
    lib = CodebookLibrary(id=new_id, name=payload.name, description=payload.description)
    db.add(lib)
    db.commit()
    return {"id": new_id, "name": lib.name}


# 3. 初始化默认 Library (如果用户还没有的话)
@router.post("/libraries/init_default")
def init_default_library(db: Session = Depends(get_db)):
    existing = db.query(CodebookLibrary).first()
    if not existing:
        default_lib = CodebookLibrary(id=f"lib_default", name="Default Project",
                                      description="Auto-generated default library")
        db.add(default_lib)
        db.commit()
        return {"id": default_lib.id}
    return {"id": existing.id}


# 4. 获取 Code (支持按 Library 筛选)
@router.get("/", response_model=List[CodebookOut])
def get_codebook(library_id: Optional[str] = None, db: Session = Depends(get_db)):
    """
    列出编码。如果提供了 library_id，只列出该库的编码。
    """
    query = db.query(Codebook).filter(Codebook.status != 'deprecated')

    if library_id:
        query = query.filter(Codebook.library_id == library_id)

    codes = query.all()

    out = []
    for c in codes:
        # 简单统计使用次数
        count = db.query(EventLabel).join(Event).filter(
            EventLabel.codebook_id == c.id,
            Event.status == 'accepted'
        ).count()

        out.append(CodebookOut(
            id=c.id,
            code=c.code,
            definition=c.definition,
            usage_count=count,
            status=c.status,
            library_id=c.library_id
        ))

    out.sort(key=lambda x: x.usage_count, reverse=True)
    return out


# 5. 手动创建 Code (必须指定 Library)
@router.post("/")
def create_code(code: str, definition: str, library_id: str, db: Session = Depends(get_db)):
    new_id = f"cb_{uuid.uuid4().hex[:8]}"
    new_code = Codebook(
        id=new_id,
        code=code,
        definition=definition,
        status="active",
        library_id=library_id  # ✨
    )
    db.add(new_code)
    db.commit()
    return {"status": "created", "id": new_id}


@router.delete("/{code_id}")
def delete_code(code_id: str, db: Session = Depends(get_db)):
    c = db.query(Codebook).filter(Codebook.id == code_id).first()
    if c:
        c.status = 'deprecated'
        db.commit()
    return {"status": "deleted"}