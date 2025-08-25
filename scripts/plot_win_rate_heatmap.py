import sqlite3
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os

# 定义数据库文件和输出图像的路径
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'arena.db')
OUTPUT_IMAGE_PATH = os.path.join(os.path.dirname(__file__), '..', 'win_rate_heatmap.png')

def get_battle_data(db_path):
    """从数据库获取所有已完成的对战数据"""
    with sqlite3.connect(db_path) as conn:
        # 查询所有已完成且非平局的对战
        query = """
        SELECT model_a_name, model_b_name, winner
        FROM battles
        WHERE status = 'completed' AND winner != 'tie';
        """
        df = pd.read_sql_query(query, conn)
    return df

def calculate_win_rates(df):
    """计算模型之间的胜率"""
    # 统计所有参与对战的模型
    models = pd.unique(df[['model_a_name', 'model_b_name']].values.ravel('K'))
    
    # 初始化一个空的 DataFrame 用于存储胜率
    win_rate_matrix = pd.DataFrame(index=models, columns=models, dtype=float)

    for model_a in models:
        for model_b in models:
            if model_a == model_b:
                # 自己对自己的胜率为0.5或NaN，这里设为NaN以便在热力图中显示为空白
                win_rate_matrix.loc[model_a, model_b] = None
                continue

            # 筛选出 model_a vs model_b 的所有对战
            battles_a_vs_b = df[((df['model_a_name'] == model_a) & (df['model_b_name'] == model_b)) |
                                ((df['model_a_name'] == model_b) & (df['model_b_name'] == model_a))]
            
            total_battles = len(battles_a_vs_b)
            if total_battles == 0:
                win_rate_matrix.loc[model_a, model_b] = None
                continue

            # 计算 model_a 战胜 model_b 的次数
            a_wins = 0
            # 当 A 是 model_a 且获胜
            a_wins += battles_a_vs_b[(battles_a_vs_b['model_a_name'] == model_a) & (battles_a_vs_b['winner'] == 'model_a')].shape[0]
            # 当 A 是 model_b 且 B 输了 (即 A 获胜)
            a_wins += battles_a_vs_b[(battles_a_vs_b['model_b_name'] == model_a) & (battles_a_vs_b['winner'] == 'model_b')].shape[0]
            
            win_rate = a_wins / total_battles
            win_rate_matrix.loc[model_a, model_b] = win_rate

    return win_rate_matrix

def plot_heatmap(win_rate_matrix, output_path):
    """绘制胜率热力图"""
    if win_rate_matrix.empty:
        print("没有足够的数据来生成热力图。")
        return
        
    # 对模型名称进行排序，以获得更规整的图表
    sorted_models = sorted(win_rate_matrix.index)
    sorted_matrix = win_rate_matrix.loc[sorted_models, sorted_models]

    plt.figure(figsize=(16, 14)) # 增大图像尺寸
    sns.heatmap(
        sorted_matrix,
        annot=True,
        annot_kws={"size": 8}, # 缩小字体大小
        fmt=".2f",
        cmap="vlag", # 使用红-白-蓝颜色映射
        linewidths=.5, # 添加边框
        linecolor='black', # 边框颜色
        cbar_kws={'label': 'Win Rate (Model A vs Model B)'}
    )
    ax = plt.gca() # 获取当前坐标轴
    ax.xaxis.set_ticks_position('top') # 将x轴刻度线设置在顶部
    ax.xaxis.set_label_position('top') # 将x轴标签设置在顶部

    plt.title('Fraction of Model A Wins for All Non-tied A vs. B Battles', fontsize=16, pad=20) # 增加标题和图表的间距
    plt.xlabel('Model B', fontsize=12)
    plt.ylabel('Model A', fontsize=12)
    plt.xticks(rotation=45, ha='left') # 旋转x轴标签并左对齐
    plt.yticks(rotation=0)
    plt.tight_layout()
    
    plt.savefig(output_path)
    print(f"热力图已保存至: {output_path}")

def main():
    """主函数"""
    print(f"正在从 {DB_PATH} 读取数据...")
    battle_df = get_battle_data(DB_PATH)
    
    if battle_df.empty:
        print("数据库中没有找到已完成的对战记录。")
        return
        
    print(f"共找到 {len(battle_df)} 条非平局的对战记录。")
    
    print("正在计算胜率矩阵...")
    win_rate_matrix = calculate_win_rates(battle_df)
    
    print("正在绘制热力图...")
    plot_heatmap(win_rate_matrix, OUTPUT_IMAGE_PATH)
    print("完成。")

if __name__ == "__main__":
    main()