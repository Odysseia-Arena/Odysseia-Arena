import threading
import time
from . import config
from . import glicko2_rating
from .logger_config import logger

# --- 状态变量 ---
_updater_thread = None
_stop_event = threading.Event()
_last_update_timestamp = 0

def _rating_update_worker():
    """
    后台工作线程，定期检查并触发评分更新。
    """
    global _last_update_timestamp
    
    logger.info("Rating updater worker started.")
    _last_update_timestamp = time.time()

    while not _stop_event.is_set():
        try:
            # 每分钟检查一次
            _stop_event.wait(60)
            if _stop_event.is_set():
                break

            period_minutes = config.RATING_UPDATE_PERIOD_MINUTES
            
            # 如果周期设置为0（实时更新），则此工作线程不执行任何操作
            if period_minutes <= 0:
                continue

            current_time = time.time()
            elapsed_seconds = current_time - _last_update_timestamp
            
            if elapsed_seconds >= period_minutes * 60:
                logger.info(f"Rating update period of {period_minutes} minutes has elapsed. Starting update...")
                
                try:
                    # 调用核心更新逻辑
                    glicko2_rating.run_rating_update()
                    _last_update_timestamp = current_time
                    logger.info("Rating update completed successfully.")
                except Exception as e:
                    logger.exception("An error occurred during the rating update process.")
            
        except Exception as e:
            logger.exception("An unexpected error occurred in the rating updater worker.")

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
