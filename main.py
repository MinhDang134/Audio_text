import os
import shutil
import requests
import google.generativeai as genai
from fastapi import FastAPI, File, UploadFile, Request, HTTPException, BackgroundTasks, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from sqlalchemy import select
import uuid
import json
# {
#   "conversation": [
#     {
#       "speaker": "Speaker 1",
#       "timestamp": "HH:MM:SS",
#       "utterance": "Câu nói của khách hàng."
#     },
#     {
#       "speaker": "Speaker 2",
#       "timestamp": "HH:MM:SS",
#       "utterance": "Câu nói của nhân viên chăm sóc khách hàng."
#     },
#     // ... các câu nói khác
#   ],
#   "summary": "Tóm tắt cuộc hội thoại (nếu có yêu cầu thêm)",
#   "sentiment": "Phân tích cảm xúc chung (nếu có yêu cầu thêm)"
# }


from audio.database import get_session, engine
from audio.models import audiot, history

load_dotenv()
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
analysis_jobs = {}

try:
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    if not GOOGLE_API_KEY:
        raise ValueError("Không tìm thấy GOOGLE_API_KEY trong file .env")
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    model_hai = genai.GenerativeModel(model_name="gemini-2.0-flash")

    print("Đã cấu hình Google API thành công.")
except Exception as e:
    print(f"Lỗi cấu hình như sau: {e}")
    model = None
    model_hai = None

prompt_instructions = """
*câu hỏi 1:* viết chi tiết toàn bộ cuộc hội thoại ra , chia ra người khách hàng là speaker 1 , còn nhân viên chăm sóc khách hàng là speaker 2 , phân tích chuẩn từng câu từng chữ nhất có thể , và hiển thị luôn thời gian đối tượng nói từng câu
"""

def send_to_webhook(payload: dict, job_id: str):
    try:
        if not WEBHOOK_URL:
            print(f"[{job_id}] Chưa cấu hình WEBHOOK_URL, bỏ qua việc gửi.")
            analysis_jobs[job_id] = {"status": "WEBHOOK_SKIPPED"}
            return

        print(f"[{job_id}] Đang gửi kết quả đến webhook: {WEBHOOK_URL}")
        response = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        print(f"[{job_id}] Gửi webhook thành công!")
        analysis_jobs[job_id] = {"status": "WEBHOOK_SENT"}
    except requests.exceptions.RequestException as e:
        print(f"[{job_id}] Lỗi khi gửi webhook: {e}")
        analysis_jobs[job_id] = {"status": "WEBHOOK_FAILED", "error": str(e)}


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/analyze")
async def analyze_audio(background_tasks: BackgroundTasks, ai_model: str = Form(...),audio_file: UploadFile = File(...)):
    if model is None:
        raise HTTPException(status_code=500, detail="Mô hình AI chưa được khởi tạo.")
    if not audio_file:
        raise HTTPException(status_code=500, detail="Không có file audio.")
    if not ai_model:
        raise HTTPException(status_code=500, detail="Chưa chọn mô hình AI.")


    job_id = uuid.uuid4()
    analysis_jobs[str(job_id)] = {"status": "PROCESSING", "report": None}

    temp_file_path = f"temp_{job_id}_{audio_file.filename}"

    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
        if audio_file.content_type is None:
            file_extension = os.path.splitext(audio_file.filename)[1].lower()
            if file_extension == ".mp3":
                mime_type = "audio/mpeg"
            elif file_extension == ".wav":
                mime_type = "audio/wav"
            elif file_extension == ".aac":
                mime_type = "audio/aac"
            else:
                raise HTTPException(status_code=400,
                                    detail=f"Không thể xác định MIME type cho file {audio_file.filename}. Vui lòng tải lên file audio chuẩn hoặc báo cáo lỗi.")
        else:
            mime_type = audio_file.content_type

        gemini_file = genai.upload_file(path=temp_file_path, mime_type=mime_type)

        if ai_model == "model_b":
            response = model_hai.generate_content([gemini_file, prompt_instructions])
        elif ai_model == "model_a":
            response = model.generate_content([gemini_file, prompt_instructions])
        else:
            raise HTTPException(status_code=500, detail="Chương trình lỗi rồi ")

        report_text = response.text

        analysis_jobs[str(job_id)]["status"] = "Thành Công"
        analysis_jobs[str(job_id)]["report"] = report_text


        try:
            with get_session() as session:
                analysis_result = audiot(
                    job_id=job_id,
                    status = analysis_jobs[str(job_id)]["status"],
                    source_file=audio_file.filename,
                    report=report_text,
                    model_ai=ai_model
                )
                analysis_result_history = history(
                    job_id=job_id,
                    status=analysis_jobs[str(job_id)]["status"],
                    source_file=audio_file.filename,
                    report=report_text,
                    model_ai=ai_model
                )
                session.add(analysis_result)
                session.add(analysis_result_history)
        except Exception as db_e:
            print(f"[{job_id}] Lỗi khi lưu vào cơ sở dữ liệu: {db_e}")
            analysis_jobs[str(job_id)]["status"] = "DB_SAVE_FAILED"
            analysis_jobs[str(job_id)]["error"] = str(db_e)

        print(f"[{job_id}] Phân tích hoàn tất! Bắt đầu gửi webhook trong nền.")
        webhook_payload = {
            "job_id": str(job_id),
            "source_file": audio_file.filename,
            "status" : analysis_jobs[str(job_id)]["status"],
            "report": report_text,
            "model_ai": ai_model
        }
        background_tasks.add_task(send_to_webhook, webhook_payload, str(job_id))  # Truyền str(job_id)

        return {"job_id": str(job_id), "report": report_text}


    except Exception as e:
        print(f"[{job_id}] Lỗi xử lý: {e}")
        analysis_jobs[str(job_id)] = {"status": "Không thành công", "error": str(e)}
        with get_session() as session:
            analysis_result = audiot(
                job_id=job_id,
                status=analysis_jobs[str(job_id)]["status"],
                source_file=audio_file.filename,
                report= " ",
                model_ai=ai_model
            )
            analysis_result_history = history(
                job_id=job_id,
                status=analysis_jobs[str(job_id)]["status"],
                source_file=audio_file.filename,
                report=" ",
                model_ai=ai_model
            )

            session.add(analysis_result)
            session.add(analysis_result_history)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        await audio_file.close()



@app.get("/status/{job_id}")
def get_job_status(job_id: str):
    query = select(audiot).where(audiot.job_id == job_id)
    with get_session() as session:
        result = session.execute(query).first()
        if result:
            for row in result:
                ketqua ={
                    "job_id": row.job_id,
                    "source_file": row.source_file,
                    "status": row.status,
                    "report": row.report,
                    "model_ai": row.model_ai
                }
                return ketqua
        else:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy job_id: {job_id}")

@app.get("/history/{job_id}")
def get_job_history(job_id:str):
    query = select(history).where(history.job_id == job_id)
    with get_session() as session:
        result = session.execute(query).first()
        if result:
            for row in result:
                ketqua ={
                    "job_id": row.job_id,
                    "source_file": row.source_file,
                    "status": row.status,
                    "report": row.report,
                    "model_ai": row.model_ai
                }
                return ketqua
        else:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy job_id: {job_id}")

@app.get("/history_summary")
def get_history_summary():
    query = select(history.job_id, history.source_file).order_by(history.job_id.desc()).limit(10)
    with get_session() as session:
        results = session.execute(query).fetchall()
        history_list = [{"job_id": r.job_id, "source_file": r.source_file} for r in results]
        return history_list

