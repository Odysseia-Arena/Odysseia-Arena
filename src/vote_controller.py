# vote_controller.py
import time
import hashlib
from typing import Dict
from . import storage
from . import elo_rating
from . import config

# 1. 定义自定义异常以处理事务回滚控制流
class VoteConflictError(Exception):
    """当由于状态冲突（例如比赛已结束）导致投票无法处理时抛出。"""
    pass

def _hash_user_id(user_id: str) -> str:
    """生成用户ID的哈希值，用于隐私保护"""
    # user_id格式: discord:123456789 或未来的 web:abc123
    # 使用SHA256哈希
    return hashlib.sha256(user_id.encode()).hexdigest()

def _check_anti_cheat(battle_id: str, user_hash: str) -> str | None:
    """执行防作弊检查"""
    current_time = time.time()

    # 使用优化后的查询
    # 计算需要查询的最长时间窗口
    max_window = max(config.VOTE_TIME_WINDOW, config.USER_RATE_LIMIT_WINDOW)
    # 只加载最近需要的投票记录
    voting_history = storage.get_recent_votes(max_window)

    user_votes_in_window = 0

    # 遍历历史记录（数据库已按时间倒序返回且已过滤时间）
    for vote in voting_history: 
        # 1. 重复投票检测
        if vote["battle_id"] == battle_id and vote["user_hash"] == user_hash:
            # 仍需检查具体的 VOTE_TIME_WINDOW 要求
            if current_time - vote["timestamp"] < config.VOTE_TIME_WINDOW:
                return f"您在{config.VOTE_TIME_WINDOW//60}分钟内已为此对战投过票。"

        # 2. 用户速率限制计数
        if vote["user_hash"] == user_hash:
             # 仍需检查具体的 USER_RATE_LIMIT_WINDOW 要求
             if current_time - vote["timestamp"] < config.USER_RATE_LIMIT_WINDOW:
                user_votes_in_window += 1

    # 2. 用户速率限制检查
    if user_votes_in_window >= config.USER_MAX_VOTES_PER_HOUR:
        return "投票过于频繁，请稍后再试。"
        
    return None

def submit_vote(battle_id: str, vote_choice: str, discord_id: str) -> Dict:
    """
    处理投票提交。现在是原子操作。
    """
    if vote_choice not in ["model_a", "model_b", "tie"]:
        raise ValueError("无效的投票选项。")

    # 构建完整的user_id（带前缀）
    user_id = f"discord:{discord_id}"
    user_hash = _hash_user_id(user_id)
    
    # 防作弊检查 (在事务外进行，以减少数据库锁定的时间。这是只读操作)
    cheat_error = _check_anti_cheat(battle_id, user_hash)
    if cheat_error:
        return {"status": "error", "message": cheat_error}

    # [关键改动：使用事务包裹 RMW 逻辑]
    try:
        # 使用数据库事务确保投票处理的原子性 (RMW)
        with storage.transaction():
            # --- 原子操作开始 (已获取数据库写锁) ---
            
            # 1. 获取对战记录 (在事务中读取，确保状态最新)
            # 必须在事务内部重新读取，以获取最新状态
            battle = storage.get_battle_record(battle_id)
            if not battle:
                # 抛出异常将触发回滚
                raise FileNotFoundError("找不到该对战记录。")

            # 2. 检查对战状态 (关键的并发检查)
            # 如果另一个并发请求已经完成了投票，这里的检查会失败
            if battle["status"] != "pending_vote":
                # 抛出自定义异常将触发回滚，并在下方捕获
                raise VoteConflictError("该对战已结束投票。")

            # 4. 处理投票结果
            winner = vote_choice
            model_a_id = battle["model_a_id"]
            model_b_id = battle["model_b_id"]

            # 5. 更新ELO评分
            # elo_rating.process_battle_result 中的 RMW 操作现在是安全的，
            # 因为它通过 threading.local 自动参与到了当前的事务中。
            elo_rating.process_battle_result(model_a_id, model_b_id, winner)

            # 6. 更新对战记录状态为已完成
            updates = {
                "status": "completed",
                "winner": winner
            }
            storage.update_battle_record(battle_id, updates)

            # 7. 保存投票历史（哈希化以保护隐私）
            vote_record = {
                "timestamp": time.time(),
                "battle_id": battle_id,
                "vote_choice": vote_choice,
                "user_id": user_id,
                "user_hash": user_hash
            }
            storage.save_vote_record(vote_record)
            
            # --- 原子操作结束 (事务提交，锁释放) ---

    except VoteConflictError as e:
        # 捕获自定义异常，返回错误信息（此时事务已回滚）
        return {"status": "error", "message": str(e)}

    # 直接从 battle 记录中获取历史名称
    model_a_name = battle["model_a_name"]
    model_b_name = battle["model_b_name"]
    
    # 确定获胜者名称以返回给用户
    if winner == "model_a":
        winner_name = model_a_name
    elif winner == "model_b":
        winner_name = model_b_name
    else:
        winner_name = "Tie"

    return {
        "status": "success",
        "message": "投票成功提交。",
        "winner": winner_name,
        "model_a_name": model_a_name,
        "model_b_name": model_b_name
    }