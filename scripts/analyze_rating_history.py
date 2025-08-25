# scripts/analyze_rating_history.py
import sys
import os
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, List, Any

# --- 模块路径设置 ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src import glicko2_impl as glicko2
from src.config import DATA_DIR, GLICKO2_DEFAULT_RATING, GLICKO2_DEFAULT_RD, GLICKO2_DEFAULT_VOL, GLICKO2_TAU

# --- 数据库文件路径 ---
DATABASE_FILE = os.path.join(DATA_DIR, "arena.db")

def get_completed_battles() -> List[Dict]:
    """从数据库获取所有已完成的对战记录，并按时间排序"""
    try:
        with sqlite3.connect(DATABASE_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT timestamp, model_a_id, model_b_id, winner FROM battles WHERE status = 'completed' ORDER BY timestamp ASC"
            )
            battles = [dict(row) for row in cursor.fetchall()]
            return battles
    except sqlite3.OperationalError as e:
        print(f"数据库错误: {e}")
        print("请确保 'battles' 表存在且包含 'model_a_id', 'model_b_id', 'winner', 'status', 'timestamp' 字段。")
        return []

def analyze_and_plot():
    """
    分析历史对战数据，模拟评分变化，并绘制图表。
    """
    battles = get_completed_battles()
    if not battles:
        print("在数据库中找不到已完成的对战记录，无法生成图表。")
        return

    print(f"找到了 {len(battles)} 条已完成的对战记录，正在处理...")

    # 存储每个模型当前的 Glicko-2 Rating 对象
    model_ratings: Dict[str, glicko2.Rating] = {}
    # 存储每次评分变动的记录
    history_records = []
    
    # 初始化 Glicko-2 环境
    env = glicko2.Glicko2(tau=GLICKO2_TAU, mu=GLICKO2_DEFAULT_RATING, phi=GLICKO2_DEFAULT_RD, sigma=GLICKO2_DEFAULT_VOL)

    # 模拟评分过程
    for i, battle in enumerate(battles):
        timestamp = battle['timestamp']
        model_a_id = battle['model_a_id']
        model_b_id = battle['model_b_id']
        winner = battle['winner']

        # 获取或创建 Rating 对象
        rating_a = model_ratings.get(model_a_id, env.create_rating())
        rating_b = model_ratings.get(model_b_id, env.create_rating())

        # 确定比赛结果
        if winner == "model_a":
            new_rating_a, new_rating_b = env.rate_1vs1(rating_a, rating_b)
        elif winner == "model_b":
            new_rating_b, new_rating_a = env.rate_1vs1(rating_b, rating_a)
        else: # tie
            new_rating_a, new_rating_b = env.rate_1vs1(rating_a, rating_b, drawn=True)
        
        # 保存更新后的 Rating 对象和历史记录
        model_ratings[model_a_id] = new_rating_a
        model_ratings[model_b_id] = new_rating_b
        
        history_records.append({'timestamp': timestamp, 'model_id': model_a_id, 'rating': new_rating_a.mu})
        history_records.append({'timestamp': timestamp, 'model_id': model_b_id, 'rating': new_rating_b.mu})
            
        if (i + 1) % 100 == 0:
            print(f"已处理 {i + 1}/{len(battles)} 场比赛...")

    # --- 使用 Pandas 进行数据重塑和绘图 ---
    print("正在转换数据以生成时间序列图表...")
    df = pd.DataFrame(history_records)
    
    # 将 Unix 时间戳转换为 Pandas 的 datetime 对象
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    
    # 将数据透视为以时间为索引，模型为列的格式
    df_pivot = df.pivot(index='timestamp', columns='model_id', values='rating')
    
    # 按小时对数据进行重采样，取每小时的最后一个值
    # 这可以使图表在高密度比赛时段更清晰
    df_resampled = df_pivot.resample('h').last()

    # 使用前向填充，让每个模型在没有比赛的时段保持其评分
    df_filled = df_resampled.ffill()
    # 对于图表开头可能存在的 NaN (如果第一个小时没有比赛)，用初始值1500填充
    df_filled.fillna(1500, inplace=True)

    # --- 根据最终排名对图例进行排序 ---
    # 1. 获取每个模型的最终评分
    final_ratings = df_filled.iloc[-1]
    # 2. 根据最终评分对模型名称进行降序排序
    sorted_models = final_ratings.sort_values(ascending=False).index.tolist()
    # 3. 按照排序后的模型列表重新排列 DataFrame 的列
    df_sorted = df_filled[sorted_models]

    # 绘制图表
    print("正在生成图表...")
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(15, 8))

    df_sorted.plot(ax=ax, linestyle='-', alpha=0.8, linewidth=1.5)

    ax.set_title('Model Rating History Over Time', fontsize=16)
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('Glicko-2 Rating', fontsize=12)
    ax.legend(title='Models', bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.grid(True)
    
    plt.tight_layout()

    # 保存图表
    output_filename = 'rating_history.png'
    plt.savefig(output_filename, dpi=300)
    print(f"图表已成功保存为: {os.path.join(project_root, output_filename)}")

if __name__ == "__main__":
    analyze_and_plot()