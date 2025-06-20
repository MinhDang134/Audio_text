import multiprocessing
import os
import uuid
import shutil
import time
import logging
from typing import Dict, Any, Optional

import google.generativeai as genai
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from audio.models import audiot, history
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(processName)s - %(message)s')



def audio_analysis_worker(
        job_queue: multiprocessing.Queue,
        result_queue: multiprocessing.Queue,
        shared_analysis_jobs: Dict[str, Dict[str, Any]],
        gemini_api_key: str,
        prompt_inst: str,
        db_url: str
):
    logging.info("Worker sẵn sàng nhận công việc.")
    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    model_hai = genai.GenerativeModel(model_name="gemini-2.0-flash")


    engine = create_engine(db_url)


    while True:
        try:
            job_data = job_queue.get()
            if job_data is None:
                logging.info("Nhận tín hiệu dừng, worker kết thúc.")
                break

            job_id = job_data["job_id"]
            audio_file_info = job_data["audio_file_info"]
            ai_model = job_data["ai_model"]
            temp_file_path = job_data["temp_file_path"]


            shared_analysis_jobs[job_id]["status"] = "PROCESSING"
            logging.info(f"[{job_id}] Bắt đầu phân tích file: {audio_file_info['filename']}")

            status = "Không thành công"
            report_text = ""
            error_message = None

            try:
                mime_type = audio_file_info["mime_type"]
                filename = audio_file_info["filename"]

                gemini_file = genai.upload_file(path=temp_file_path, mime_type=mime_type)

                response = None
                if ai_model == "model_b":
                    response = model_hai.generate_content([gemini_file, prompt_inst])
                elif ai_model == "model_a":
                    response = model.generate_content([gemini_file, prompt_inst])
                else:
                    raise ValueError(f"Mô hình AI không hợp lệ: {ai_model}")

                report_text = response.text
                status = "Thành Công"

            except Exception as e:
                logging.error(f"[{job_id}] Lỗi xử lý phân tích: {e}")
                error_message = str(e)
                shared_analysis_jobs[job_id]["status"] = "AI_PROCESSING_FAILED"
                shared_analysis_jobs[job_id]["error"] = error_message


            finally:
                if os.path.exists(temp_file_path):
                    try:
                        os.remove(temp_file_path)
                        logging.info(f"[{job_id}] Đã xóa file tạm: {temp_file_path}")
                    except OSError as e:
                        logging.warning(f"[{job_id}] Lỗi khi xóa file tạm {temp_file_path}: {e}")

                result_queue.put({
                    "job_id": str(job_id),
                    "status": status,
                    "report": report_text,
                    "source_file": filename,
                    "model_ai": ai_model,
                    "error": error_message
                })
                logging.info(f"[{job_id}] Đã gửi kết quả về hàng đợi.")

        except Exception as e:
            logging.critical(f"Lỗi không mong muốn trong vòng lặp worker: {e}")
            break



def result_monitor(
        result_queue: multiprocessing.Queue,
        shared_analysis_jobs: Dict[str, Dict[str, Any]],
        db_url: str,
        webhook_url: Optional[str]
):
    logging.info("Monitor sẵn sàng theo dõi kết quả.")
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    while True:
        try:
            result = result_queue.get()
            if result is None:
                logging.info("Nhận tín hiệu dừng, monitor kết thúc.")
                break

            job_id = result["job_id"]
            status = result["status"]
            report = result["report"]
            source_file = result["source_file"]
            model_ai = result["model_ai"]
            error_message = result.get("error")

            logging.info(f"[{job_id}] Nhận kết quả từ worker: {status}")

            shared_analysis_jobs[job_id]["status"] = status
            shared_analysis_jobs[job_id]["report"] = report
            if error_message:
                shared_analysis_jobs[job_id]["error"] = error_message

            try:
                with SessionLocal() as session:
                    analysis_result = audiot(
                        job_id=uuid.UUID(job_id),
                        status=status,
                        source_file=source_file,
                        report=report,
                        model_ai=model_ai
                    )
                    analysis_result_history = history(
                        job_id=uuid.UUID(job_id),
                        status=status,
                        source_file=source_file,
                        report=report,
                        model_ai=model_ai
                    )
                    session.add(analysis_result)
                    session.add(analysis_result_history)
                    session.commit()
                logging.info(f"[{job_id}] Đã lưu kết quả vào cơ sở dữ liệu.")
            except Exception as db_e:
                logging.error(f"[{job_id}] Lỗi khi lưu vào cơ sở dữ liệu: {db_e}")
                shared_analysis_jobs[job_id]["status"] = "DB_SAVE_FAILED"
                shared_analysis_jobs[job_id]["error"] = str(db_e)

            if webhook_url:
                webhook_payload = {
                    "job_id": job_id,
                    "source_file": source_file,
                    "status": status,
                    "report": report,
                    "model_ai": model_ai,
                    "error": error_message
                }
                try:
                    requests.post(webhook_url, json=webhook_payload, timeout=10)
                    logging.info(f"[{job_id}] Webhook gửi thành công.")
                except Exception as webhook_e:
                    logging.error(f"[{job_id}] Lỗi khi gửi webhook: {webhook_e}")
                    shared_analysis_jobs[job_id]["webhook_status"] = "FAILED"
                    shared_analysis_jobs[job_id]["webhook_error"] = str(webhook_e)
            else:
                logging.info(f"[{job_id}] Không có WEBHOOK_URL, bỏ qua gửi webhook.")

        except Exception as e:
            logging.critical(f"Lỗi không mong muốn trong vòng lặp monitor: {e}")
            break