import sqlite3
import json
import os

# 定义数据库文件路径和输出文件路径
# 假设 arena.db 和这个脚本在同一个目录，如果不是，请修改此路径
DATABASE_FILE = "../../data/arena.db"
OUTPUT_JSON_FILE = "battle_data.json"

def extract_battles_to_json(db_path: str, output_path: str):
    """
    从 SQLite 数据库中提取所有对战记录并保存为 JSON 文件。
    
    Args:
        db_path (str): 数据库文件路径。
        output_path (str): 输出 JSON 文件路径。
    """
    print(f"开始执行提取任务：从 {db_path} 提取数据到 {output_path}...")

    # 检查数据库文件是否存在
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件 '{db_path}' 不存在。")
        print("请确保 arena.db 文件存在于正确的位置。")
        return

    conn = None
    try:
        # 1. 连接到 SQLite 数据库
        print("正在连接数据库...")
        conn = sqlite3.connect(db_path)
        
        # 2. 设置 row_factory 为 sqlite3.Row
        # 这一步非常关键，它允许我们将查询结果的每一行当作字典来访问，方便后续转换为 JSON
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 3. 查询 battles 表中的所有记录
        # 3. 查询 battles 表中的指定字段
        # 我们只提取需要的字段，以减小输出文件的大小
        print("正在查询 'battles' 表中的指定数据...")
        # 添加 ORDER BY timestamp ASC 可以让输出的记录按时间顺序排列
        cursor.execute("SELECT model_a_name, model_b_name, prompt, response_a, response_b FROM battles ORDER BY timestamp ASC")
        
        # 4. 获取所有查询结果
        # 由于数据库文件不大（约21MB），我们可以安全地一次性读取所有数据到内存
        rows = cursor.fetchall()
        print(f"共找到 {len(rows)} 条对战记录。")

        if not rows:
            print("未找到任何记录，不生成 JSON 文件。")
            return

        # 5. 将 sqlite3.Row 对象列表转换为标准的 Python 字典列表
        # 这是为了能被 json 库正确序列化
        battles_data = [dict(row) for row in rows]

        # 6. 将数据写入 JSON 文件
        print(f"正在将数据写入 JSON 文件: {output_path}...")
        with open(output_path, 'w', encoding='utf-8') as f:
            # ensure_ascii=False 确保中文字符能正确显示而不是被转义
            # indent=4 使输出的 JSON 文件格式整齐易读
            json.dump(battles_data, f, ensure_ascii=False, indent=4)

        print("提取和转换成功完成。")

    except sqlite3.OperationalError as e:
        # 捕获数据库操作错误，例如表不存在或文件损坏
        print(f"数据库操作错误: {e}")
        if "no such table: battles" in str(e):
            print("错误：在数据库中找不到 'battles' 表。请检查数据库文件是否正确。")
    except sqlite3.Error as e:
        # 捕获其他 SQLite 错误
        print(f"数据库错误: {e}")
    except IOError as e:
        # 捕获文件写入错误（例如权限问题）
        print(f"文件写入错误: {e}")
    except Exception as e:
        # 捕获其他未知错误
        print(f"发生未知错误: {e}")
    finally:
        # 7. 确保数据库连接在任何情况下都会被关闭
        if conn:
            conn.close()
            print("数据库连接已关闭。")

# 脚本主入口
if __name__ == "__main__":
    extract_battles_to_json(DATABASE_FILE, OUTPUT_JSON_FILE)