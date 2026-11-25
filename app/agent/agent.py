"""Agent 版問答：Claude 自己決定要不要查知識庫、用什麼關鍵字、要不要再查一次。

「要工具 → 執行 → 把結果送回」的來回由 SDK 的 Tool Runner 處理；
這裡只寫工具本體（查詢、去重、接續編號）和最後的答案整理。
"""
from anthropic import AsyncAnthropic, beta_async_tool
from fastapi import HTTPException
from app.config import ANTHROPIC_API_KEY, ANTHROPIC_CLAUDE_MODEL
from app.agent.LLM import SYSTEM_PROMPT
from app.agent.RAG.retrieve import retrieve

# 在原本的回答規則前面，加上使用工具的規則
TOOL_RULES = """
                0-1.回答資安相關問題前，先用 search_knowledge_base 查詢知識庫；以下規則中的「檢索資料」就是工具回傳的內容。
                0-2.知識庫是英文文件，查詢時用英文關鍵字；第一次的結果不相關，可以換關鍵字再查，最多查三次。
                0-3.與資安無關的問題不要查詢，直接回答「資料中沒有相關內容。」
                0-4.引用時使用工具回傳的片段編號。
"""
AGENT_SYSTEM_PROMPT = TOOL_RULES + SYSTEM_PROMPT
MAX_ITERATIONS = 4          # 呼叫 Claude 的次數上限：最多查 3 次，再加 1 次回答

client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


async def run_agent(question: str, top_k: int = 5) -> dict:
    """回傳 {"answer": 答案, "sources": 引用來源, "searches": 每次查詢用的關鍵字}。"""
    collected = []           # 這次對話查到的所有塊；位置 +1 就是引用編號
    seen = {}                # chunk.id → 編號，同一塊查到兩次時沿用舊編號
    searches = []            # 每次查詢用的關鍵字（除錯、展示用）
    embed_failed = False

    # 工具寫在函式裡面，才能共用這次請求的 collected、seen（兩個使用者同時問也不會混在一起）
    # docstring 會變成給 Claude 看的工具說明，Args 會變成參數說明
    @beta_async_tool
    async def search_knowledge_base(query: str) -> str:
        """查詢資安知識庫（MITRE ATT&CK 攻擊技術與緩解措施、OWASP、Cloudflare 文件），回傳編號過的相關段落。

        Args:
            query: 查詢關鍵字，請用英文，例如 multi-factor authentication、phishing。
        """
        nonlocal embed_failed
        searches.append(query)
        try:
            chunks = await retrieve(query, top_k)
        except HTTPException:
            embed_failed = True
            return "查詢失敗：向量模型暫時無法使用。"
        parts = []
        for c in chunks:
            if c.id not in seen:                     # 新的塊才給新編號，編號接在之前的後面
                collected.append(c)
                seen[c.id] = len(collected)
            parts.append(f"[{seen[c.id]}]\t{c.content}")
        return "\n\n".join(parts)

    runner = client.beta.messages.tool_runner(
        model=ANTHROPIC_CLAUDE_MODEL,
        max_tokens=2048,
        system=AGENT_SYSTEM_PROMPT,
        tools=[search_knowledge_base],
        messages=[{"role": "user", "content": question}],
        max_iterations=MAX_ITERATIONS,
        output_config={"effort": "low"},
    )
    final = await runner.until_done()       # SDK 處理「要工具 → 執行 → 送回結果」的來回，直到 Claude 回答

    # 工具失敗時 Claude 只會收到「查詢失敗」；一塊都沒查到就直接回 503，不讓它硬答
    if embed_failed and not collected:
        raise HTTPException(status_code=503, detail="向量模型暫時無法使用，請確認 Ollama 已啟動")

    # final.content 裡有思考區塊和文字區塊，只取文字
    answer = "".join(b.text for b in final.content if b.type == "text").strip()
    if final.stop_reason == "refusal":
        answer = "這個問題無法回答。"
    elif final.stop_reason == "tool_use" or not answer:      # 碰到次數上限時，最後一則可能還在要工具
        answer = "查詢次數已達上限，沒能整理出答案，請換個問法再試一次。"
    elif final.stop_reason == "max_tokens":
        answer += "\n\n（回答過長，已被截斷）"

    # 編號就是 collected 的位置，所以照順序編就能和答案裡的 [n] 對上
    sources = [{"ref": i, "id": c.id, "title": c.content.split("\n", 1)[0]} for i, c in enumerate(collected, 1)]
    return {"answer": answer, "sources": sources, "searches": searches}
