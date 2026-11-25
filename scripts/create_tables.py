"""建立資料表：只需要跑一次，重跑也不會出錯（已存在的表會略過）。

用法（在專案根目錄）：
  docker compose exec backend python scripts/create_tables.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # 讓 Python 找得到 app 套件

from sqlalchemy import inspect, text       # noqa: E402
from app.base import Base, engine          # noqa: E402
import app.models                          # noqa: E402,F401  # 一定要匯入，Base 才知道有哪些表


async def create_tables() -> None:
    if not Base.metadata.tables:
        raise SystemExit("Base 裡沒有任何表：請確認模型 class 有繼承 Base，而且已經匯入")

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        before = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
        await conn.run_sync(Base.metadata.create_all)      # 已存在的表會自動略過
        after = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))

    print("新建立的表:", sorted(after - before) or "沒有（都已經存在）")
    print("目前資料庫裡的表:", sorted(after))
    await engine.dispose()                                  # 關閉連線，避免結束時的警告

if __name__ == "__main__":
    asyncio.run(create_tables())