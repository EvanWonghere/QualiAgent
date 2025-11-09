#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/9/29 17:50
# @Author  : EvanWong
# @File    : db.py
# @Project : QualiAgent

# backend/db.py
from pathlib import Path
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("QUALIAGENT_DB_PATH", str(ROOT / "data.db"))).resolve()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
Base = declarative_base()

def db_info() -> str:
    return str(DB_PATH)

