# src/battle_cleaner.py
import time
import threading
from src.data import storage
from src.utils import config
from src.controllers import tier_manager
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

BATTLE_TIMEOUT_MINUTES = 30
CLEANUP_INTERVAL_SECONDS = 300  # 5 minutes

def cleanup_expired_battles():
    """
    清理超时的 battle，包括 pending_vote 和 pending_generation 状态。
    """
    try:
        with storage.transaction():
            # 1. 清理超时的 pending_vote battles
            vote_expiration_time = time.time() - (BATTLE_TIMEOUT_MINUTES * 60)
            expired_vote_battles = storage.get_pending_battles_before(vote_expiration_time)
            
            if expired_vote_battles:
                print(f"[{time.ctime()}] Found {len(expired_vote_battles)} expired pending_vote battles to clean up.")
                all_scores = storage.get_model_scores()
                for battle in expired_vote_battles:
                    battle_id = battle['battle_id']
                    model_a_id = battle['model_a_id']
                    model_b_id = battle['model_b_id']
                    storage.delete_battle_record(battle_id)
                    print(f"    - Deleted pending_vote battle {battle_id}.")
                storage.save_model_scores(all_scores)
                print(f"[{time.ctime()}] pending_vote cleanup complete.")

            # 2. 清理卡住的 pending_generation battles
            generation_expiration_time = time.time() - config.GENERATION_TIMEOUT
            stale_generation_battles = storage.get_stale_generation_battles(generation_expiration_time)

            if stale_generation_battles:
                print(f"[{time.ctime()}] Found {len(stale_generation_battles)} stale pending_generation battles to clean up.")
                for battle in stale_generation_battles:
                    battle_id = battle['battle_id']
                    storage.delete_battle_record(battle_id)
                    print(f"    - Deleted pending_generation battle {battle_id}.")
                print(f"[{time.ctime()}] pending_generation cleanup complete.")

            if not expired_vote_battles and not stale_generation_battles:
                print(f"[{time.ctime()}] 清理任务完成，没有发现需要清理的超时对战。")

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

def run_promotion_relegation_scheduler():
    """
    启动一个后台调度器，在北京时间每天凌晨4点运行模型升降级任务。
    """
    scheduler = BackgroundScheduler(timezone='Asia/Shanghai')
    scheduler.add_job(
        tier_manager.promote_and_relegate_models,
        trigger=CronTrigger(hour=4, minute=0),
        id='daily_promotion_relegation',
        name='Daily Model Promotion and Relegation',
        replace_existing=True
    )
    scheduler.start()
    print("Promotion/relegation scheduler started, scheduled to run daily at 04:00 Shanghai time.")