from fastapi import APIRouter, HTTPException
from typing import List
from backend.contracts.models import CodebookItem
from backend.repositories.fixtures_repo import load_codebook

router = APIRouter()

@router.get("", response_model=List[CodebookItem])
def list_codebook():
    return load_codebook()

@router.post("")
def create_codebook_item():
    raise HTTPException(status_code=501, detail="Not implemented in Phase 0.5")

@router.post("/merge")
def merge_codebook_item():
    raise HTTPException(status_code=501, detail="Not implemented in Phase 0.5")

