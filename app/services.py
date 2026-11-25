"""服務層：把「檢索 → 組提示詞 → 生成」串起來，路由（main.py）只負責呼叫這裡。

流程：問題 ──embed_texts──▶ 問題向量 ──search──▶ 最相近的 top_k 塊 ──build_prompt──▶ Claude ──▶ 答案
"""
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from app.utils import clean_question
from app.crud import ChunkRepository
from app.agent.LLM import Claude, Ollama
from app.config import LLM_PROVIDER
from app.agent.RAG.embeding import embed_texts
from app.base import SessionLocal
from app.agent.RAG.prompt import build_prompt
from app.agent.orchestrator import retrieve
from app.agent.orchestrator import run_agent
import asyncio
import json




async def post_agent_ask_service(body):
    question = clean_question(body)
    try:
        result = await run_agent(question, body.top_k, model=body.model, effort=body.effort)
    except Exception:
        raise HTTPException(status_code=502, detail="語言模型暫時無法使用，請稍後再試")
    return {"question": question, **result}

async def post_search_service(body):
    """知識檢索：只檢索，不呼叫 Claude，回傳最相近的 body.top_k 塊。"""
    question = clean_question(body)
    chunks = await retrieve(question, body.top_k)
    return {
        "question": question,
        # title 取內容第一行：切片時每塊開頭都補上了文件標題，所以第一行就是標題
        "results": [{"id": c.id, "title": c.content.split("\n", 1)[0], "content": c.content} for c in chunks],
    }


async def post_ask_service(body):
    """問答：檢索 → 組提示詞 → 交給 Claude 生成答案，並附上引用的來源。"""
    question = clean_question(body)
    chunks = await retrieve(question, body.top_k)
    new_prompt = build_prompt([c.content for c in chunks], question)    # 編號 [1][2][3] 與下面 sources 的 ref 一致
    try:
        llm = Ollama() if LLM_PROVIDER == "ollama" else Claude()    # 由環境變數 LLM_PROVIDER 決定
        answer = await llm.generate([{"role": "user", "content": new_prompt}])
    except Exception:
        # Claude API 失敗（金鑰、額度、網路）：回 502（上游服務出錯）
        raise HTTPException(status_code=502, detail="語言模型暫時無法使用，請稍後再試")
    return {
        "question": question,
        "answer": answer,
        # enumerate(chunks, 1)：編號從 1 開始，對應答案裡的 [1][2][3]
        # 注意：這裡列出「所有檢索到的塊」，不是只有答案實際引用的那幾塊
        "sources": [{"ref": i, "id": c.id, "title": c.content.split("\n", 1)[0]} for i, c in enumerate(chunks, 1)],
    }

async def post_agent_stream_service(body):
    question = clean_question(body)
    queue = asyncio.Queue()

    async def worker():
        try:
            result = await run_agent(question, body.top_k, emit=queue.put, model=body.model, effort=body.effort)
            await queue.put({"type": "answer", "question": question, **result})
        except HTTPException as e:
            await queue.put({"type": "error", "status": e.status_code, "detail": e.detail})
        except Exception:
            await queue.put({"type": "error", "status": 502, "detail": "語言模型暫時無法使用，請稍後再試"})
        finally:
             await queue.put(None)
    async def events():
        task = asyncio.create_task(worker())
        try:
            yield f"data: {json.dumps({'type': 'start', 'question': question}, ensure_ascii=False)}\n\n"
            while (event := await queue.get()) is not None:
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            task.cancel()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-buffering": "no"
        }
    )
