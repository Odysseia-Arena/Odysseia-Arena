# arena_server.py
from fastapi import FastAPI, HTTPException, Request, status, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import time
import datetime
import uuid
import json

# 导入核心模块
from src.utils import config
from src.data import storage
from src.controllers import battle_controller
from src.controllers import vote_controller
from src.rating import glicko2_rating
from src.controllers.battle_controller import RateLimitError
from src.background import battle_cleaner
from src.utils.logger_config import log_event, log_error, logger
from src.background import file_watcher
from src.background import rating_updater
from src.background import database_backup
from src.controllers import tier_manager
from src.services import statistics_calculator
from src.services.session_manager import process_battle_input

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

    # 启动周期性评分更新任务
    rating_updater.start_rating_updater()

    # 启动数据库每小时备份任务
    database_backup.start_backup_scheduler()

# --- Pydantic模型定义（用于请求体验证和响应结构） ---

class BattleRequest(BaseModel):
    # 会话ID
    session_id: str
    # 对战类型，现在是 'high_tier' 或 'low_tier'
    battle_type: str
    # Discord用户ID字段，用于速率限制
    discord_id: Optional[str] = None
    # 用户输入内容
    input: Optional[str] = None

class BattleBackRequest(BaseModel):
    discord_id: str

class UnstuckRequest(BaseModel):
    discord_id: str

class LatestSessionRequest(BaseModel):
    discord_id: str

class VoteRequest(BaseModel):
    vote_choice: str # "model_a", "model_b", 或 "tie"
    discord_id: str # Discord用户ID

class RevealRequest(BaseModel):
    battle_id: str

class RevealResponse(BaseModel):
    model_a_id: Optional[str] = None
    model_b_id: Optional[str] = None
    model_a_name: Optional[str] = None
    model_b_name: Optional[str] = None

class CharacterMessageSelectionRequest(BaseModel):
    session_id: str
    character_messages_id: int  # character_messages的序号/索引
    discord_id: Optional[str] = None # 关联用户

class GenerateOptionsRequest(BaseModel):
    session_id: str
    discord_id: Optional[str] = None # 关联用户

# --- API端点 ---

