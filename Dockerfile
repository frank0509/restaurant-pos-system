# 1. 使用輕量級的 Python 3.10 作為基底環境
FROM python:3.10-slim

# 2. 設定容器內部的工作目錄為 /app
WORKDIR /app

# 3. 先複製 requirements.txt 進去並安裝套件 (利用快取機制加速)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 把目前資料夾下的所有程式碼複製進容器的 /app 裡
COPY . .

# 5. 宣告這個容器會使用 8000 Port
EXPOSE 8000

# 6. 容器啟動時，預設執行的指令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]