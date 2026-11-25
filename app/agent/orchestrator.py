# async def search_knowledge_base(query: str) -> str:
#     nonlocal embed_failed
from app.agent.RAG.embeding import embed_texts
from fastapi.exceptions import HTTPException
from app.base import SessionLocal
from app.crud import ChunkRepository
from app.config import ANTHROPIC_CLAUDE_MODEL, ANTHROPIC_API_KEY
from anthropic import AsyncAnthropic, beta_async_tool
from app.agent.LLM import SYSTEM_PROMPT

client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
TOOL_RULES = """
                0-1.回答資安相關問題前，先用 search_knowledge_base 查詢知識庫；以下規則中的「檢索資料」就是工具回傳的內容。
                0-2.知識庫是英文文件，查詢時用英文關鍵字；第一次的結果不相關，可以換關鍵字再查，最多查三次。
                0-3.與資安無關的問題不要查詢，直接回答「資料中沒有相關內容。」
                0-4.引用時使用工具回傳的片段編號。

                1.你是一個專業的 Cyber Threat Intelligence（CTI）分析助手，負責根據檢索資料回答使用者的資安問題。
                2.你擅長運用顧問的問答風格，回答使用者的問題。
                3.根據 search_knowledge_base 查到的資料，以及使用者提問，生成正確的回應。
                4.沒有的事實不可捏造，一切皆以正確來源做回覆。
                5.用繁體中文回答。
                6.與資安無關的問題不要查詢，直接回答『資料中沒有相關內容。』；資安問題查了三次仍沒有相關資料，才回答這一句。
                7.回答時，在引用資料的句子後面標出片段編號，例如 [1] 或 [2][3]，編號使用 search_knowledge_base 回傳的編號；沒有引用到的片段不要標。
                8.使用者問「常用、最常見、最多、排名」這類程度問題時，檢索資料若沒有頻率或統計資訊，要先明說「資料中沒有常見程度的資訊」，再列出資料裡有的手法，不可把它們說成最常用。
                9.資料片段只涵蓋問題的一部分時，要說明「以下僅根據檢索到的資料」，不要假裝是完整清單。
                10.輸出格式:一開始為簡單摘要，第二部分為重點說明，要有標題，內容可以條列式陳列，第三部分為總結，第四部份為延伸。
"""
MAX_ITERATIONS = 4
async def retrieve(question: str, top_k: int):
    """檢索（search 和 ask 共用）：問題 → 向量 → 資料庫裡最相近的 top_k 塊，回傳 Chunks 物件清單。"""
    try:
        vecs = await embed_texts([question])               # 要傳清單，取第 [0] 個當問題向量
    except Exception:
        # Ollama 沒開或連不到：回 503（服務暫時無法使用），讓前端顯示明確訊息
        raise HTTPException(status_code=503, detail="向量模型暫時無法使用，請確認 Ollama 已啟動")
    # 每次請求開一個獨立的 session，離開 with 時自動關閉連線
    async with SessionLocal() as session:
        return await ChunkRepository(session).search(vecs[0], top_k)

async def run_agent(question: str, top_k: int = 5, emit = None, model: str = ANTHROPIC_CLAUDE_MODEL, effort: str = "low") -> dict:
    collected = [] # 查到的塊(chunk)
    seen = {} # 塊的編號
    searches = [] # 用過的關鍵字
    embed_failed = False # 檢索是否失敗

    answer = None
    sources = None

# ___________________________tool function___________________________________________
    @beta_async_tool
    async def search_knowledge_base(query: str) -> str:

        
        nonlocal embed_failed # 用於修改外層函數的變數
        searches.append(query)

        # emit 1 : 開始查詢
        if emit: 
            await emit({"type": "search", "query": query})

        try:
            chunks = await retrieve(query, top_k)
        except HTTPException:
            embed_failed = True

            # emit 2 : 查詢失敗
            if emit: 
                await emit({"type": "search_error", "query": query})
            return "查詢失敗 : 向量模型暫時無法使用。"

        parts = []
        found = []
        for chunk in chunks:
            is_new = chunk.id not in seen
            if is_new:
                collected.append(chunk)
                seen[chunk.id] = len(collected)
            parts.append(f"[{seen[chunk.id]}]\t{chunk.content}")
            found.append({"ref": seen[chunk.id], "title": chunk.content.split("\n", 1)[0], "new": is_new})

        if emit:
            await emit({"type": "found", "query": query, "results": found})
        return "\n\n".join(parts)
# ______________________________________________________________________
    
    runner = client.beta.messages.tool_runner(
        model=model,
        max_tokens=2048,
        system=TOOL_RULES,
        tools = [search_knowledge_base],
        max_iterations=MAX_ITERATIONS,
        output_config={"effort": effort},
        messages=[{"role": "user", "content": question}]
    )
    final = await runner.until_done()

    if embed_failed and not collected:
        raise HTTPException(status_code=503, detail="向量模型至時無法使用，請確認 Ollama 已啟動")

    answer = "".join(content.text for content in final.content if content.type == "text").strip()    

    if final.stop_reason == "refusal":
        answer = "這個問題無法回答。"
    elif final.stop_reason == "tool_use" or not answer:
        answer = "查詢次數已達上限，沒能整理出答案，請換個問法再試一次。"
    elif final.stop_reason == "max_tokens":
        answer += "\n\n(回答過長，已被截斷) "

    sources = [{"ref": index, "id": chunk.id, "title": chunk.content.split("\n", 1)[0] } for index, chunk in enumerate(collected, 1)]
    return {"answer": answer, "sources": sources, "searches": searches}

