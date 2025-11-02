#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/9/29 17:50
# @Author  : EvanWong
# @File    : db.py
# @Project : QualiAgent

# backend/db.py
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

ROOT = Path(__file__).resolve().parents[1]  # backend/ -> project root
DB_PATH = ROOT / "data.db"                  # e.g., /Users/you/QualiAgent/data.db
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
