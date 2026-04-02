from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. 設定資料庫位置：這裡使用輕量級的 SQLite，檔案會自動生成在專案目錄下
SQLALCHEMY_DATABASE_URL = "sqlite:///./orders.db"

# 2. 建立資料庫引擎 (Engine)
# check_same_thread=False 是 SQLite 特有設定，允許 FastAPI 的非同步多執行緒存取
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# 3. 建立 Session 工廠，每次有請求進來時，會用它產生一個資料庫連線 (Session)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. 建立基礎類別 (Base)，之後我們所有的資料表模型都會繼承它
Base = declarative_base()

# 5. 建立一個依賴函式 (Dependency)，確保每次 API 呼叫完畢後會自動關閉資料庫連線，避免資源佔用
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()