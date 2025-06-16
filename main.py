import os
import shutil
import requests
import google.generativeai as genai
from fastapi import FastAPI, File, UploadFile, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv


load_dotenv()
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

try:
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    if not GOOGLE_API_KEY:
        raise ValueError("Không tìm thấy GOOGLE_API_KEY trong file .env")
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    print("Đã cấu hình Google API thành công.")
except Exception as e:
    print(f"LỖI CẤU HÌNH: {e}")
    model = None


prompt_instructions = "*câu hỏi 1 :* viết chi tiết toàn bộ cuộc hội thoại ra  "



def send_to_webhook(payload: dict):

    try:
        if not WEBHOOK_URL:
            print("Chưa cấu hình WEBHOOK_URL, bỏ qua việc gửi.")
            return

        print(f"Đang gửi kết quả đến webhook: {WEBHOOK_URL}")
        response = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        print("Gửi webhook thành công!")
    except requests.exceptions.RequestException as e:
        print(f"Lỗi khi gửi webhook: {e}")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/analyze")
async def analyze_audio(background_tasks: BackgroundTasks, audio_file: UploadFile = File(...)):
    if model is None:
        raise HTTPException(status_code=500, detail="Mô hình AI chưa được khởi tạo.")
    if not audio_file :
        raise HTTPException(status_code=500,detail="không có video mp3 ")
    temp_file_path = f"temp_{audio_file.filename}"
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
        gemini_file = genai.upload_file(path=temp_file_path)
        response = model.generate_content([gemini_file, prompt_instructions])
        report_text = response.text
        print("--- Phân tích hoàn tất! Bắt đầu gửi webhook trong nền ---")
        webhook_payload = {
            "source_file": audio_file.filename,
            "report": report_text
        }
        background_tasks.add_task(send_to_webhook, webhook_payload)
        return {"report": report_text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        await audio_file.close()