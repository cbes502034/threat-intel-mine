"""建立向量索引：切片 → 轉向量 → 寫進 chunks 表。只在資料或切片設定改變時才要跑。

用法（專案根目錄）：
  docker compose exec backend python -m scripts.build_index
重跑前請先清表（TRUNCATE chunks RESTART IDENTITY），否則會重複寫入。537 塊約需 8 分鐘。
"""
from app.agent.RAG.embeding import get_chunked_data, embed_texts
from app.crud import ChunkRepository
from app.base import SessionLocal
import asyncio
async def snake_case():
    texts = get_chunked_data()                      # 四份語料切好後，攤平成 list[str]
    async with SessionLocal() as session:
        cr = ChunkRepository(session)
        for i in range(0, len(texts), 20):          # 每 20 塊一批：一次丟太多給 Ollama 會很慢甚至失敗
            batch = texts[i:i+20]
            vectors = await embed_texts(batch)      # 這一批的向量，順序與 batch 一一對應
            await cr.add_many(texts=batch, vectors=vectors)   # 每批 commit 一次，中途失敗也保留已完成的
            print(f"已完成 {i + len(batch)} / {len(texts)}")


if __name__ == "__main__":
    asyncio.run(snake_case())
