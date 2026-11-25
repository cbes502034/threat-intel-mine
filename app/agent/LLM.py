import ollama
from time import time
from app.config import OLLAMA_MODEL, OLLAMA_URL, ANTHROPIC_CLAUDE_MODEL, ANTHROPIC_API_KEY
from app.verification.format import Msg
from app.utils import execute_time


import asyncio
from anthropic import AsyncAnthropic


start = time()

# 回答規則：Claude 與 Ollama 共用同一份，改這裡兩邊都會生效
SYSTEM_PROMPT = """
                1.你是一個專業的 Cyber Threat Intelligence（CTI）分析助手，負責根據檢索資料回答使用者的資安問題。
                2.你擅長運用顧問的問答風格，回答使用者的問題。
                3.請根據 檢索資料，以及 使用者提問，生成正確的回應。
                4.沒有的事實不可捏造，一切皆以正確來源做回覆。
                5.用繁體中文回答。
                6.如果資料片段跟問題無關，只回答「資料中沒有相關內容。」這一句，不要描述檢索到的資料，也不要提供資料以外的建議。
                7.回答時，在引用資料的句子後面標出片段編號，例如 [1] 或 [2][3]；沒有引用到的片段不要標。
                8.使用者問「常用、最常見、最多、排名」這類程度問題時，檢索資料若沒有頻率或統計資訊，要先明說「資料中沒有常見程度的資訊」，再列出資料裡有的手法，不可把它們說成最常用。
                9.資料片段只涵蓋問題的一部分時，要說明「以下僅根據檢索到的資料」，不要假裝是完整清單。
                10.輸出格式:一開始為簡單摘要，第二部分為重點說明，要有標題，內容可以條列式陳列，第三部分為總結，第四部份為延伸。
                11.延伸的部分要有註明「AI的結果僅供參考」，因為這裡會請你發揮你的所學。
                12.前三個主題以排名前三的為主，延伸的部分以後段4~5為主，由於相關性稍微少，因此你可以發揮你的能力結合在一起。
            """


class Ollama:
    """本機模型生成答案（模型名稱由環境變數 OLLAMA_MODEL 決定）；介面與 Claude 相同，可互換。"""
    def __init__(self, model: str = OLLAMA_MODEL, url: str = OLLAMA_URL):
        self.model = model
        self.client = ollama.AsyncClient(host=url)      # 要用 Async 版，才能 await

    async def generate(self, user_msg: Msg) -> str:
        """user_msg：[{"role": "user", "content": build_prompt 的結果}]；回傳答案文字（str）。
        Ollama 沒有獨立的 system 參數，規則要放在 messages 最前面，角色用 "system"。
        """
        response = await self.client.chat(
            model=self.model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, *user_msg],
            think=False,                                 # 不輸出思考過程，只要答案
        )
        return response["message"]["content"]

class Claude:
    """答案生成：把「檢索資料 + 使用者提問」交給 Claude，system prompt 規定回答規則。"""
    def __init__(self, model: str = ANTHROPIC_CLAUDE_MODEL):
        self.model = model
        self.client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    # @execute_time
    async def generate(self, user_msg: Msg) -> str:
        """user_msg：[{"role": "user", "content": build_prompt 的結果}]；回傳答案文字（str）。
        system 的規則是回答品質的主要控制點：只依資料回答、繁體中文、無關就拒答、標註 [編號]。
        """
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,                 # 回答長度上限（token）；太小長答案會被截斷
            messages=user_msg,
            system=SYSTEM_PROMPT,
            output_config={"effort": "low"},   # 思考深度低：換取較快的回應
        )
        # response.content 是區塊清單，只取第一個文字區塊
        return next(b.text for b in response.content if b.type == "text")
