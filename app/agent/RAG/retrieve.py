"""檢索：問題 → 向量 → 資料庫裡最相近的 top_k 塊。

固定流程（services.py）與 Agent 的工具（agent.py）都用這一支。
放在這裡而不是 services.py，是為了避免 services.py ↔ agent.py 互相匯入。
"""
from fastapi import HTTPException
from app.agent.RAG.embeding import embed_texts
from app.base import SessionLocal
from app.crud import ChunkRepository


async def retrieve(question: str, top_k: int):
    """回傳 Chunks 物件清單（依餘弦距離由近到遠）。"""
    try:
        vecs = await embed_texts([question])               # 要傳清單，取第 [0] 個當問題向量
    except Exception:
        # Ollama 沒開或連不到：回 503（服務暫時無法使用），讓前端顯示明確訊息
        raise HTTPException(status_code=503, detail="向量模型暫時無法使用，請確認 Ollama 已啟動")
    # 每次請求開一個獨立的 session，離開 with 時自動關閉連線
    async with SessionLocal() as session:
        return await ChunkRepository(session).search(vecs[0], top_k)
