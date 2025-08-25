import sqlite3
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os

# 定义数据库文件和输出图像的路径
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'arena.db')
OUTPUT_IMAGE_PATH = os.path.join(os.path.dirname(__file__), '..', 'match_count_heatmap.png')

def get_battle_data(db_path):
    """从数据库获取所有已完成的对战数据"""
    with sqlite3.connect(db_path) as conn:
        # 查询所有已完成的对战
        query = """
        SELECT model_a_name, model_b_name
        FROM battles
        WHERE status = 'completed' AND winner != 'skip';
        """
        df = pd.read_sql_query(query, conn)
    return df

def calculate_match_counts(df):
    """计算模型之间的对战场次"""
    # 统计所有参与对战的模型
    models = pd.unique(df[['model_a_name', 'model_b_name']].values.ravel('K'))
    
    # 初始化一个空的 DataFrame 用于存储场次
    match_count_matrix = pd.DataFrame(index=models, columns=models, dtype=int).fillna(0)

    for index, row in df.iterrows():
        model_a = row['model_a_name']
        model_b = row['model_b_name']
        # 两个方向都增加计数，以保证矩阵对称
        match_count_matrix.loc[model_a, model_b] += 1
        match_count_matrix.loc[model_b, model_a] += 1
        
    return match_count_matrix

def plot_heatmap(match_count_matrix, output_path):
    """绘制对战场次热力图"""
    if match_count_matrix.empty:
        print("没有足够的数据来生成热力图。")
        return
        
    # 对模型名称进行排序
    sorted_models = sorted(match_count_matrix.index)
    sorted_matrix = match_count_matrix.loc[sorted_models, sorted_models]

    plt.figure(figsize=(16, 14))
    sns.heatmap(
        sorted_matrix,
        annot=True,
        annot_kws={"size": 8},
        fmt=".0f",  # 使用浮点数格式，显示0位小数（即整数）
        cmap="viridis", # 换一个颜色映射
        linewidths=.5,
        linecolor='black',
        cbar_kws={'label': 'Number of Battles'}
    )
    
    ax = plt.gca()
    ax.xaxis.set_ticks_position('top')
    ax.xaxis.set_label_position('top')

    plt.title('Number of Battles Between Models', fontsize=16, pad=20)
    plt.xlabel('Model B', fontsize=12)
    plt.ylabel('Model A', fontsize=12)
    plt.xticks(rotation=45, ha='left')
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
        
    print(f"共找到 {len(battle_df)} 条已完成的对战记录。")
    
    print("正在计算对战场次矩阵...")
    match_count_matrix = calculate_match_counts(battle_df)
    
    print("正在绘制热力图...")
    plot_heatmap(match_count_matrix, OUTPUT_IMAGE_PATH)
    print("完成。")

if __name__ == "__main__":
    main()