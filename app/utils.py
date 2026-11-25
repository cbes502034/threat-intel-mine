"""小工具：時間、計時裝飾器、問題清理。"""
from datetime import datetime, timezone, timedelta
from functools import wraps
from time import time
from fastapi import HTTPException

def ISO8601_TW_now():
    """回傳台灣時間（UTC+8）的 ISO 8601 字串，精度到秒。"""
    tw_tz = timezone(timedelta(hours=8))
    tw_iso_time = datetime.now(tw_tz).isoformat(timespec='seconds')
    return tw_iso_time # 輸出範例: 2026-11-22T02:12:00+08:00

def execute_time(func):
    """計時裝飾器（目前沒有被啟用使用）。
    注意：time_out 只有宣告型別、從未被賦值，真的使用時會出錯；用之前要先補上 time_out = end - start。
    """
    @wraps(func)
    def wrap(*args, **kwargs) -> tuple:
        time_out: float
        start = time()
        response = func(*args, **kwargs)
        end = time()
        if response is None: return time_out
        return response, time_out
    return wrap


def clean_question(body) -> str:
    """去掉前後空白；空的問題直接回 400。
    （SearchBody 只擋長度 < 1，全空白的字串會通過那關，所以這裡要再檢查一次）
    """
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="問題不能是空的")
    return question
