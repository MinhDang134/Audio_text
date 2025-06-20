import logging
import os
import shutil
import time
import uuid
from typing import Dict, Any, Optional
import google.generativeai as genai
import multiprocessing
from multiprocessing import Queue, Process, Manager
from fastapi import FastAPI, File, UploadFile, Request, HTTPException, BackgroundTasks, Form, APIRouter
from dotenv import load_dotenv
from sqlalchemy import select
from audio.database import get_session, engine, DATABASE_URL
from audio.models import audiot, history, session_chat, ChatMessage
from audio.service import audio_analysis_worker, result_monitor

router = APIRouter()
load_dotenv()


manager = Manager()
analysis_jobs: Dict[str, Dict[str, Any]] = manager.dict()
chat_histories ={}


job_queue: multiprocessing.Queue = multiprocessing.Queue()
result_queue: multiprocessing.Queue = multiprocessing.Queue()


workers = []
monitor_process: Optional[Process] = None
NUM_WORKERS = 4
DB_CONNECTION_STRING = DATABASE_URL

try:
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    if not GOOGLE_API_KEY:
        raise ValueError("Không tìm thấy GOOGLE_API_KEY trong file .env")
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    model_hai = genai.GenerativeModel(model_name="gemini-2.0-flash")

    logging.info("Đã cấu hình Google API thành công.")
except Exception as e:
    logging.error(f"Lỗi cấu hình như sau: {e}")
    model = None
    model_hai = None

prompt_instructions = """

Bạn là một công cụ phân tích cuộc hội thoại. Nhiệm vụ của bạn là phân tích một đoạn hội thoại được cung cấp, xác định người nói (Speaker 1 là khách hàng, Speaker 2 là nhân viên chăm sóc khách hàng), ghi lại từng câu nói một cách chính xác và kèm theo thời gian tương ứng của mỗi câu. Kết quả phải được trả về dưới định dạng JSON chuẩn. xuống dòng đàng hoàng cho tôi nhé đừng in cả một cục 

---

**Định dạng JSON mong muốn:**

```json
{
  "conversation_id": "ID_cuoc_hoi_thoai_nay",
  "speakers": {
    "speaker1_role": "customer",
    "speaker2_role": "customer_service_representative"
  },
  "dialogue": [
    {
      "speaker": "speaker1",
      "timestamp": "HH:MM:SS",
      "text": "Câu nói của speaker 1."
    },
    {
      "speaker": "speaker2",
      "timestamp": "HH:MM:SS",
      "text": "Câu nói của speaker 2."
    },
    // ... các đoạn hội thoại tiếp theo
  ]
}
"""


@router.on_event("startup")
async def startup_event():
    logging.info("Khởi động ứng dụng và các worker...")
    global monitor_process
    for i in range(NUM_WORKERS):
        p = Process(
            target=audio_analysis_worker,
            args=(job_queue, result_queue, analysis_jobs, GOOGLE_API_KEY, prompt_instructions, DB_CONNECTION_STRING)
        )
        workers.append(p)
        p.start()


    monitor_process = Process(
        target=result_monitor,
        args=(result_queue, analysis_jobs, DB_CONNECTION_STRING, WEBHOOK_URL)
    )
    monitor_process.start()


@router.on_event("shutdown")
async def shutdown_event():
    logging.info("Tắt ứng dụng và các worker...")
    for _ in range(NUM_WORKERS):
        job_queue.put(None)
    result_queue.put(None)

    for p in workers:
        p.join()
    if monitor_process:
        monitor_process.join()
    logging.info("Tất cả worker và monitor đã dừng.")
    manager.shutdown()


