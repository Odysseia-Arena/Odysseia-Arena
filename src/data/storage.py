# storage.py
import json
import os
import sqlite3
import threading
import time
from typing import Dict, List, Any, Optional, Tuple
from contextlib import contextmanager
from typing import Optional
from src.utils import config
from src.utils.logger_config import logger

# 定义数据存储路径
DATABASE_FILE = os.path.join(config.DATA_DIR, "arena.db")
FIXED_PROMPT_RESPONSES_FILE = config.FIXED_PROMPT_RESPONSES_FILE

# 使用 threading.local 存储当前线程的活动事务连接
_transaction_state = threading.local()

# --- 数据库连接和事务管理 (核心逻辑) ---

def _connect() -> sqlite3.Connection:
    """创建新的数据库连接"""
    # 设置较长的 timeout (15秒) 以应对并发写入时的锁定等待
    conn = sqlite3.connect(DATABASE_FILE, timeout=15.0)
    # 使用 Row 工厂以便于将结果作为字典访问，保持与旧代码的兼容性
    conn.row_factory = sqlite3.Row
    # 启用 WAL 模式以提高并发性能 (允许读操作与写操作并行)
    conn.execute("PRAGMA journal_mode=WAL;")
    # 启用外键约束
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@contextmanager
def db_access():
    """
    提供数据库访问的上下文管理器。
    如果在事务中，则复用事务连接。
    如果不在事务中，则创建新连接并处理自动提交/回滚/关闭。
    """
    # 检查是否存在活动事务连接
    tx_conn = getattr(_transaction_state, 'connection', None)

    if tx_conn:
        # 在事务中：提供连接，不在此处提交或关闭。
        yield tx_conn
    else:
        # 不在事务中：创建新连接，管理其生命周期。
        conn = _connect()
        try:
            # 使用 'with conn:' 确保操作成功时自动提交，发生异常时自动回滚 (SQLite特性)
            with conn:
                yield conn
        finally:
            conn.close()

@contextmanager
def transaction():
    """
    启动一个数据库事务。确保 RMW 操作的原子性。
    使用 BEGIN IMMEDIATE 获取写锁，保证跨进程的原子性。
    """
    # 简单处理嵌套事务：如果已在事务中，则复用连接
    if getattr(_transaction_state, 'connection', None) is not None:
        yield _transaction_state.connection
        return

    conn = _connect()
    try:
        # 开始 IMMEDIATE 事务，立即尝试获取写锁，保证序列化。
        conn.execute("BEGIN IMMEDIATE TRANSACTION")
        # 将连接保存到线程本地存储
        _transaction_state.connection = conn
        yield conn
        conn.commit()
    except Exception as e:
        # 发生错误时自动回滚
        conn.rollback()
        logger.error(f"数据库事务执行失败: {e}", exc_info=True)
        raise
    finally:
        # 清理事务状态并关闭连接
        _transaction_state.connection = None
        conn.close()

# --- 初始化和辅助函数 ---

