# src/file_watcher.py
import time
import os
from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from src.utils import config
from src.data import storage
from src.utils.logger_config import logger

class ConfigChangeHandler(FileSystemEventHandler):
    """处理配置文件更改的事件处理器"""

    def __init__(self, models_config, prompts_config):
        self.models_config = models_config
        self.prompts_config = prompts_config
        # 使用一个简单的去抖动机制来避免短时间内重复加载
        self.last_triggered = {}

    def _should_trigger(self, path):
        """检查事件是否应该触发重载（去抖动）"""
        now = time.time()
        last_time = self.last_triggered.get(path, 0)
        if now - last_time > 2: # 2秒的冷却时间
            self.last_triggered[path] = now
            return True
        return False

    def on_modified(self, event):
        if event.is_directory:
            return
        
        target_file = os.path.basename(event.src_path)
        
        if target_file == os.path.basename(config.MODELS_FILE):
            if self._should_trigger(config.MODELS_FILE):
                logger.info(f"File watcher detected modification of {target_file}, forcing reload.")
                self.models_config.force_reload()
                # 在重载后立即同步数据库
                logger.info("Synchronizing models with the database after reload...")
                storage.sync_models_with_db()
                logger.info("Database synchronization complete.")
        
        elif target_file == os.path.basename(config.FIXED_PROMPTS_FILE):
            if self._should_trigger(config.FIXED_PROMPTS_FILE):
                logger.info(f"File watcher detected modification of {target_file}, forcing reload.")
                self.prompts_config.force_reload()

def _run_watcher():
    """在后台线程中运行文件监控器"""
    path = config.CONFIG_DIR
    
    # 获取在 config.py 中实例化的 HotReloadConfig 对象
    handler = ConfigChangeHandler(config._models_config, config._prompts_config)
    
    observer = Observer()
    observer.schedule(handler, path, recursive=False)
    observer.start()
    
    logger.info(f"Started file watcher on directory: '{path}'")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

def start_file_watcher():
    """启动文件监控后台任务"""
    watcher_thread = Thread(target=_run_watcher, daemon=True)
    watcher_thread.start()
    logger.info("File watcher background thread started.")