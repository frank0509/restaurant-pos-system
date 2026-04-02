import qrcode
import os
import uuid
import datetime
from database import SessionLocal, engine
import models

# 確保資料表結構已經建立在資料庫中
models.Base.metadata.create_all(bind=engine)

# ⚠️ 注意：這裡一定要換成你電腦(本機)的真實 IPv4 位址
MY_IP = "192.168.1.109" 
PORT = "8000"

def generate_for_table():
    db = SessionLocal() # 開啟資料庫連線
    
    # 1. 透過終端機讓使用者輸入要開的桌號
    table = input("👉 請輸入要開啟的桌號 (例如 A1, B2): ").strip()
    if not table:
        print("❌ 桌號不能為空！")
        return

    # 2. 生成安全憑證 (Token) 與過期時間
    token = str(uuid.uuid4())[:8] # 利用 uuid 產生隨機亂碼，取前 8 碼即可
    expiry = datetime.datetime.now() + datetime.timedelta(hours=2) # 設定時效為 2 小時後

    # 3. 清除該桌「舊的」Token，確保一桌只有一個有效的 QR Code
    db.query(models.ActiveToken).filter(models.ActiveToken.table_id == table).delete()
    
    # 4. 將「新的」Token 存入資料庫
    new_token = models.ActiveToken(table_id=table, token=token, expiry_time=expiry)
    db.add(new_token)
    db.commit()

    # 5. 組合出帶有參數的專屬網址 (例如: http://192.168.1.100:8000/order/A1?token=abcd1234)
    url = f"http://{MY_IP}:{PORT}/order/{table}?token={token}"

    # 6. 確認 static 資料夾存在，並生成圖片
    if not os.path.exists("static"): 
        os.makedirs("static")
        
    img = qrcode.make(url)
    filename = f"static/qr_{table}.png"
    img.save(filename)

    # 印出成功訊息
    print(f"\n✅ 桌號 {table} 專屬 QR Code 生成完畢！")
    print(f"🔗 掃碼網址: {url}")
    print(f"⏰ 有效期限至: {expiry.strftime('%Y-%m-%d %H:%M:%S')} (2小時內有效)")
    print(f"📁 圖片已存檔於: {filename}\n")
    
    db.close() # 關閉資料庫連線

if __name__ == "__main__":
    generate_for_table()