def initialize_storage():
    """初始化数据库和表结构，并处理必要的迁移"""
    os.makedirs(config.DATA_DIR, exist_ok=True)

    with transaction() as conn:
        cursor = conn.cursor()
        
        # 1. 创建模型评分表 (models) 
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS models (
                model_id TEXT PRIMARY KEY,
                model_name TEXT NOT NULL,
                rating REAL NOT NULL,
                battles INTEGER DEFAULT 0 NOT NULL,
                wins INTEGER DEFAULT 0 NOT NULL,
                ties INTEGER DEFAULT 0 NOT NULL,
                skips INTEGER DEFAULT 0 NOT NULL,
                is_active BOOLEAN DEFAULT 1 NOT NULL,
                tier TEXT DEFAULT 'low' NOT NULL
            );
        """)

        # --- 数据库迁移逻辑 ---
        # 检查并添加 Glicko-2 所需的字段，以兼容旧数据库
        cursor.execute("PRAGMA table_info(models)")
        columns = [row["name"] for row in cursor.fetchall()]

        if 'rating_deviation' not in columns:
            logger.info("数据库迁移：正在为 'models' 表添加 'rating_deviation' 字段...")
            cursor.execute(f"ALTER TABLE models ADD COLUMN rating_deviation REAL DEFAULT {config.GLICKO2_DEFAULT_RD} NOT NULL;")
        
        if 'volatility' not in columns:
            logger.info("数据库迁移：正在为 'models' 表添加 'volatility' 字段...")
            cursor.execute(f"ALTER TABLE models ADD COLUMN volatility REAL DEFAULT {config.GLICKO2_DEFAULT_VOL} NOT NULL;")

        if 'tier' not in columns:
            logger.info("数据库迁移：正在为 'models' 表添加 'tier' 字段...")
            cursor.execute("ALTER TABLE models ADD COLUMN tier TEXT DEFAULT 'low' NOT NULL;")

        if 'skips' not in columns:
            logger.info("数据库迁移：正在为 'models' 表添加 'skips' 字段...")
            cursor.execute("ALTER TABLE models ADD COLUMN skips INTEGER DEFAULT 0 NOT NULL;")

        # 为实时评分添加新字段
        if 'rating_realtime' not in columns:
            logger.info("数据库迁移：正在为 'models' 表添加 'rating_realtime' 字段...")
            cursor.execute("ALTER TABLE models ADD COLUMN rating_realtime REAL;")
        if 'rating_deviation_realtime' not in columns:
            logger.info("数据库迁移：正在为 'models' 表添加 'rating_deviation_realtime' 字段...")
            cursor.execute("ALTER TABLE models ADD COLUMN rating_deviation_realtime REAL;")
        if 'volatility_realtime' not in columns:
            logger.info("数据库迁移：正在为 'models' 表添加 'volatility_realtime' 字段...")
            cursor.execute("ALTER TABLE models ADD COLUMN volatility_realtime REAL;")
        
        # 2. 创建对战记录表 (battles)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS battles (
                battle_id TEXT PRIMARY KEY,
                battle_type TEXT NOT NULL,
                prompt TEXT NOT NULL,
                model_a_id TEXT NOT NULL REFERENCES models(model_id),
                model_b_id TEXT NOT NULL REFERENCES models(model_id),
                model_a_name TEXT NOT NULL,
                model_b_name TEXT NOT NULL,
                response_a TEXT NOT NULL,
                response_b TEXT NOT NULL,
                status TEXT NOT NULL, -- pending_vote, completed
                winner TEXT, -- model_a, model_b, tie
                timestamp REAL NOT NULL,
                created_at REAL NOT NULL,
                discord_id TEXT -- 添加 discord_id 字段
            );
        """)

        # 迁移：为 battles 表添加 prompt_id 和 prompt_theme 字段
        cursor.execute("PRAGMA table_info(battles)")
        battle_columns = [row["name"] for row in cursor.fetchall()]
        if 'prompt_id' not in battle_columns:
            cursor.execute("ALTER TABLE battles ADD COLUMN prompt_id TEXT;")
        if 'prompt_theme' not in battle_columns:
            cursor.execute("ALTER TABLE battles ADD COLUMN prompt_theme TEXT;")

        # 3. 投票历史表 (voting_history)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS voting_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                battle_id TEXT NOT NULL REFERENCES battles(battle_id),
                vote_choice TEXT NOT NULL,
                user_id TEXT NOT NULL,  -- 格式: discord:123456789
                user_hash TEXT NOT NULL  -- user_id的哈希值，用于隐私保护
            );
        """)
        # 添加索引以加速防作弊检查 (关键优化)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_voting_history_timestamp_desc ON voting_history (timestamp DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_voting_history_user_hash ON voting_history (user_hash);")

        # 4. 待处理比赛表 (pending_matches) - 用于周期性评分更新
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_a_id TEXT NOT NULL,
                model_b_id TEXT NOT NULL,
                outcome REAL NOT NULL, -- 1.0 for A win, 0.5 for tie, 0.0 for B win
                timestamp REAL NOT NULL
            );
        """)

        # --- 模型数据同步 ---
        sync_models_with_db(conn)

