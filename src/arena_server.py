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
from .logger_config import log_event, log_error, logger

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
        # 初始化存储（创建文件和初始评分）
        storage.initialize_storage()
        
        # 在启动时加载一次以获取数量
        prompts_count = len(config.load_fixed_prompts())
        log_event("SERVER_STARTUP", {
            "status": "success",
            "models_loaded": len(config.AVAILABLE_MODELS),
            "fixed_prompts_loaded": prompts_count
        })
        logger.info(f"服务器启动成功！已加载 {len(config.AVAILABLE_MODELS)} 个模型，{prompts_count} 个固定提示词。")
    except Exception as e:
        log_error(f"存储初始化失败: {e}", {"step": "initialize_storage"})
        logger.critical("服务器启动失败：存储初始化错误。")
        # 如果存储初始化失败，服务器不应继续运行
        raise Exception("Server startup failed due to storage initialization error.")

# --- Pydantic模型定义（用于请求体验证和响应结构） ---

class BattleRequest(BaseModel):
    # 默认为第一阶段的固定提示词对战
    battle_type: str = "fixed" 
    # 第二阶段的自定义提示词（可选，功能已实现但暂时隐藏）
    custom_prompt: Optional[str] = None

class VoteRequest(BaseModel):
    vote_choice: str # "model_a", "model_b", 或 "tie"
    discord_id: str # Discord用户ID

# --- API端点 ---

@app.post("/battle", status_code=status.HTTP_201_CREATED)
async def create_battle(request_body: BattleRequest):
    """创建新的对战"""
    try:
        # 第一阶段限制：只支持 fixed
        # 实时对战逻辑现在由 battle_controller 处理
        # battle_type 和 custom_prompt 的验证也移到 controller 中
        battle_details = await battle_controller.create_battle(
            battle_type=request_body.battle_type,
            custom_prompt=request_body.custom_prompt
        )
        log_event("BATTLE_CREATED", {"battle_id": battle_details["battle_id"], "type": request_body.battle_type})
        return battle_details
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
    return battle

# 健康检查端点
@app.get("/health")
async def health_check():
    return {"status": "ok", "models_count": len(config.AVAILABLE_MODELS), "fixed_prompts_count": len(config.FIXED_PROMPTS)}