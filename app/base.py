"""資料庫連線設定：Base（所有表的共同父類別）、engine（連線池）、SessionLocal（session 工廠）。"""
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER
from sqlalchemy.orm import DeclarativeBase

# 所有資料表 class（見 models.py）都要繼承它，Base.metadata 才會收集到這些表
class Base(DeclarativeBase):
    pass

# 用 URL.create 組連線字串，密碼有特殊字元時比手寫字串安全
url = URL.create(
    drivername="postgresql+psycopg",  # 若使用 psycopg2 請改為 "postgresql+psycopg2"
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,  # 例如 "localhost" 或 Docker 服務名稱 "db"
    port=DB_PORT,
    database=DB_NAME,
)
# engine：整個程式共用一個，內部維護連線池
engine = create_async_engine(url)
# SessionLocal 是「工廠」不是 session：要用 `async with SessionLocal() as session:` 才會產生 session
# expire_on_commit=False：commit 後物件屬性不會失效，async 下才不會在讀取時觸發額外查詢而出錯
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
