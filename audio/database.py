import logging
import os
from contextlib import contextmanager
from typing import Generator, Optional
from dotenv import load_dotenv
from sqlalchemy.engine import Engine
from sqlmodel import create_engine, Session, SQLModel

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logging.error("Biến môi trường DATABASE_URL chưa được cấu hình. Vui lòng đặt nó.")
    raise ValueError("DATABASE_URL môi trường là bắt buộc.")

engine: Engine = create_engine(DATABASE_URL)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    print("Đã tạo tất cả các bảng trong cơ sở dữ liệu.")

@contextmanager
def get_session(engine_to_use: Optional[Engine] = None) -> Generator[Session, None, None]:
    current_engine = engine_to_use if engine_to_use is not None else engine
    session = Session(current_engine)
    try:
        yield session
        session.commit()
        logging.info("kết nối session thành công ")
    except Exception as e:
        session.rollback()
        logging.error(f"database xảy ra lỗi lên sẽ rollback lại : {e}", exc_info=True)
        raise
    finally:
        session.close()
        logging.info("Session closed.")