def sync_models_with_db(conn: Optional[sqlite3.Connection] = None):
    """
    将配置文件中的模型列表与数据库同步。
    - 插入新模型。
    - 更新现有模型的名称。
    """
    def _sync_logic(db_conn):
        cursor = db_conn.cursor()
        
        # 1. 从数据库中获取现有模型列表
        cursor.execute("SELECT model_id FROM models")
        existing_model_ids = {row["model_id"] for row in cursor.fetchall()}
        
        # 2. 从配置中获取当前模型列表
        current_models = config.get_models()
        current_model_ids = {model['id'] for model in current_models}
        
        # 3. 插入新模型
        new_model_ids = current_model_ids - existing_model_ids
        if new_model_ids:
            initial_scores = config.get_initial_scores()
            models_to_insert = []
            for model_obj in current_models:
                if model_obj['id'] in new_model_ids:
                    model_id = model_obj['id']
                    preset_scores = initial_scores.get(model_id)
                    
                    if preset_scores:
                        # 如果在 model_scores.json 中找到预设值
                        rating = preset_scores.get("rating", config.GLICKO2_DEFAULT_RATING)
                        # 如果 rd 为 null 或未提供，则使用默认值
                        rd = preset_scores.get("rd")
                        if rd is None:
                            rd = config.GLICKO2_DEFAULT_RD
                        volatility = preset_scores.get("volatility", config.GLICKO2_DEFAULT_VOL)
                    else:
                        # 否则，使用全局默认值
                        rating = config.GLICKO2_DEFAULT_RATING
                        rd = config.GLICKO2_DEFAULT_RD
                        volatility = config.GLICKO2_DEFAULT_VOL

                    models_to_insert.append((
                        model_id,
                        model_obj['name'],
                        rating,
                        rd,
                        volatility,
                        'low',
                        0
                    ))
            
            if models_to_insert:
                # 使用 INSERT OR IGNORE 避免在模型已存在时出错
                cursor.executemany("INSERT OR IGNORE INTO models (model_id, model_name, rating, rating_deviation, volatility, tier, skips) VALUES (?, ?, ?, ?, ?, ?, ?)", models_to_insert)
                if cursor.rowcount > 0:
                    logger.info(f"数据库同步：新增了 {cursor.rowcount} 个模型。")

        # 4. 更新现有模型的名称 (实现名称热更新)
        models_to_update = []
        for model_obj in current_models:
            if model_obj['id'] in existing_model_ids:
                models_to_update.append((model_obj['name'], model_obj['id']))
        
        if models_to_update:
            cursor.executemany("UPDATE models SET model_name = ? WHERE model_id = ?", models_to_update)

    if conn:
        # 如果提供了现有连接（例如在事务中），则直接使用它
        _sync_logic(conn)
    else:
        # 否则，创建一个新的连接上下文
        with db_access() as new_conn:
            _sync_logic(new_conn)

# --- 对战记录管理 ---
# (所有这些函数现在都使用 db_access()，因此它们会自动参与活动事务或自动提交)

