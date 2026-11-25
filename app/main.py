"""FastAPI 入口：只負責「路由」，真正的邏輯都在 services.py。

啟動方式（docker compose 內）：uvicorn app.main:app --reload
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.config import STATIC_DIR
from app.verification.format import SearchBody
from app.services import (
    post_search_service,
    post_ask_service,
    post_agent_ask_service
)
app = FastAPI()


# 健康檢查：前端載入時會打這支，用來判斷後端是否在線（畫面右上的 ONLINE / OFFLINE）
@app.get("/api/health")
def get_health() -> dict: return {"status_code": 200}


# 只檢索：回傳最相近的 top_k 塊原文，不呼叫 Claude
# body 由 SearchBody 驗證（question 1~500 字、top_k 1~10），不合規格 FastAPI 自動回 422
@app.post("/api/search")
async def post_search(body: SearchBody): return await post_search_service(body)


# 問答：檢索 + 組提示詞 + Claude 生成，回傳 answer 與 sources
@app.post("/api/ask")
async def post_ask(body: SearchBody): return await post_ask_service(body)

@app.post("/api/agent_ask")
async def post_agent_ask(body: SearchBody): return await post_agent_ask_service(body) 

# 靜態頁面要放在所有 /api 路由之後
# 否則 "/" 這個掛載點會先吃掉所有請求，/api/* 就打不到了
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True))