@app.post("/battle", status_code=status.HTTP_201_CREATED)
async def create_battle(request_body: BattleRequest):
    """创建或继续一场对战"""
    logger.info(f"Received request for /battle from session_id: {request_body.session_id}, discord_id: {request_body.discord_id}")
    try:
        # 验证对战类型
        if request_body.battle_type not in ["high_tier", "low_tier"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的对战类型。")

        # 检查是创建新对战还是继续对战
        if request_body.input is None:
            # --- 场景1: input为null，进行初次对战设置 ---
            logger.info(f"Processing initial battle setup for session_id: {request_body.session_id}")
            
            input_result = await process_battle_input(session_id=request_body.session_id,
                                                      input_string=None,
                                                      discord_id=request_body.discord_id,
                                                      battle_type=request_body.battle_type)
            
            if input_result.get("status") != "success":
                error_detail = input_result.get('error', '未知错误')
                raise HTTPException(status_code=500, detail=f"输入处理失败: {error_detail}")

            # 直接从结果中获取处理好的 character_messages 列表
            character_messages_list = input_result.get("character_messages")
            
            if not character_messages_list or not isinstance(character_messages_list, list):
                raise HTTPException(status_code=500, detail="API响应中缺少有效的character_messages列表")

            return {
                "battle_id": str(uuid.uuid4()), # 这是一个临时的ID，真正的battle在用户选择后创建
                "config": input_result.get("config_data"),
                "character_messages": character_messages_list,
                "status": "pending_character_selection"
            }
        else:
            # --- 场景2: input不为null，用户提交了选择，继续对战 ---
            logger.info(f"Continuing battle for session_id: {request_body.session_id}")
            
            # battle_controller.continue_battle_with_selection 现在会处理所有逻辑，包括保存
            battle_response = await battle_controller.continue_battle_with_selection(
                session_id=request_body.session_id,
                user_input=request_body.input,
                battle_type=request_body.battle_type,
                discord_id=request_body.discord_id
            )
            
            battle_id = battle_response["battle_id"]
            log_event("BATTLE_CONTINUED", {"battle_id": battle_id, "session_id": request_body.session_id})

            # 返回匿名化的对战数据 (选项生成已移至controller)
            return battle_response
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
                "prompt_theme": battle.get("prompt_theme", "general"),
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
        deleted_count = battle_controller.unstuck_battle(request_body.discord_id)
        
        if deleted_count > 0:
            log_event("BATTLES_UNSTUCK", {"discord_id": request_body.discord_id, "count": deleted_count})
            if deleted_count == 1:
                message = "您卡住的1场对战已被清除，现在可以重新开始了。"
            else:
                message = f"您卡住的 {deleted_count} 场对战已被全部清除，现在可以重新开始了。"
            return {"message": message}
        else:
            log_event("BATTLES_UNSTUCK_NOT_FOUND", {"discord_id": request_body.discord_id})
            return {"message": "没有找到需要清除的对战。"}
            
    except Exception as e:
        logger.exception("处理 /battleunstuck 请求时发生未知错误")
        log_error(f"处理 /battleunstuck 时发生未知错误: {e}", {"discord_id": request_body.discord_id})
        raise HTTPException(status_code=500, detail="服务器内部错误。")

@app.post("/sessions/latest", status_code=status.HTTP_200_OK)
async def get_latest_session(request_body: LatestSessionRequest):
    """获取指定discord_id的最新session_id和对话轮数"""
    logger.info(f"Received request for latest session for discord_id: {request_body.discord_id}")
    try:
        session_info = storage.get_latest_session_info_by_discord_id(request_body.discord_id)
        if not session_info:
            raise HTTPException(status_code=404, detail="未找到该用户的会话记录。")
        
        log_event("LATEST_SESSION_FETCHED", {"discord_id": request_body.discord_id, "session_id": session_info["session_id"]})
        return session_info
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception("获取最新会话时发生未知错误")
        log_error(f"获取最新会话时发生未知错误: {e}", {"discord_id": request_body.discord_id})
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
        
        # 生成排行榜主体数据
        leaderboard = glicko2_rating.generate_leaderboard()
        
        # 获取额外的统计数据
        model_stats = statistics_calculator.get_all_models_stats()
        
        # 将统计数据合并到排行榜中
        for model_data in leaderboard:
            model_name = model_data["model_name"]
            if model_name in model_stats:
                stats = model_stats[model_name]
                model_data["battles"] = stats.get("battles", 0)
                model_data["wins"] = stats.get("wins", 0)
                model_data["ties"] = stats.get("ties", 0)
                model_data["skips"] = stats.get("skips", 0)
                model_data["win_rate_percentage"] = stats.get("win_rate_percentage", 0)

        # 计算下次更新时间
        now = datetime.datetime.now()
        next_update_dt = (now + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        next_update_iso = next_update_dt.isoformat()

        duration = time.time() - start_time
        log_event("LEADERBOARD_REQUEST", {"duration_ms": round(duration * 1000, 2)})
        
        return {
            "leaderboard": leaderboard,
            "next_update_time": next_update_iso
        }
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
    
    # Start with a copy of the battle record
    battle_details = dict(battle)

    # If the battle has been revealed, add the friendly 'model_a' and 'model_b' keys.
    if battle_details.get("revealed"):
        battle_details["model_a"] = battle_details.pop("model_a_name", battle_details.get("model_a_id"))
        battle_details["model_b"] = battle_details.pop("model_b_name", battle_details.get("model_b_id"))
    
    # Always remove the specific id/name keys to avoid leaking info.
    battle_details.pop("model_a_id", None)
    battle_details.pop("model_b_id", None)
    battle_details.pop("model_a_name", None)
    battle_details.pop("model_b_name", None)

    if battle_details.get("winner") == "tie":
        battle_details["winner"] = "Tie"
        
    return battle_details

# --- 新增的统计信息端点 ---
@app.get("/api/battle_statistics")
async def get_battle_statistics():
    """获取模型对战的详细统计数据，包括胜率和对战场次。"""
    logger.info("Received request for /api/battle_statistics")
    try:
        stats = statistics_calculator.get_battle_statistics()
        return stats
    except Exception as e:
        logger.exception("生成对战统计数据时发生错误")
        log_error(f"生成对战统计数据时发生错误: {e}", {"step": "get_battle_statistics"})
        raise HTTPException(status_code=500, detail="无法生成对战统计数据。")

@app.get("/api/prompt_statistics")
async def get_prompt_statistics():
    """获取基于每个提示词的详细对战统计。"""
    logger.info("Received request for /api/prompt_statistics")
    try:
        stats = statistics_calculator.get_prompt_statistics()
        return {"prompt_statistics": stats}
    except Exception as e:
        logger.exception("生成提示词统计数据时发生错误")
        log_error(f"生成提示词统计数据时发生错误: {e}", {"step": "get_prompt_statistics"})
        raise HTTPException(status_code=500, detail="无法生成提示词统计数据。")

# --- Character Messages 选择端点 ---
@app.post("/character_selection")
async def submit_character_selection(request_body: CharacterMessageSelectionRequest):
    """用户提交选择的character_message"""
    logger.info(f"Received character selection request for session_id: {request_body.session_id}")
    try:
        from src.services.session_manager import SessionManager
        
        session_manager = SessionManager()
        
        # 验证session是否存在
        session = session_manager.get_or_create_session(request_body.session_id, discord_id=request_body.discord_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在或无法创建。"
            )
        
        # 验证character_messages是否存在
        if not session.character_messages_user_view:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该会话尚未获取character_messages。"
            )
        
        # 解析character_messages并验证索引
        try:
            character_messages_user = json.loads(session.character_messages_user_view)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="character_messages数据格式错误。"
            )
        
        if not (0 <= request_body.character_messages_id < len(character_messages_user)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的character_messages_id。有效范围: 0-{len(character_messages_user)-1}"
            )
        
        # 保存用户选择
        success = session_manager.set_character_message_selection(
            request_body.session_id,
            request_body.character_messages_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="保存character_message选择失败。"
            )
        
        # 将选择的character_message添加到上下文
        context_success = session_manager.add_selected_message_to_context(request_body.session_id, discord_id=request_body.discord_id)
        
        if not context_success:
            # 如果添加到上下文失败，记录但不阻止响应
            logger.warning(f"添加character_message到上下文失败，session_id: {request_body.session_id}")
        
        # 自动生成第一组选项
        from src.services.response_generator import response_option_generator
        generated_options = await response_option_generator.generate_options_for_session(
            request_body.session_id,
            discord_id=request_body.discord_id
        )

        # 获取选择的消息（user_view）用于响应
        selected_message = character_messages_user[request_body.character_messages_id]
        
        log_event("CHARACTER_MESSAGE_SELECTED", {
            "session_id": request_body.session_id,
            "selected_index": request_body.character_messages_id,
            "context_added": context_success,
            "options_generated": len(generated_options)
        })
        
        return {
            "status": "success",
            "message": "character_message选择已保存，并已添加到对话上下文。",
            "session_id": request_body.session_id,
            "selected_index": request_body.character_messages_id,
            "selected_message": selected_message,
            "context_updated": context_success,
            "generated_options": generated_options
        }
        
    except HTTPException as e:
        # 重新抛出已处理的HTTP异常
        raise e
    except Exception as e:
        # 处理未知错误
        logger.exception("处理character_message选择时发生未知错误")
        log_error(f"处理character_message选择时发生未知错误: {e}", {"step": "character_selection"})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="处理character_message选择时发生内部错误。"
        )

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

