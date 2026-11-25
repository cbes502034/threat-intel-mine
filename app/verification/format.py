"""請求／資料格式定義（Pydantic）：格式不符時 FastAPI 會自動回 422。"""
from pydantic import BaseModel, Field

class Msg(BaseModel):
    chat_prompt: list[dict]
    system_prompt: str

# /api/search 與 /api/ask 共用的請求格式
class SearchBody(BaseModel):
    question: str = Field(min_length=1, max_length=500)   # ← 使用者的問題
    top_k: int = Field(default=5, ge=1, le=10)            # ← 要回傳幾塊，預設 3
