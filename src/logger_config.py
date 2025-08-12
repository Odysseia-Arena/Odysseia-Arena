# logger_config.py
import logging
import json
import time
import os

# 定义日志目录和文件
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "arena_server.log")

def setup_logger():
    """设置统一的日志器"""
    os.makedirs(LOG_DIR, exist_ok=True)
    
    logger = logging.getLogger("ArenaLogger")
    logger.setLevel(logging.INFO)

    # 防止重复添加处理器
    if logger.handlers:
        return logger

    # 文件处理器 (记录到文件)
    try:
        fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
        fh.setLevel(logging.INFO)
    except IOError as e:
        print(f"警告: 无法打开日志文件 {LOG_FILE}: {e}")
        fh = None

    # 控制台处理器 (输出到控制台)
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING) # 控制台只输出警告及以上级别的日志，保持简洁

    # 定义格式化器
    # 使用简单的字符串格式，方便阅读
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    if fh:
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger

# 获取配置好的日志器实例
logger = setup_logger()

# 提供简单的日志记录函数，方便其他模块调用
def log_event(event_type: str, details: dict):
    """记录结构化事件日志（以JSON字符串形式记录）"""
    log_entry = {
        "event_type": event_type,
        "details": details
    }
    # 使用logger.info记录JSON字符串
    logger.info(json.dumps(log_entry, ensure_ascii=False))

def log_error(error_message: str, context: dict = None):
    """记录错误日志"""
    details = {"message": error_message}
    if context:
        details["context"] = context
        
    log_event("ERROR", details)
    # 同时使用logger.error级别记录，方便控制台查看
    logger.error(f"Error occurred: {error_message}. Context: {context}")