def save_battle_record(battle_id: str, record: Dict):
    """保存新的对战记录"""
    with db_access() as conn:
        conn.execute("""
            INSERT INTO battles (
                battle_id, battle_type, prompt_id, prompt_theme, prompt,
                model_a_id, model_b_id, model_a_name, model_b_name,
                response_a, response_b, status, winner, timestamp, created_at, discord_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record["battle_id"], record.get("battle_type"), 
            record.get("prompt_id"), record.get("prompt_theme"), record.get("prompt"),
            record.get("model_a_id"), record.get("model_b_id"),
            record.get("model_a_name"), record.get("model_b_name"),
            record.get("response_a"), record.get("response_b"),
            record["status"], record.get("winner"), record["timestamp"],
            record["created_at"], record.get("discord_id")
        ))

def get_battle_record(battle_id: str) -> Dict | None:
    """获取指定的对战记录"""
    with db_access() as conn:
        cursor = conn.execute("SELECT * FROM battles WHERE battle_id = ?", (battle_id,))
        record = cursor.fetchone()
        if record:
            return dict(record)
        return None

def update_battle_record(battle_id: str, updates: Dict):
    """更新现有的对战记录"""
    if not updates:
        return True

    set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values())
    values.append(battle_id)

    with db_access() as conn:
        cursor = conn.execute(f"UPDATE battles SET {set_clause} WHERE battle_id = ?", values)
        return cursor.rowcount > 0

def delete_battle_record(battle_id: str) -> bool:
    """删除指定的对战记录"""
    with db_access() as conn:
        cursor = conn.execute("DELETE FROM battles WHERE battle_id = ?", (battle_id,))
        return cursor.rowcount > 0

def delete_pending_battles_by_discord_id(discord_id: str) -> int:
    """删除指定用户所有卡在“生成中”(pending_generation)状态的对战，并返回删除的数量"""
    with db_access() as conn:
        cursor = conn.execute(
            "DELETE FROM battles WHERE discord_id = ? AND status = 'pending_generation'",
            (discord_id,)
        )
        return cursor.rowcount

def get_pending_battles_before(timestamp: float) -> List[Dict]:
    """获取在指定时间戳之前创建的、状态为 pending_vote 的对战记录"""
    with db_access() as conn:
        cursor = conn.execute(
            "SELECT * FROM battles WHERE status = 'pending_vote' AND created_at < ?",
            (timestamp,)
        )
        return [dict(row) for row in cursor.fetchall()]

def get_stale_generation_battles(timestamp: float) -> List[Dict]:
    """获取在指定时间戳之前创建的、状态为 pending_generation 的对战记录"""
    with db_access() as conn:
        cursor = conn.execute(
            "SELECT * FROM battles WHERE status = 'pending_generation' AND created_at < ?",
            (timestamp,)
        )
        return [dict(row) for row in cursor.fetchall()]

def get_recent_battles_by_discord_id(discord_id: str, time_window: float) -> List[Dict]:
    """获取指定用户在给定时间窗口内创建的对战记录"""
    cutoff_time = time.time() - time_window
    with db_access() as conn:
        cursor = conn.execute(
            "SELECT * FROM battles WHERE discord_id = ? AND created_at > ? ORDER BY created_at DESC",
            (discord_id, cutoff_time)
        )
        return [dict(row) for row in cursor.fetchall()]

def has_pending_battle(discord_id: str) -> bool:
    """检查用户是否有一个正在进行的对战 (状态为 'pending_generation' 或 'pending_vote')"""
    with db_access() as conn:
        cursor = conn.execute(
            "SELECT 1 FROM battles WHERE discord_id = ? AND (status = 'pending_generation' OR status = 'pending_vote') LIMIT 1",
            (discord_id,)
        )
        return cursor.fetchone() is not None

def get_pending_battle_count(discord_id: str) -> int:
    """获取用户正在进行的对战数量"""
    with db_access() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM battles WHERE discord_id = ? AND (status = 'pending_generation' OR status = 'pending_vote')",
            (discord_id,)
        )
        count = cursor.fetchone()[0]
        return count if count is not None else 0

def get_latest_battle_by_discord_id(discord_id: str) -> Optional[Dict]:
    """获取指定用户最新的一条对战记录"""
    with db_access() as conn:
        cursor = conn.execute(
            "SELECT * FROM battles WHERE discord_id = ? ORDER BY created_at DESC LIMIT 1",
            (discord_id,)
        )
        record = cursor.fetchone()
        return dict(record) if record else None

# --- 模型评分管理 ---

def update_model_tiers(updates: List[Tuple[str, str]]):
    """
    批量更新模型的等级 (tier)。
    :param updates: 一个元组列表，每个元组为 (new_tier, model_id)
    """
    with db_access() as conn:
        conn.executemany("UPDATE models SET tier = ? WHERE model_id = ?", updates)


def set_model_active_status(model_id: str, is_active: bool) -> bool:
    """设置模型的活动状态"""
    with db_access() as conn:
        cursor = conn.execute(
            "UPDATE models SET is_active = ? WHERE model_id = ?",
            (1 if is_active else 0, model_id)
        )
        return cursor.rowcount > 0

def get_model_scores() -> Dict[str, Dict]:
    """获取所有模型的评分和统计信息（包括tier）"""
    scores = {}
    with db_access() as conn:
        cursor = conn.execute("SELECT * FROM models")
        for row in cursor.fetchall():
            model_id = row["model_id"]
            stats = dict(row)
            if "model_id" in stats:
                 del stats["model_id"]
            scores[model_id] = stats
    return scores

def save_model_scores(scores: Dict[str, Dict]):
    """
    保存更新后的模型评分。
    """
    data_to_update = []
    for model_id, stats in scores.items():
        # 为新字段提供默认值，以防它们在stats字典中不存在
        rating_realtime = stats.get('rating_realtime', stats['rating'])
        rd_realtime = stats.get('rating_deviation_realtime', stats.get('rating_deviation', config.GLICKO2_DEFAULT_RD))
        vol_realtime = stats.get('volatility_realtime', stats.get('volatility', config.GLICKO2_DEFAULT_VOL))

        data_to_update.append((
            stats["model_name"], stats["rating"], stats.get("rating_deviation", config.GLICKO2_DEFAULT_RD),
            stats.get("volatility", config.GLICKO2_DEFAULT_VOL), stats["battles"],
            stats["wins"], stats.get("ties", 0), stats.get("skips", 0),
            rating_realtime, rd_realtime, vol_realtime,
            model_id
        ))

    with db_access() as conn:
        conn.executemany("""
            UPDATE models SET
            model_name = ?, rating = ?, rating_deviation = ?, volatility = ?,
            battles = ?, wins = ?, ties = ?, skips = ?,
            rating_realtime = ?, rating_deviation_realtime = ?, volatility_realtime = ?
            WHERE model_id = ?
        """, data_to_update)

# --- 待处理比赛管理 (用于周期性更新) ---

def add_pending_match(model_a_id: str, model_b_id: str, outcome: float):
    """添加一场待处理的比赛结果"""
    with db_access() as conn:
        conn.execute(
            "INSERT INTO pending_matches (model_a_id, model_b_id, outcome, timestamp) VALUES (?, ?, ?, ?)",
            (model_a_id, model_b_id, outcome, time.time())
        )

def get_and_clear_pending_matches() -> List[Dict]:
    """原子性地获取并清空所有待处理的比赛"""
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT model_a_id, model_b_id, outcome FROM pending_matches")
        matches = [dict(row) for row in cursor.fetchall()]
        cursor.execute("DELETE FROM pending_matches")
        return matches

# --- 投票记录管理 ---

def get_recent_votes(time_window: float) -> List[Dict]:
    """获取最近指定时间窗口内的投票记录 (用于替代 get_voting_history)"""
    cutoff_time = time.time() - time_window
    with db_access() as conn:
        cursor = conn.execute(
            "SELECT * FROM voting_history WHERE timestamp > ? ORDER BY timestamp DESC",
            (cutoff_time,)
        )
        recent_votes = [dict(row) for row in cursor.fetchall()]
    return recent_votes

def save_vote_record(record: Dict):
    """保存新的投票记录"""
    with db_access() as conn:
        conn.execute("""
            INSERT INTO voting_history (
                timestamp, battle_id, vote_choice, user_id, user_hash
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            record["timestamp"], record["battle_id"], record["vote_choice"],
            record["user_id"], record["user_hash"]
        ))

# --- 固定提示词响应缓存 (保持使用JSON，因为是只读的) ---

def get_fixed_prompt_responses() -> Dict[str, Dict[str, str]]:
    """加载固定提示词的高质量响应缓存（只读）"""
    try:
        if not os.path.exists(FIXED_PROMPT_RESPONSES_FILE):
            return {}
        with open(FIXED_PROMPT_RESPONSES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.warning(f"无法解析JSON文件 {FIXED_PROMPT_RESPONSES_FILE}。")
        return {}

# --- 统计信息 ---

def get_total_users_count() -> int:
    """获取已记录的唯一用户总数"""
    with db_access() as conn:
        cursor = conn.execute("SELECT COUNT(DISTINCT discord_id) FROM battles WHERE discord_id IS NOT NULL")
        count = cursor.fetchone()[0]
        return count if count is not None else 0

def get_completed_battles_count() -> int:
    """获取已完成的对战总数"""
    with db_access() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM battles WHERE status = 'completed'")
        count = cursor.fetchone()[0]
        return count if count is not None else 0