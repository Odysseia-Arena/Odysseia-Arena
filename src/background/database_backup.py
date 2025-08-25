# src/background/database_backup.py
import os
import shutil
import time
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from src.utils import config
from src.utils.logger_config import logger

BACKUP_DIR = os.path.join(config.DATA_DIR, "backups")
DATABASE_FILE = os.path.join(config.DATA_DIR, "arena.db")
MAX_BACKUPS = 24  # 保留最近24个备份文件 (24小时)

def backup_database():
    """
    执行数据库备份操作，并清理旧的备份。
    """
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        # 1. 创建带时间戳的备份文件名
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_filename = f"arena_{timestamp}.db"
        backup_filepath = os.path.join(BACKUP_DIR, backup_filename)
        
        # 2. 复制数据库文件
        shutil.copy2(DATABASE_FILE, backup_filepath)
        logger.info(f"数据库成功备份至: {backup_filepath}")
        
        # 3. 清理旧的备份
        cleanup_old_backups()
        
    except Exception as e:
        logger.error(f"数据库备份失败: {e}", exc_info=True)

def cleanup_old_backups():
    """
    清理超过 MAX_BACKUPS 数量的旧备份文件。
    """
    try:
        backups = sorted(
            [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.startswith('arena_') and f.endswith('.db')],
            key=os.path.getmtime,
            reverse=True
        )
        
        if len(backups) > MAX_BACKUPS:
            files_to_delete = backups[MAX_BACKUPS:]
            for f in files_to_delete:
                os.remove(f)
                logger.info(f"已删除旧的备份文件: {f}")
    except Exception as e:
        logger.error(f"清理旧备份时出错: {e}", exc_info=True)

def start_backup_scheduler():
    """
    启动一个后台调度器，在每小时整点运行数据库备份任务。
    """
    scheduler = BackgroundScheduler(timezone='Asia/Shanghai')
    scheduler.add_job(
        backup_database,
        trigger=CronTrigger(minute=0, second=0),
        id='hourly_database_backup',
        name='Hourly Database Backup',
        replace_existing=True
    )
    scheduler.start()
    logger.info("数据库每小时备份任务已启动，将在每个整点执行。")