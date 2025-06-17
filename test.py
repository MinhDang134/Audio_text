# import asyncio
#
# import uvicorn
#
# from main import get_job_status
# from fastapi import HTTPException
#
# def minhdangtext():
#     job_id  = "7e9dc794-2642-4a17-8429-cb7ceb07454b"
#     try:
#         minhdang_chill = get_job_status(job_id)
#         if minhdang_chill:
#             print(f"Co du lieu la{minhdang_chill}")
#     except Exception as e:
#         raise HTTPException(status_code=404, detail=f"bị lỗi sau {e}")
#
# if __name__ == '__main__':
#     minhdangtext()
