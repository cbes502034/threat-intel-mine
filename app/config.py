"""設定檔：所有環境變數集中在這裡讀，其他檔案只 import 這裡的常數。
實際的值寫在 .env，由 docker compose 注入容器。
"""
from pathlib import Path
import os

# 前端靜態頁面所在資料夾：專案根目錄下的 static/
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
ID = 1
# Ollama：負責把文字轉成向量（bge-m3）
OLLAMA_URL = os.getenv("OLLAMA_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

# 測試用（容器內連到主機上的 Ollama 要用 host.docker.internal）
OLLAMA_URL_TEST = "http://host.docker.internal:11434"
OLLAMA_MODEL_TEST = "qwen3:4b"

# Claude：負責根據檢索結果生成答案
# 生成答案用哪個模型："claude"（預設）或 "ollama"（本機模型，名稱見 OLLAMA_MODEL）
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "claude").lower()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_CLAUDE_MODEL = os.getenv("ANTHROPIC_CLAUDE_MODEL")

# PostgreSQL 連線資訊（給 base.py 組連線字串）
DB_HOST = os.getenv("DB_HOST")  # ← 服務名，不是 localhost
DB_PORT = os.getenv("DB_PORT")  # ← 容器內部的 port，不是 5435
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
if __name__ == "__main__":
    # print(OLLAMA_URL)
    print(DB_NAME)