@app.post("/reveal/{battle_id}", response_model=RevealResponse)
async def reveal_models(battle_id: str):
    """揭示一场对战的模型名称"""
    logger.info(f"Received request to reveal models for battle_id: {battle_id}")
    try:
        model_info = battle_controller.reveal_battle_models(battle_id)
        if not model_info:
            raise HTTPException(status_code=404, detail="对战ID不存在或无法揭示。")
        
        log_event("MODELS_REVEALED", {"battle_id": battle_id})
        return model_info
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception(f"揭示模型时发生未知错误 for battle {battle_id}")
        log_error(f"揭示模型时发生未知错误: {e}", {"battle_id": battle_id})
        raise HTTPException(status_code=500, detail="揭示模型时发生服务器内部错误。")

@app.post("/generate_options", status_code=status.HTTP_200_OK)
async def generate_options_endpoint(request_body: GenerateOptionsRequest):
    """为当前会话上下文重新生成回答选项。"""
    logger.info(f"Received request to regenerate options for session_id: {request_body.session_id}")
    try:
        from src.services.response_generator import response_option_generator
        from src.services.session_manager import SessionManager

        # 检查会话是否存在
        session_manager = SessionManager()
        session = session_manager.get_or_create_session(request_body.session_id, discord_id=request_body.discord_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在。")

        # 生成新选项
        new_options = await response_option_generator.generate_options_for_session(request_body.session_id)

        log_event("OPTIONS_REGENERATED", {
            "session_id": request_body.session_id,
            "options_count": len(new_options)
        })

        return {
            "status": "success",
            "session_id": request_body.session_id,
            "generated_options": new_options
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception(f"重新生成选项时发生未知错误 for session {request_body.session_id}")
        log_error(f"重新生成选项时发生未知错误: {e}", {"session_id": request_body.session_id})
        raise HTTPException(status_code=500, detail="重新生成选项时发生服务器内部错误。")