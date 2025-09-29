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
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    chunks = relationship("Chunk", back_populates="dataset", cascade="all, delete")

class Chunk(Base):
    __tablename__ = "chunks"
    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"))
    text = Column(Text)
    embedding = Column(Text)  # JSON string of float list
    start_pos = Column(Integer)
    end_pos = Column(Integer)
    dataset = relationship("Dataset", back_populates="chunks")

def init_db():
    Base.metadata.create_all(bind=engine)