@router.post("/analyze")
async def analyze_audio(ai_model: str = Form(...), audio_file: UploadFile = File(...)):
    if model is None:
        raise HTTPException(status_code=500, detail="Mô hình AI chưa được khởi tạo.")
    if not audio_file:
        raise HTTPException(status_code=500, detail="Không có file audio.")
    if not ai_model:
        raise HTTPException(status_code=500, detail="Chưa chọn mô hình AI.")

    job_id = uuid.uuid4()
    analysis_jobs[str(job_id)] = {"status": "QUEUED", "report": None, "model_ai": ai_model, "source_file": audio_file.filename}

    temp_dir = "temp_audio_files"
    os.makedirs(temp_dir, exist_ok=True)
    temp_file_path = os.path.join(temp_dir, f"{job_id}_{audio_file.filename}")

    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)

        mime_type = audio_file.content_type
        if mime_type is None:
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

        job_queue.put({
            "job_id": str(job_id),
            "audio_file_info": {
                "filename": audio_file.filename,
                "mime_type": mime_type
            },
            "ai_model": ai_model,
            "temp_file_path": temp_file_path
        })
        logging.info(f"[{job_id}] Đã thêm công việc vào hàng đợi.")

        return {"job_id": str(job_id), "status": "QUEUED", "message": "Yêu cầu của bạn đang được xử lý."}

    except Exception as e:
        logging.error(f"[{job_id}] Lỗi khi xử lý yêu cầu API: {e}")
        analysis_jobs[str(job_id)]["status"] = "API_ERROR"
        analysis_jobs[str(job_id)]["error"] = str(e)
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(status_code=500, detail=f"Lỗi khi nhận yêu cầu: {str(e)}")
    finally:
        await audio_file.close()

@router.get("/status/{job_id}")
async def check_analysis_status(job_id: str):
    job_status = analysis_jobs.get(job_id)
    if not job_status:

        query = select(audiot).where(audiot.job_id == uuid.UUID(job_id))
        with get_session() as session:
            result = session.execute(query).scalars().first()
            if result:
                ketqua = {
                    "job_id": str(result.job_id),
                    "source_file": result.source_file,
                    "status": result.status,
                    "report": result.report,
                    "model_ai": result.model_ai
                }
                return ketqua
            else:
                raise HTTPException(status_code=404, detail="Không tìm thấy Job ID.")

    return job_status

@router.get("/history/{job_id}")
def get_job_history(job_id:str):
    query = select(history).where(history.job_id == uuid.UUID(job_id))
    with get_session() as session:
        result = session.execute(query).scalars().first()
        if result:
            ketqua ={
                "job_id": str(result.job_id),
                "source_file": result.source_file,
                "status": result.status,
                "report": result.report,
                "model_ai": result.model_ai
            }
            return ketqua
        else:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy job_id: {job_id}")

@router.get("/history_summary")
def get_history_summary():
    query = select(history.job_id, history.source_file).order_by(history.job_id.desc()).limit(10)
    with get_session() as session:
        results = session.execute(query).fetchall()
        history_list = [{"job_id": str(r.job_id), "source_file": r.source_file} for r in results]
        return history_list


@router.delete("/delete/{job_id}")
def delete_job(job_id: str):
    with get_session() as session:
        history_to_delete = session.query(history).filter(history.job_id == uuid.UUID(job_id)).first()
        if history_to_delete:
            session.delete(history_to_delete)
            session.commit()
            logging.info(f"Xóa thành công {job_id}")
            return {"message": f"Job {job_id} đã được xóa thành công."}
        else:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy job_id: {job_id} để xóa.")


async def send_to_webhook(payload: dict, job_id: str):
    try:
        if not WEBHOOK_URL:
            logging.info(f"[{job_id}] Chưa cấu hình WEBHOOK_URL, bỏ qua việc gửi.")

            return

        logging.info(f"[{job_id}] Đang gửi kết quả đến webhook: {WEBHOOK_URL}")

        logging.info(f"[{job_id}] Gửi webhook thành công!")
    except Exception as e:
        logging.error(f"[{job_id}] Lỗi khi gửi webhook: {e}")

