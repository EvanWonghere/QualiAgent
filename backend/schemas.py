#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/9/29 16:26
# @Author  : EvanWong
# @File    : schemas.py
# @Project : QualiAgent


# backend/schemas.py
from pydantic import BaseModel
from typing import Optional
import datetime

# --- Base Models ---
class MemoBase(BaseModel):
    title: str
    content: str

class CodeBase(BaseModel):
    code: str
    excerpt: str
    transcript_id: Optional[int] = None
    memo_id: Optional[int] = None
    dataset_id: Optional[int] = None

# --- Create Models ---
class MemoCreate(MemoBase):
    pass

class CodeCreate(CodeBase):
    pass

# --- Response Models ---
class Memo(MemoBase):
    id: int
    class Config:
        from_attributes = True

class Transcript(BaseModel):
    id: int
    title: str
    content: str
    class Config:
        from_attributes = True

class Code(CodeBase):
    id: int
    created_at: datetime.datetime
    source: Optional[str] = None
    class Config:
        from_attributes = True

class Dataset(BaseModel):
    id: int
    name: str
    created_at: datetime.datetime
    class Config:
        from_attributes = True
