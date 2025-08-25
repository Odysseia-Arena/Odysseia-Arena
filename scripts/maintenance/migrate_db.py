# scripts/migrate_db.py
"""
数据库迁移脚本。

用于安全地更新现有数据库的表结构，而不会丢失数据。
这个脚本是幂等的，可以安全地多次运行。

用法:
    python -m scripts.migrate_db
"""
import os
import sys

# 将项目根目录添加到Python路径中
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from src.data import storage

def add_is_active_to_models():
    """
    检查 models 表是否存在 is_active 列，如果不存在，则添加它。
    """
    print("正在检查 'models' 表的 'is_active' 列...")
    try:
        with storage.db_access() as conn:
            cursor = conn.cursor()
            
            # 使用 PRAGMA table_info 获取表的列信息
            cursor.execute("PRAGMA table_info(models)")
            columns = [row['name'] for row in cursor.fetchall()]
            
            if 'is_active' not in columns:
                print("'is_active' 列不存在，正在添加...")
                # 添加列，并为现有数据设置默认值为 1 (True)
                cursor.execute("ALTER TABLE models ADD COLUMN is_active BOOLEAN DEFAULT 1 NOT NULL")
                conn.commit()
                print("成功添加 'is_active' 列到 'models' 表。")
            else:
                print("'is_active' 列已存在，无需操作。")

    except Exception as e:
        print(f"在处理 'models' 表时发生错误: {e}")
        raise

def main():
    print("--- 开始数据库迁移 ---")
    
    try:
        # 确保数据库和基础表结构存在
        storage.initialize_storage()
        
        # 执行迁移任务
        add_is_active_to_models()
        
        print("\n--- 数据库迁移完成 ---")
        print("数据库结构现在是最新的。")

    except Exception as e:
        print(f"\n--- 迁移失败 ---")
        print(f"迁移过程中发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()