@router.post("/chat")
async def chat_with_gemini(request: Request):
    if model_hai is None:
        raise HTTPException(status_code=500, detail="Mô hình Gemini Chatbot chưa được khởi tạo.")
    data = await request.json()
    user_message = data.get('message')
    session_id = data.get('session_id')

    if not user_message:
        raise HTTPException(status_code=400, detail="Vui lòng cung cấp tin nhắn.")

    current_chat_session_obj = None
    loaded_history_for_gemini = []

    if not session_id:
        session_id = str(uuid.uuid4())
        logging.info(f"[{session_id}] Tạo phiên trò chuyện mới (không có ID được cung cấp).")

        try:
            with get_session() as session_db:
                new_chat_session_entry = session_chat(session_id=session_id)
                session_db.add(new_chat_session_entry)
                session_db.commit()
                session_db.refresh(new_chat_session_entry)
        except Exception as e:
            logging.error(f"[{session_id}] Lỗi khi lưu session_id mới vào DB: {e}")
            raise HTTPException(status_code=500, detail=f"Lỗi hệ thống khi tạo phiên mới: {e}")


    else:

        if session_id in chat_histories:
            current_chat_session_obj = chat_histories[session_id]
            logging.info(f"[{session_id}] Tải lại phiên trò chuyện từ bộ nhớ.")


        else:
            try:
                with get_session() as session_db:
                    db_session_entry = session_db.query(session_chat).filter(
                        session_chat.session_id == session_id).first()

                    if db_session_entry:

                        logging.info(f"[{session_id}] Tìm thấy phiên trong DB, tải lịch sử tin nhắn.")
                        messages = session_db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(
                            ChatMessage.timestamp).all()


                        for msg in messages:

                            role = "user" if msg.sender == "user" else "model"
                            loaded_history_for_gemini.append({
                                "role": role,
                                "parts": [msg.message_text]
                            })


                        chat_histories[session_id] = model_hai.start_chat(history=loaded_history_for_gemini)
                        current_chat_session_obj = chat_histories[session_id]
                        logging.info(f"[{session_id}] Đã khởi tạo lại chat object với lịch sử từ DB.")

                    else:
                        logging.info(f"[{session_id}] ID không tồn tại trong DB, tạo phiên mới với ID đã cung cấp.")

                        try:
                            with get_session() as session_db_new:
                                new_chat_session_entry = session_chat(session_id=session_id)
                                session_db_new.add(new_chat_session_entry)
                                session_db_new.commit()
                                session_db_new.refresh(new_chat_session_entry)
                            chat_histories[session_id] = model_hai.start_chat(history=[])
                            current_chat_session_obj = chat_histories[session_id]
                        except Exception as e:
                            logging.error(f"[{session_id}] Lỗi khi lưu session_id mới (không tìm thấy) vào DB: {e}")
                            raise HTTPException(status_code=500, detail=f"Lỗi hệ thống khi tạo phiên mới: {e}")
            except Exception as e:
                logging.error(f"[{session_id}] Lỗi khi kiểm tra/tạo session_id trong DB: {e}")
                raise HTTPException(status_code=500, detail=f"Lỗi hệ thống khi tìm kiếm/tạo phiên: {e}")


    if current_chat_session_obj is None:
        raise HTTPException(status_code=500, detail="Không thể khởi tạo phiên trò chuyện.")


    try:
        with get_session() as session_db:
            user_msg_entry = ChatMessage(
                session_id=session_id,
                sender="user",
                message_text=user_message,
                timestamp=time.time()
            )
            session_db.add(user_msg_entry)
            session_db.commit() # Commit ngay để tin nhắn người dùng được lưu

        response = current_chat_session_obj.send_message(user_message)
        bot_response = response.text

        with get_session() as session_db:
            bot_msg_entry = ChatMessage(
                session_id=session_id,
                sender="bot",
                message_text=bot_response,
                timestamp=time.time()
            )
            session_db.add(bot_msg_entry)
            session_db.commit()

        return {"response": bot_response, "session_id": session_id}

    except Exception as e:
        logging.error(f"[{session_id}] Lỗi khi gọi Gemini Chatbot API hoặc lưu tin nhắn: {e}")
        raise HTTPException(status_code=500, detail=f"Có lỗi xảy ra khi xử lý yêu cầu: {e}")