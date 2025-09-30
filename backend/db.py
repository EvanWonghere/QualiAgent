#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/9/29 17:50
# @Author  : EvanWong
# @File    : db.py
# @Project : QualiAgent

# backend/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./data.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
