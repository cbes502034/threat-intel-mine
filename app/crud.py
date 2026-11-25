"""資料庫存取（Repository）：把 chunks 表的新增與查詢包成方法，其他地方不直接寫 SQL。"""
from app.models import Chunks
from sqlalchemy import select

class ChunkRepository:
    def __init__(self, session):
        # session 由呼叫端用 `async with SessionLocal() as session` 建立後傳入（不是 SessionLocal 本身）
        self.session = session

    async def add_many(self, texts, vectors):
        """批次寫入：texts[i] 與 vectors[i] 一一對應成一筆，最後一次 commit。"""
        if len(texts) != len(vectors):
            raise ValueError("texts 與 vectors 長度不一致")
        self.session.add_all([Chunks(content=t, vector=v) for t, v in zip(texts, vectors)])
        await self.session.commit()

    async def search(self, query_vec, top_k=3):
        """向量檢索：依餘弦距離（<=>）由近到遠排序，取前 top_k 筆。
        距離越小越相似；注意它永遠會回傳 top_k 筆，不管有沒有真的相關。
        """
        query = await self.session.execute(select(Chunks).order_by(Chunks.vector.cosine_distance(query_vec)).limit(top_k))
        return query.scalars().all()   # scalars()：取每列的第一欄（Chunks 物件）；all()：轉成 list
