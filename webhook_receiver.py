from fastapi import FastAPI, Request

app = FastAPI()


@app.post("/webhook-listener")
async def receive_webhook(request: Request):
    data = await request.json()
    print(" WEBHOOK ĐÃ NHẬN ĐƯỢC DỮ LIỆU! ")
    source_file = data.get("source_file", "Không rõ")
    print(f"File nguồn: {source_file}")
    report = data.get("report", "Không có nội dung.")
    print("--- Nội dung báo cáo ---")
    print(report)
    print("===================================\n")
    return {"status": "success", "message": "Dữ liệu đã được nhận."}