import threading
import time
import datetime
from src.utils import config
from src.rating import glicko2_rating
from src.utils.logger_config import logger

# --- 状态变量 ---
_updater_thread = None
_stop_event = threading.Event()
_last_update_timestamp = 0
_lock = threading.Lock()

def _rating_update_worker():
    """
    后台工作线程，在每个整点触发评分更新。
    """
    global _last_update_timestamp
    
    logger.info("Rating updater worker started for hourly updates.")

    while not _stop_event.is_set():
        try:
            now = datetime.datetime.now()
            next_hour = (now + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            wait_seconds = (next_hour - now).total_seconds()
            
            logger.info(f"Next rating update scheduled at {next_hour.isoformat()}. Waiting for {wait_seconds:.2f} seconds.")
            
            # 等待直到下一个整点
            woke_up = not _stop_event.wait(wait_seconds)
            
            if woke_up:
                logger.info(f"It's {datetime.datetime.now().isoformat()}. Starting hourly rating update...")
                
                try:
                    # 调用核心更新逻辑
                    glicko2_rating.run_rating_update()
                    with _lock:
                        _last_update_timestamp = time.time()
                    logger.info("Hourly rating update completed successfully.")
                except Exception as e:
                    logger.exception("An error occurred during the hourly rating update process.")
            
        except Exception as e:
            logger.exception("An unexpected error occurred in the rating updater worker.")

def get_last_update_time() -> float:
    """获取上次成功更新的时间戳"""
    with _lock:
        return _last_update_timestamp

def start_rating_updater():
    """
    启动评分更新器的后台线程。
    """
    global _updater_thread
    if _updater_thread is None or not _updater_thread.is_alive():
        if config.RATING_UPDATE_PERIOD_MINUTES > 0:
            _stop_event.clear()
            _updater_thread = threading.Thread(target=_rating_update_worker, daemon=True)
            _updater_thread.start()
            logger.info("Periodic rating updater has been started.")
        else:
            logger.info("Periodic rating updater is disabled (real-time mode).")

def stop_rating_updater():
    """
    停止评分更新器的后台线程。
    """
    global _updater_thread
    if _updater_thread and _updater_thread.is_alive():
        _stop_event.set()
        _updater_thread.join()
        logger.info("Periodic rating updater has been stopped.")
