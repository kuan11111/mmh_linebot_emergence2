# config.py
import os

hospid = None
empno = None
current_mode = None
call_position_counts = {"行政": 0, "護理": 0, "醫師": 0, "醫技": 0}
green_one_position_counts = {"行政": 0, "護理": 0, "醫師": 0, "醫技": 0}
green_two_position_counts = {"行政": 0, "護理": 0, "醫師": 0, "醫技": 0}
is_reset_done = False  # 初始化標誌
scheduled_reset_timer = None  # 初始化計時器變量


call_user_reports = {}
call_employee_check_in = set()
green_one_employee_check_in = set()  # 綠色一級報到記錄
green_two_employee_check_in = set()  # 綠色二級報到記錄

RESET_TIME_FILE = "reset_time.txt"
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
ALLOWED_USERS = [
    "Ua60af72d20b2e3309d41f3bf6b230b3d",  # K888
    "U8a21526a6eceb8ec439fb33d4c27c0d0",  # K263
    "Uce214e8f83e0fb72b9bec5c1c7a3b815",  # K041
    "Ud80bcb870e909a295ae846d8abe9600f",  # K132
    "Uebafa6c3e1fc2bf305d38c2b1619822e",  # K034
]
