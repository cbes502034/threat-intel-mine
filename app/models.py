"""資料表定義（ORM）：目前只有一張 chunks 表，存「切好的文字」與「它的向量」。"""
from app.base import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, Text, func, DECIMAL
from pgvector.sqlalchemy import Vector
class Chunks(Base):
    __tablename__ = "chunks"                          # 資料庫裡的表名
    id: Mapped[int] = mapped_column(primary_key=True)  # 主鍵，自動遞增
    content: Mapped[str] = mapped_column(Text)         # 切片文字（開頭已含文件標題）
    vector = mapped_column(Vector(1024))               # bge-m3 的輸出是 1024 維；維度要和模型一致
