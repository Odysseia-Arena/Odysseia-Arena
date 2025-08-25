# arena_server.py
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import time

# 导入核心模块
from . import config
from . import storage
from . import battle_controller
from . import vote_controller
from . import elo_rating
from .battle_controller import RateLimitError
from . import battle_cleaner
from .logger_config import log_event, log_error, logger
from . import file_watcher
from . import tier_manager

# 初始化FastAPI应用
app = FastAPI(title="创意写作大模型竞技场后端", version="1.0.0")

# CORS配置，允许所有来源（在生产环境中应更严格）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 服务器启动事件 ---
@app.on_event("startup")
async def startup_event():
    logger.info("服务器启动中，开始验证配置...")
    
    # 第一步：验证配置是否满足最低要求
    is_valid, errors = config.validate_configuration()
    if not is_valid:
        logger.critical("配置验证失败，系统无法启动:")
        for error in errors:
            logger.critical(f"  - {error}")
        log_error("配置验证失败", {"errors": errors})
        # 阻止服务器启动
        raise Exception(f"Server startup failed: Configuration validation errors: {'; '.join(errors)}")
    
    logger.info("配置验证通过，开始初始化存储...")
    try:
        # 初始化存储（创建表和字段）
        storage.initialize_storage()
        
        # 初始化模型等级（如果需要）
        tier_manager.initialize_model_tiers()

        # 在启动时加载一次以获取数量
        prompts_count = len(config.load_fixed_prompts())
        models_count = len(config.get_models())
        log_event("SERVER_STARTUP", {
            "status": "success",
            "models_loaded": models_count,
            "fixed_prompts_loaded": prompts_count
        })
        logger.info(f"服务器启动成功！已加载 {models_count} 个模型，{prompts_count} 个固定提示词。")
    except Exception as e:
        log_error(f"存储初始化失败: {e}", {"step": "initialize_storage"})
        logger.critical("服务器启动失败：存储初始化错误。", exc_info=True)
        # 如果存储初始化失败，服务器不应继续运行
        raise Exception("Server startup failed due to storage initialization error.")

    # 启动后台清理任务
    battle_cleaner.run_battle_cleaner()
    
    # 启动每日升降级任务
    battle_cleaner.run_promotion_relegation_scheduler()

    # 启动配置文件热更新监控
    file_watcher.start_file_watcher()

# --- Pydantic模型定义（用于请求体验证和响应结构） ---

class BattleRequest(BaseModel):
    # 对战类型，现在是 'high_tier' 或 'low_tier'
    battle_type: str
    # 自定义提示词字段保留，但当前逻辑不使用
    custom_prompt: Optional[str] = None
    discord_id: Optional[str] = None # 添加 discord_id 字段

class BattleBackRequest(BaseModel):
    discord_id: str

class UnstuckRequest(BaseModel):
    discord_id: str

class VoteRequest(BaseModel):
    vote_choice: str # "model_a", "model_b", 或 "tie"
    discord_id: str # Discord用户ID

# --- API端点 ---

