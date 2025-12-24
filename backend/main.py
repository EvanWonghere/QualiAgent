# backend/main.py
import os
import uvicorn
from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.db import Base, engine, db_info
from backend.migrations.run import run as run_migrations

# --- 1. 引入核心模块 ---
from backend.api import (
    importer as importer_router,
    transcripts as transcripts_router,
    ai as ai_router,
    review as review_router,
    codebook as codebook_router,
    segments as segments_router  # ✅ 修复1：取消注释，引入 segments 模块
)

load_dotenv()

# --- 生命周期管理 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f">>> QualiAgent Starting...")
    print(f">>> Database Info: {db_info()}")

    # 1. 自动创建表结构
    Base.metadata.create_all(bind=engine)

    # 2. 尝试运行迁移脚本
    try:
        run_migrations(engine)
    except Exception as e:
        print(f"!!! Migration warning (can be ignored in dev): {e}")

    yield
    print(">>> Shutting down...")


# --- 初始化 App ---
app = FastAPI(
    title="QualiAgent Backend",
    version="0.8.0 (AI Integrated)",
    description="API backend for QualiAgent: AI-Assisted Qualitative Analysis Tool",
    lifespan=lifespan
)

# --- CORS 设置 ---
default_origins = "http://localhost:8501,http://127.0.0.1:8501,http://localhost:5173,http://127.0.0.1:5173"
origins = os.environ.get("CORS_ORIGINS", default_origins).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 注册 API 路由 ---

# 1. 基础数据模块
app.include_router(importer_router.router, prefix="/import", tags=["Import"])
app.include_router(transcripts_router.router, prefix="/transcripts", tags=["Transcripts"])

# ✅ 修复2：取消注释，注册 /segments 路由
# 这样前端访问 http://localhost:8000/segments/xxx 就能通了
app.include_router(segments_router.router, prefix="/segments", tags=["Segments"])

# 2. AI 核心
app.include_router(ai_router.router, prefix="/events_v2", tags=["AI Engine"])

# 3. 可选模块
if review_router:
    app.include_router(review_router.router, prefix="/review", tags=["Review Queue"])

if codebook_router:
    app.include_router(codebook_router.router, prefix="/codebook", tags=["Codebook"])


# --- 基础监控接口 ---
@app.get("/health")
def health():
    return {"status": "ok", "database": db_info()}

@app.get("/")
def read_root():
    return {"message": "QualiAgent Backend is Running!", "ai_module": "Active"}

@app.get("/config/defaults")
def config_defaults():
    return {
        "OPENAI_LLM_MODEL": os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini"),
        "USE_EMBEDDINGS": os.getenv("USE_EMBEDDINGS", "1"),
        "USE_LLM": os.getenv("USE_LLM", "1"),
    }


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)