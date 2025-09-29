# backend/models.py
import datetime
from sqlalchemy import (create_engine, Column, Integer, String, Text, DateTime, ForeignKey)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = "sqlite:///./data.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class Dataset(Base):
    __tablename__ = "datasets"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.UTC))
    chunks = relationship("Chunk", back_populates="dataset", cascade="all, delete")
    codes = relationship("Code", back_populates="dataset") # ✨ 新增

class Chunk(Base):
    __tablename__ = "chunks"
    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"))
    text = Column(Text)
    embedding = Column(Text)
    start_pos = Column(Integer)
    end_pos = Column(Integer)
    dataset = relationship("Dataset", back_populates="chunks")

class Transcript(Base):
    __tablename__ = "transcripts"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, unique=True, nullable=False)
    content = Column(Text, nullable=False)
    codes = relationship("Code", back_populates="transcript")

class Memo(Base):
    __tablename__ = "memos"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, unique=True, nullable=False)
    content = Column(Text, nullable=False)
    codes = relationship("Code", back_populates="memo")

class Code(Base):
    __tablename__ = "codes"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, index=True)
    excerpt = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.UTC))

    transcript_id = Column(Integer, ForeignKey("transcripts.id"), nullable=True)
    memo_id = Column(Integer, ForeignKey("memos.id"), nullable=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=True) # ✨ 新增

    transcript = relationship("Transcript", back_populates="codes")
    memo = relationship("Memo", back_populates="codes")
    dataset = relationship("Dataset", back_populates="codes") # ✨ 新增

def init_db():
    Base.metadata.create_all(bind=engine)