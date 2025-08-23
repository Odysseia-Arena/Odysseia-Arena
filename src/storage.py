# storage.py
import json
import os
import sqlite3
import threading
import time
from typing import Dict, List, Any, Optional
from contextlib import contextmanager
from . import config

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
        # 在生产环境中应记录日志
        print(f"Database transaction failed: {e}")
        raise
    finally:
        # 清理事务状态并关闭连接
        _transaction_state.connection = None
        conn.close()

# --- 初始化和辅助函数 ---

def initialize_storage():
    """初始化数据库和表结构"""
    os.makedirs(config.DATA_DIR, exist_ok=True)

    # 使用 transaction 来初始化数据库
    with transaction() as conn:
        cursor = conn.cursor()
        
        # 1. 模型评分表 (models)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS models (
                model_id TEXT PRIMARY KEY,
                model_name TEXT NOT NULL,
                rating INTEGER NOT NULL,
                battles INTEGER DEFAULT 0 NOT NULL,
                wins INTEGER DEFAULT 0 NOT NULL,
                ties INTEGER DEFAULT 0 NOT NULL
            );
        """)

        # 2. 对战记录表 (battles)
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
                created_at REAL NOT NULL
            );
        """)

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

        # --- 模型数据同步 ---
        # 1. 插入新模型
        cursor.execute("SELECT model_id FROM models")
        existing_model_ids = {row["model_id"] for row in cursor.fetchall()}
        
        models_to_insert = []
        for model_obj in config.AVAILABLE_MODELS:
            model_id = model_obj['id']
            if model_id not in existing_model_ids:
                models_to_insert.append((model_id, model_obj['name'], config.DEFAULT_ELO_RATING))
        
        if models_to_insert:
            cursor.executemany("INSERT INTO models (model_id, model_name, rating) VALUES (?, ?, ?)", models_to_insert)

        # 2. 更新现有模型的名称 (实现名称热更新)
        models_to_update = []
        for model_obj in config.AVAILABLE_MODELS:
            models_to_update.append((model_obj['name'], model_obj['id']))
        
        if models_to_update:
            cursor.executemany("UPDATE models SET model_name = ? WHERE model_id = ?", models_to_update)

# --- 对战记录管理 ---
# (所有这些函数现在都使用 db_access()，因此它们会自动参与活动事务或自动提交)

def save_battle_record(battle_id: str, record: Dict):
    """保存新的对战记录"""
    # 为了兼容旧代码，将model_a/b重命名为model_a/b_id
    record['model_a_id'] = record.pop('model_a')
    record['model_b_id'] = record.pop('model_b')

    with db_access() as conn:
        conn.execute("""
            INSERT INTO battles (
                battle_id, battle_type, prompt,
                model_a_id, model_b_id, model_a_name, model_b_name,
                response_a, response_b, status, winner, timestamp, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record["battle_id"], record["battle_type"], record["prompt"],
            record["model_a_id"], record["model_b_id"],
            record["model_a_name"], record["model_b_name"],
            record["response_a"], record["response_b"],
            record["status"], record.get("winner"), record["timestamp"],
            record["created_at"]
        ))

def get_battle_record(battle_id: str) -> Dict | None:
    """获取指定的对战记录"""
    with db_access() as conn:
        cursor = conn.execute("SELECT * FROM battles WHERE battle_id = ?", (battle_id,))
        record = cursor.fetchone()
        if record:
            # 将 sqlite3.Row 转换为普通字典以保持兼容性
            return dict(record)
        return None

def update_battle_record(battle_id: str, updates: Dict):
    """更新现有的对战记录"""
    if not updates:
        return True

    # 动态构建 SQL 语句
    set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values())
    values.append(battle_id)

    with db_access() as conn:
        cursor = conn.execute(f"UPDATE battles SET {set_clause} WHERE battle_id = ?", values)
        return cursor.rowcount > 0

def delete_battle_record(battle_id: str):
    """删除指定的对战记录"""
    with db_access() as conn:
        cursor = conn.execute("DELETE FROM battles WHERE battle_id = ?", (battle_id,))
        return cursor.rowcount > 0

def get_pending_battles_before(timestamp: float) -> List[Dict]:
    """获取在指定时间戳之前创建的、状态为 pending_vote 的对战记录"""
    with db_access() as conn:
        cursor = conn.execute(
            "SELECT * FROM battles WHERE status = 'pending_vote' AND created_at < ?",
            (timestamp,)
        )
        return [dict(row) for row in cursor.fetchall()]

# --- 模型评分管理 ---

def get_model_scores() -> Dict[str, Dict]:
    """获取所有模型的评分"""
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
        data_to_update.append((
            stats["model_name"], stats["rating"], stats["battles"],
            stats["wins"], stats.get("ties", 0), model_id
        ))

    with db_access() as conn:
        conn.executemany("""
            UPDATE models SET
            model_name = ?, rating = ?, battles = ?, wins = ?, ties = ?
            WHERE model_id = ?
        """, data_to_update)

# --- 投票记录管理 ---

# !! 移除低效的 get_voting_history() !!
# 旧的 storage.py 中存在 get_voting_history()，它会加载所有记录到内存中。
# 我们将其移除，并替换为更高效的查询函数。

# !! 新增优化函数 !!
def get_recent_votes(time_window: float) -> List[Dict]:
    """获取最近指定时间窗口内的投票记录 (用于替代 get_voting_history)"""
    cutoff_time = time.time() - time_window
    with db_access() as conn:
        # 利用 timestamp DESC 索引进行高效查询
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
    # 这个文件通常是静态的，不需要迁移到SQLite
    try:
        if not os.path.exists(FIXED_PROMPT_RESPONSES_FILE):
            return {}
        with open(FIXED_PROMPT_RESPONSES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"警告: 无法解析JSON文件 {FIXED_PROMPT_RESPONSES_FILE}。")
        return {}

# --- 排行榜缓存管理 (已弃用) ---
# 注意：排行榜现在直接从数据库读取，不再使用缓存机制