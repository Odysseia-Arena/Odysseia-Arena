# scripts/maintenance/import_initial_scores.py
# python scripts/maintenance/import_initial_scores.py initial_scores.json
import json
import os
import sys
import argparse

# 将 src 目录添加到 Python 路径中，以便可以导入 src 下的模块
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.data import storage
from src.utils.logger_config import logger

def import_scores_from_json(file_path: str):
    """
    从 JSON 文件导入模型初始得分数据到数据库。

    Args:
        file_path (str): 包含模型得分数据的 JSON 文件的路径。
    """
    logger.info(f"开始从文件 '{file_path}' 导入模型初始得分...")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error(f"错误：找不到文件 '{file_path}'。")
        return
    except json.JSONDecodeError:
        logger.error(f"错误：无法解析文件 '{file_path}' 中的 JSON。")
        return

    if not isinstance(data, dict):
        logger.error("错误：JSON 文件的顶层结构必须是一个字典 (model_id -> score_data)。")
        return

    records_to_upsert = []
    for model_id, stats in data.items():
        rating = stats.get("rating")
        rd = stats.get("rd")
        volatility = stats.get("volatility")
        tier = stats.get("tier")

        if not all([rating is not None, rd is not None, volatility is not None, tier is not None]):
            logger.warning(f"跳过模型 '{model_id}'，因为缺少必要的字段（rating, rd, volatility, tier）。")
            continue
        
        records_to_upsert.append((
            model_id,
            model_id,  # model_name
            float(rating),
            float(rd),
            float(volatility),
            tier,
            float(rating),  # rating_realtime
            float(rd),      # rating_deviation_realtime
            float(volatility) # volatility_realtime
        ))

    try:
        with storage.transaction() as conn:
            logger.info("已启动数据库事务。")
            cursor = conn.cursor()
            
            # 使用 INSERT OR REPLACE (UPSERT) 逻辑
            # 如果 model_id 已存在，则替换整行记录
            # 注意：这会重置 battles, wins 等统计数据为默认值 0
            cursor.executemany("""
                INSERT OR REPLACE INTO models (
                    model_id, model_name, rating, rating_deviation, volatility, tier,
                    rating_realtime, rating_deviation_realtime, volatility_realtime,
                    battles, wins, ties, skips, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 1)
            """, records_to_upsert)
            
            logger.info(f"数据导入完成。总共处理了 {cursor.rowcount} 条记录。")

    except Exception as e:
        logger.error(f"在导入过程中发生数据库错误，事务已回滚: {e}", exc_info=True)
    else:
        logger.info("数据库事务已成功提交。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="从 JSON 文件手动导入模型初始得分数据到数据库。")
    parser.add_argument("file_path", type=str, help="包含模型得分数据的 JSON 文件的路径。")
    
    args = parser.parse_args()
    
    # 1. 确保数据库和表结构存在
    storage.initialize_storage()
    
    # 2. 执行导入
    import_scores_from_json(args.file_path)