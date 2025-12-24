# backend/schemas.py
from pydantic import BaseModel
from typing import Optional
import datetime

class MemoBase(BaseModel):
    title: str
    content: str

class CodeBase(BaseModel):
    code: str
    excerpt: str
    transcript_id: Optional[int] = None
    memo_id: Optional[int] = None

class MemoCreate(MemoBase):
    pass

class CodeCreate(CodeBase):
    pass

# ✨ --- NEW: Schema to hold AI configuration ---
class AIConfig(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    llm_model: Optional[str] = None
    embed_model: Optional[str] = None

# ✨ --- Updated request schemas to include the config ---
class AIGenerateRequest(BaseModel):
    transcript_id: int
    config: Optional[AIConfig] = None

class AISearchRequest(BaseModel):
    transcript_id: int
    query: str
    top_k: int = 5
    config: Optional[AIConfig] = None

class Memo(MemoBase):
    id: int
    class Config:
        from_attributes = True

class Transcript(BaseModel):
    id: int
    title: str
    status: str  # ✨ FIX: Add the status field so the API returns it.
    class Config:
        from_attributes = True

# ✨ --- NEW: Schemas for detailed single-item views ---
class TranscriptDetail(Transcript):
    content: str

class MemoDetail(Memo):
    content: str # Memo already had content in its base, this makes it explicit for the response
# ---

# ✨ --- NEW: The missing response schema ---
class CodeGenerationResponse(BaseModel):
    message: str


class Code(CodeBase):
    id: int
    created_at: datetime.datetime
    source: Optional[str] = None
    class Config:
        from_attributes = True

# ✨ --- NEW: Schema for the default config response ---
class AIConfigDefaults(BaseModel):
    api_key_set: bool
    base_url: Optional[str] = None
    llm_model: Optional[str] = None
    embed_model: Optional[str] = None
    chunk_tokens: Optional[int] = None
