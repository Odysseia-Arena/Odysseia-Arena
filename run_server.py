# run_server.py
import uvicorn

if __name__ == "__main__":
    print("正在启动创意写作大模型竞技场服务器...")
    print("请确保已安装依赖: pip install fastapi uvicorn")
    print("访问地址: http://localhost:8001")
    print("API文档地址 (Swagger UI): http://localhost:8001/docs")

    # 使用 uvicorn 启动 FastAPI 应用
    # "src.arena_server:app" 指向 src/arena_server.py 文件中的 app 实例
    # reload=True 使得代码修改后服务器会自动重启，方便开发调试
    try:
        uvicorn.run("src.arena_server:app", host="0.0.0.0", port=8001, reload=True)
    except ImportError:
        print("\n错误: 无法启动服务器。请确保安装了 uvicorn。")
        print("运行命令: pip install uvicorn")
    except Exception as e:
        print(f"\n启动服务器时发生错误: {e}")