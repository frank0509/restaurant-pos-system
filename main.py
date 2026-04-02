import asyncio
import os
import json
import datetime
import logging
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, Query, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import models
from database import engine, get_db, SessionLocal

# ==========================================
# 📊 專業日誌系統 (Logging) 設定
# ==========================================
logger = logging.getLogger("OrderSystem")
logger.setLevel(logging.INFO)
formatter = logging.Formatter(fmt="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
file_handler = RotatingFileHandler("system.log", maxBytes=1024*1024, backupCount=5, encoding="utf-8")
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)

models.Base.metadata.create_all(bind=engine)
app = FastAPI()
templates = Jinja2Templates(directory="templates")
current_session_seq = 0 

# ==========================================
# 🧹 背景自動清理任務
# ==========================================
async def auto_clean_expired_qr():
    while True:
        await asyncio.sleep(600)  
        try:
            db = SessionLocal()
            now = datetime.datetime.now()
            expired_records = db.query(models.ActiveToken).filter(models.ActiveToken.expiry_time < now).all()
            for record in expired_records:
                file_path = f"static/qr_{record.table_id}.png"
                if os.path.exists(file_path): os.remove(file_path)
                db.delete(record)
            db.commit()
            db.close()
        except Exception as e:
            logger.error(f"⚠️ [背景清理] 發生異常: {e}")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(auto_clean_expired_qr())
    logger.info("🚀 系統啟動成功：背景清理任務已上線！")

# ==========================================
# 📡 WebSocket 管理器
# ==========================================
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# ==========================================
# 🌐 網頁路由
# ==========================================
@app.get("/order/{table_id}")
async def customer_page(request: Request, table_id: str, token: str = Query(None), db: Session = Depends(get_db)):
    if not token: raise HTTPException(status_code=403, detail="缺少安全憑證")
    record = db.query(models.ActiveToken).filter(models.ActiveToken.table_id == table_id, models.ActiveToken.token == token).first()
    if not record or datetime.datetime.now() > record.expiry_time:
        raise HTTPException(status_code=403, detail="QR Code 已過期，請重新掃描。")
    return templates.TemplateResponse(request=request, name="customer.html", context={"table_id": table_id, "token": token})

@app.get("/kitchen")
async def kitchen_page(request: Request):
    return templates.TemplateResponse(request=request, name="kitchen.html")


# ==========================================
# ⚙️ API 接口
# ==========================================

# 💡 新增：客人查詢自己「已送出」的餐點
@app.get("/api/my_orders")
def get_my_orders(table_id: str, token: str, db: Session = Depends(get_db)):
    # 驗證 Token 是否合法
    valid = db.query(models.ActiveToken).filter(models.ActiveToken.table_id == table_id, models.ActiveToken.token == token).first()
    if not valid: raise HTTPException(status_code=403, detail="無效操作")
    
    # 抓取該桌今天的訂單
    today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    orders = db.query(models.OrderRecord).filter(
        models.OrderRecord.table_id == table_id,
        models.OrderRecord.created_at >= today_start
    ).all()
    
    items = []
    total = 0
    for o in orders:
        items.extend(json.loads(o.items_json))
        total += o.total_price
    return {"items": items, "total": total}

@app.get("/api/active_orders")
def get_active_orders(db: Session = Depends(get_db)):
    orders = db.query(models.OrderRecord).filter(models.OrderRecord.status.in_(["pending", "cooking"])).order_by(models.OrderRecord.id.asc()).all()
    return [{"id": o.id, "seq": o.session_seq, "table": o.table_id, "items": json.loads(o.items_json), "total": o.total_price, "status": o.status} for o in orders]

# 💡 修改：歷史紀錄加入「日期篩選」
@app.get("/api/history_orders")
def get_history_orders(target_date: str = Query(None), db: Session = Depends(get_db)):
    # 若沒有提供日期，預設抓取「今天」
    if not target_date:
        target_date = datetime.date.today().strftime("%Y-%m-%d")
        
    try:
        dt = datetime.datetime.strptime(target_date, "%Y-%m-%d")
    except:
        dt = datetime.datetime.now()
        
    start_of_day = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + datetime.timedelta(days=1)
    
    # 抓出當天的所有訂單
    orders = db.query(models.OrderRecord).filter(
        models.OrderRecord.created_at >= start_of_day,
        models.OrderRecord.created_at < end_of_day
    ).order_by(models.OrderRecord.id.desc()).all()
    
    return [{
        "id": o.id, "seq": o.session_seq, "table": o.table_id, 
        "items": json.loads(o.items_json), "total": o.total_price, "status": o.status,
        "time": o.created_at.strftime("%H:%M:%S")
    } for o in orders]

@app.post("/api/update_status/{order_id}")
async def update_status(order_id: int, status: str = Query(...), db: Session = Depends(get_db)):
    order = db.query(models.OrderRecord).filter(models.OrderRecord.id == order_id).first()
    if order:
        order.status = status
        db.commit()
        await manager.broadcast({"type": "update", "id": order_id, "status": status})
    return {"status": "success"}

@app.post("/api/submit_order")
async def submit_order(data: dict, db: Session = Depends(get_db)):
    global current_session_seq
    valid = db.query(models.ActiveToken).filter(models.ActiveToken.table_id == data.get('table_id'), models.ActiveToken.token == data.get('token')).first()
    if not valid or datetime.datetime.now() > valid.expiry_time:
        raise HTTPException(status_code=403, detail="訂單送出失敗：QR Code 已過期")

    current_session_seq += 1 
    new_order = models.OrderRecord(
        session_seq=current_session_seq,
        table_id=data['table_id'],
        items_json=json.dumps(data['items'], ensure_ascii=False),
        total_price=data['total']
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order) 
    
    logger.info(f"💰 [新訂單] 流水號: #{new_order.session_seq} | 桌號: {data['table_id']} | 總計: ${data['total']}")
    
    await manager.broadcast({
        "type": "new",
        "data": {"id": new_order.id, "seq": new_order.session_seq, "table": data['table_id'], "items": data['items'], "total": data['total'], "status": "pending"}
    })
    return {"status": "success"}

@app.websocket("/ws/kitchen")
async def kitchen_socket(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)