@app.post("/battle", status_code=status.HTTP_201_CREATED)
async def create_battle(request_body: BattleRequest):
    """创建新的对战"""
    logger.info(f"Received request for /battle from discord_id: {request_body.discord_id}")
    try:
        # 验证对战类型是否有效
        if request_body.battle_type not in ["high_tier", "low_tier"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的对战类型。请选择 'high_tier' (高端) 或 'low_tier' (低端)。"
            )

        battle_details = await battle_controller.create_battle(
            battle_type=request_body.battle_type,
            custom_prompt=request_body.custom_prompt,
            discord_id=request_body.discord_id
        )
        log_event("BATTLE_CREATED", {"battle_id": battle_details["battle_id"], "type": request_body.battle_type})
        return battle_details
    except RateLimitError as e:
        # 捕获速率限制错误
        log_event("RATE_LIMIT_EXCEEDED", {"discord_id": request_body.discord_id, "error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"message": str(e), "available_at": e.available_at}
        )
    except ValueError as e:
        # 处理参数验证错误（例如模型数量不足）
        log_error(str(e), {"step": "create_battle_validation", "request": request_body.dict()})
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as e:
        # 重新抛出已处理的HTTP异常
        raise e
    except Exception as e:
        # 处理未知错误
        logger.exception("创建对战时发生未知错误") # 记录堆栈跟踪
        log_error(f"创建对战时发生未知错误: {e}", {"step": "create_battle_internal"})
        raise HTTPException(status_code=500, detail="服务器内部错误。")

@app.post("/battleback")
async def get_battle_back(request_body: BattleBackRequest):
    """获取用户上一个对战的信息"""
    logger.info(f"Received request for /battleback from discord_id: {request_body.discord_id}")
    try:
        battle = storage.get_latest_battle_by_discord_id(request_body.discord_id)
        if not battle:
            raise HTTPException(status_code=404, detail="未找到您的对战记录。")

        status = battle["status"]
        if status == "completed":
            # 逻辑复用 get_battle_details
            return await get_battle_details(battle["battle_id"])
        elif status == "pending_vote":
            # 返回匿名化的对战信息以供投票
            return {
                "battle_id": battle["battle_id"],
                "prompt": battle["prompt"],
                "response_a": battle["response_a"],
                "response_b": battle["response_b"],
            }
        elif status == "pending_generation":
            return {"message": "创建对战中： 这通常需要一些时间，机器人会在创建成功后通知你。"}
        
        # 对于其他可能的状态，返回通用消息
        raise HTTPException(status_code=404, detail="未找到可供操作的对战。")

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception("处理 /battleback 请求时发生未知错误")
        log_error(f"处理 /battleback 时发生未知错误: {e}", {"discord_id": request_body.discord_id})
        raise HTTPException(status_code=500, detail="服务器内部错误。")

@app.post("/battleunstuck")
async def unstuck_battle_endpoint(request_body: UnstuckRequest):
    """处理用户的“脱离卡死”请求"""
    logger.info(f"Received request for /battleunstuck from discord_id: {request_body.discord_id}")
    try:
        was_stuck = battle_controller.unstuck_battle(request_body.discord_id)
        if was_stuck:
            log_event("BATTLE_UNSTUCK", {"discord_id": request_body.discord_id})
            return {"message": "您卡住的对战已被清除，现在可以重新开始了。"}
        else:
            log_event("BATTLE_UNSTUCK_NOT_FOUND", {"discord_id": request_body.discord_id})
            return {"message": "没有找到需要清除的对战。"}
    except Exception as e:
        logger.exception("处理 /battleunstuck 请求时发生未知错误")
        log_error(f"处理 /battleunstuck 时发生未知错误: {e}", {"discord_id": request_body.discord_id})
        raise HTTPException(status_code=500, detail="服务器内部错误。")

@app.post("/vote/{battle_id}")
async def submit_vote(battle_id: str, vote_request: VoteRequest):
    """提交投票"""
    try:
        result = vote_controller.submit_vote(
            battle_id=battle_id,
            vote_choice=vote_request.vote_choice,
            discord_id=vote_request.discord_id
        )

        # 处理vote_controller返回的错误状态（例如防作弊拒绝）
        if result["status"] == "error":
            log_event("VOTE_REJECTED", {"battle_id": battle_id, "reason": result["message"]})
            # 这里使用400表示请求无效（例如重复投票或速率限制）
            raise HTTPException(status_code=400, detail=result["message"])
        
        # 投票成功
        log_event("VOTE_SUBMITTED", {
            "battle_id": battle_id, 
            "choice": vote_request.vote_choice, 
            "revealed_winner": result["winner"]
        })
        return result
    except FileNotFoundError:
        # 对战ID不存在
        raise HTTPException(status_code=404, detail="对战ID不存在。")
    except ValueError as e:
        # 无效的投票选项
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as e:
        # 重新抛出已处理的HTTP异常
        raise e
    except Exception as e:
        # 处理未知错误
        logger.exception("提交投票时发生未知错误")
        log_error(f"提交投票时发生未知错误: {e}", {"battle_id": battle_id})
        raise HTTPException(status_code=500, detail="服务器内部错误。")

@app.get("/leaderboard")
async def get_leaderboard():
    """获取排行榜"""
    logger.info("Received request for /leaderboard")
    try:
        start_time = time.time()
        # 这一步会自动处理缓存逻辑
        leaderboard = elo_rating.generate_leaderboard()
        duration = time.time() - start_time
        # 记录性能指标（可选）
        log_event("LEADERBOARD_REQUEST", {"duration_ms": round(duration * 1000, 2)})
        return {"leaderboard": leaderboard}
    except Exception as e:
        logger.exception("生成排行榜时发生错误")
        log_error(f"生成排行榜时发生错误: {e}", {"step": "get_leaderboard"})
        raise HTTPException(status_code=500, detail="无法生成排行榜。")

@app.get("/battle/{battle_id}")
async def get_battle_details(battle_id: str):
    """获取指定对战的详情"""
    logger.info(f"Received request for /battle/{battle_id}")
    battle = storage.get_battle_record(battle_id)
    if not battle:
        raise HTTPException(status_code=404, detail="对战ID不存在。")
    
    # 关键逻辑：如果比赛未完成（pending_vote），隐藏模型名称以保持盲测
    if battle["status"] != "completed":
        return {
            "battle_id": battle["battle_id"],
            "prompt": battle["prompt"],
            "response_a": battle["response_a"],
            "response_b": battle["response_b"],
            "status": battle["status"]
        }
    
    # 如果比赛已完成，返回完整详情（包括模型名称和结果）
    # 将 model_a_id/b_id 重命名为 model_a/b 以匹配API文档
    battle["model_a"] = battle.pop("model_a_name", battle.get("model_a_id"))
    battle["model_b"] = battle.pop("model_b_name", battle.get("model_b_id"))
    battle.pop("model_a_id", None)
    battle.pop("model_b_id", None)
    
    if battle.get("winner") == "tie":
        battle["winner"] = "Tie"
        
    return battle

# 健康检查端点
@app.get("/health")
async def health_check():
    logger.info("Received request for /health")
    try:
        total_users = storage.get_total_users_count()
        completed_battles = storage.get_completed_battles_count()
        
        return {
            "status": "ok",
            "models_count": len(config.get_models()),
            "fixed_prompts_count": len(config.load_fixed_prompts()),
            "recorded_users_count": total_users,
            "completed_battles_count": completed_battles
        }
    except Exception as e:
        logger.exception("健康检查时发生数据库错误")
        raise HTTPException(status_code=503, detail=f"数据库服务不可用: {e}")