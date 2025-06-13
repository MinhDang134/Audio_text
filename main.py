import os
import shutil
import google.generativeai as genai
from fastapi import FastAPI, File, UploadFile, Request, HTTPException
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
    if not GOOGLE_API_KEY:
        raise ValueError("Không tìm thấy GOOGLE_API_KEY trong file .env")
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    print("Đã cấu hình Google API thành công.")
except Exception as e:
    print(f"LỖI CẤU HÌNH: {e}")
    model = None

prompt_instructions = """
Bạn là một trợ lý phân tích chuyên nghiệp. Hãy nghe kỹ file âm thanh được cung cấp và trả về một bản báo cáo chi tiết với các mục sau, định dạng bằng Markdown:

### 1. Tóm tắt tổng quan
Nội dung chính của cuộc đối thoại là gì? (từ 3-5 câu).

"""


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):

    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/analyze")
async def analyze_audio(audio_file: UploadFile = File(...)):
    if model is None:
        raise HTTPException(status_code=500, detail="Mô hình AI chưa được khởi tạo do lỗi cấu hình.")

    temp_file_path = f"temp_{audio_file.filename}"
    try:

        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)

        print(f"Đang chuẩn bị tải lên file: {audio_file.filename}...")

        gemini_file = genai.upload_file(path=temp_file_path)
        print(f"Đã tải file thành công! Bắt đầu phân tích...")


        response = model.generate_content([gemini_file, prompt_instructions])

        print("--- Phân tích hoàn tất! ---")
        return {"report": response.text}

    except Exception as e:
        print(f"Đã xảy ra lỗi trong quá trình phân tích: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        await audio_file.close()