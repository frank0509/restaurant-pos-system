from sqlalchemy import Column, Integer, String, DateTime
import datetime
from database import Base

class OrderRecord(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)         # 資料庫絕對 ID
    session_seq = Column(Integer, default=1)                   # 💡 每次系統重開從 1 開始的單號
    table_id = Column(String, index=True)      
    items_json = Column(String)                
    total_price = Column(Integer)              
    status = Column(String, default="pending")                 # 狀態: pending(待接單), cooking(製作中), done(已完成)
    created_at = Column(DateTime, default=datetime.datetime.now)

class ActiveToken(Base):
    __tablename__ = "active_tokens"
    id = Column(Integer, primary_key=True, index=True)
    table_id = Column(String, index=True)
    token = Column(String, unique=True, index=True)
    expiry_time = Column(DateTime)