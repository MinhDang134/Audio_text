# import asyncio
#
# import uvicorn
#
# from main import get_job_status
# from fastapi import HTTPException
#
# def minhdangtext():
#     job_id  = "793f39df-1529-4acb-919d-f8c742dff9f6"
#     try:
#         minhdang_chill = get_job_status(job_id)
#         if minhdang_chill:
#             print(f"Co du lieu la{minhdang_chill}")
#     except Exception as e:
#         raise HTTPException(status_code=404, detail=f"bị lỗi sau {e}")
#
# if __name__ == '__main__':
#     minhdangtext()
