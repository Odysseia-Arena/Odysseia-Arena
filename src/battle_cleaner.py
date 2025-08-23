# src/battle_cleaner.py
import time
import threading
from . import storage
from . import config

BATTLE_TIMEOUT_MINUTES = 30
CLEANUP_INTERVAL_SECONDS = 300  # 5 minutes

def cleanup_expired_battles():
    """
    清理超时的、未投票的 battle。
    """
    try:
        # 使用事务确保操作的原子性
        with storage.transaction():
            timeout_seconds = BATTLE_TIMEOUT_MINUTES * 60
            expiration_time = time.time() - timeout_seconds
            
            expired_battles = storage.get_pending_battles_before(expiration_time)
            
            if not expired_battles:
                print(f"[{time.ctime()}] No expired battles found.")
                return

            print(f"[{time.ctime()}] Found {len(expired_battles)} expired battles to clean up.")

            # 获取当前所有模型的评分/统计数据
            all_scores = storage.get_model_scores()

            for battle in expired_battles:
                battle_id = battle['battle_id']
                model_a_id = battle['model_a_id']
                model_b_id = battle['model_b_id']

                # 撤销对战场次
                if model_a_id in all_scores:
                    all_scores[model_a_id]['battles'] = max(0, all_scores[model_a_id]['battles'] - 1)
                if model_b_id in all_scores:
                    all_scores[model_b_id]['battles'] = max(0, all_scores[model_b_id]['battles'] - 1)
                
                # 删除 battle 记录
                storage.delete_battle_record(battle_id)
                print(f"    - Deleted battle {battle_id} between {model_a_id} and {model_b_id}.")

            # 保存更新后的模型统计数据
            storage.save_model_scores(all_scores)
            print(f"[{time.ctime()}] Battle cleanup complete. Updated model scores.")

    except Exception as e:
        # 在生产环境中，这里应该使用日志记录器
        print(f"[{time.ctime()}] Error during battle cleanup: {e}")


def run_battle_cleaner():
    """
    启动一个后台线程，定期运行 battle 清理任务。
    """
    def task():
        while True:
            cleanup_expired_battles()
            time.sleep(CLEANUP_INTERVAL_SECONDS)

    cleaner_thread = threading.Thread(target=task, daemon=True)
    cleaner_thread.start()
    print("Battle cleaner background task started.")