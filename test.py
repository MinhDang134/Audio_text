# import multiprocessing
# import time
# import os
#
#
#
# def tho_lam_banh(bang_don_hang, bang_banh_da_lam, ten_tho_banh, toc_do_lam_banh):
#     pid = os.getpid()
#     print(f"[{ten_tho_banh} - PID: {pid}] Đã có mặt tại xưởng, tốc độ: {toc_do_lam_banh} giây/bánh.")
#
#     while True:
#         try:
#             don_hang = bang_don_hang.get()
#
#             if don_hang is None:
#                 print(f"[{ten_tho_banh} - PID: {pid}] Nhận được tín hiệu hết việc, nghỉ ngơi thôi.")
#                 break
#
#
#             ma_don = don_hang["ma_don"]
#             loai_banh = don_hang["loai_banh"]
#             so_luong = don_hang["so_luong"]
#
#             print(f"[{ten_tho_banh} - PID: {pid}] Đang làm đơn #{ma_don}: {so_luong} cái {loai_banh}")
#
#             thoi_gian_lam = so_luong * toc_do_lam_banh
#             time.sleep(thoi_gian_lam)
#
#             ket_qua_lam_banh = f"{so_luong} cái {loai_banh} (Đơn #{ma_don})"
#             bang_banh_da_lam.put(ket_qua_lam_banh)
#             print(f"[{ten_tho_banh} - PID: {pid}] Hoàn thành: {ket_qua_lam_banh}")
#
#         except Exception as e:
#             print(f"[{ten_tho_banh} - PID: {pid}] Lỗi khi làm bánh: {e}")
#             break
#
#
#
# if __name__ == "__main__":
#     bang_don_hang = multiprocessing.Queue()
#     bang_banh_da_lam = multiprocessing.Queue()
#
#
#     cac_tho_banh = []
#     p1 = multiprocessing.Process(
#         target=tho_lam_banh,
#         args=(bang_don_hang, bang_banh_da_lam, "Anh Bếp Trưởng", 0.8)
#     )
#     cac_tho_banh.append(p1)
#     p1.start()
#
#
#     p2 = multiprocessing.Process(
#         target=tho_lam_banh,
#         args=(bang_don_hang, bang_banh_da_lam, "Chị Phụ Bếp", 1.2)
#     )
#     cac_tho_banh.append(p2)
#     p2.start()
#
#     print("\n--- Chủ cửa hàng bắt đầu nhận đơn hàng và đưa lên bảng ---")
#
#
#     danh_sach_don = [
#         {"ma_don": 1, "loai_banh": "Bánh mì ngọt", "so_luong": 5},
#         {"ma_don": 2, "loai_banh": "Bánh kem nhỏ", "so_luong": 1},
#         {"ma_don": 3, "loai_banh": "Bánh mì sandwich", "so_luong": 10},
#         {"ma_don": 4, "loai_banh": "Bánh mì ngọt", "so_luong": 3},
#         {"ma_don": 5, "loai_banh": "Bánh quy", "so_luong": 20},
#     ]
#
#     for don in danh_sach_don:
#         print(f"Chủ cửa hàng nhận đơn: #{don['ma_don']} - {don['so_luong']} cái {don['loai_banh']}")
#         bang_don_hang.put(don)
#
#
#     print("\n--- Hết đơn hàng mới, gửi tín hiệu nghỉ cho các thợ ---")
#     for _ in range(len(cac_tho_banh)):
#         bang_don_hang.put(None)
#
#
#     print("\n--- Đợi các thợ hoàn thành hết các đơn còn lại ---")
#     for th_banh in cac_tho_banh:
#         th_banh.join()
#
#
#     print("\n--- Thu thập tất cả bánh đã làm xong để giao cho khách ---")
#     tat_ca_banh_da_lam = []
#     while not bang_banh_da_lam.empty():
#         tat_ca_banh_da_lam.append(bang_banh_da_lam.get())
#
#     print("\n--- Cửa hàng đã hoàn thành các đơn: ---")
#     for banh in tat_ca_banh_da_lam:
#         print(f"- {banh}")
#
#     print("\nCửa hàng đóng cửa! Hẹn gặp lại!")