#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
回答选项生成器模块

该模块负责为用户的对话上下文动态生成回答选项。
它通过多步API调用链实现：
1. 调用SillyTavernOdysseia API准备一个干净的、包含引导指令的提示。
2. 调用外部大语言模型(LLM)生成选项。
3. 再次调用SillyTavernOdysseia API处理LLM的响应，确保格式一致性。
4. 解析并存储生成的选项。
"""

import json
import os
import random
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional

from src.services.session_manager import SessionManager
from SillyTavernOdysseia.src.api_interface import ChatAPI, ChatRequest
from src.utils.logger_config import logger
from src.utils import config

# 引导AI生成选项的特定提示词
OPTION_GENERATION_PROMPT = """
<instructions>
Based on the preceding story, provide three distinct and engaging choices for the user to continue the adventure. Format the choices using the following XML structure, ensuring each choice is wrapped in a <choice> tag.
Example:
<choices>
    <choice>Go left towards the dark cave.</choice>
    <choice>Follow the sparkling river upstream.</choice>
    <choice>Climb the tall tree to get a better view.</choice>
</choices>
</instructions>
"""

class ResponseOptionGenerator:
    """处理回答选项生成的服务类"""

    def __init__(self):
        """初始化生成器"""
        self.session_manager = SessionManager()
        self.chat_api = ChatAPI(data_root="SillyTavernOdysseia/data")
        
        # 从config模块加载外部LLM的配置
        self.external_llm_url = config.OPTION_LLM_API_URL
        self.external_llm_api_key = config.OPTION_LLM_API_KEY
        self.external_llm_model = config.OPTION_LLM_MODEL

    def _parse_options_from_xml(self, xml_string: str) -> List[str]:
        """从包含XML的字符串中解析出选项列表"""
        try:
            # 为了健壮性，先从可能包含其他文本的字符串中提取出 <choices> 块
            start_tag = "<choices>"
            end_tag = "</choices>"
            start_index = xml_string.find(start_tag)
            end_index = xml_string.find(end_tag)

            if start_index == -1 or end_index == -1:
                logger.warning(f"在响应中未找到完整的 <choices>...</choices> XML块。")
                return []

            # 提取并解析XML
            clean_xml = xml_string[start_index : end_index + len(end_tag)]
            root = ET.fromstring(clean_xml)
            options = [choice.text.strip() for choice in root.findall('choice') if choice.text]
            return options
        except ET.ParseError as e:
            logger.error(f"解析选项XML失败: {e}\n原始字符串: {xml_string}")
            return []

    async def _generate_options_from_history(self, session_id: str, config_id: str, conversation_history: List[Dict]) -> List[str]:
        """
        从一个给定的对话历史中异步生成回答选项的核心逻辑。
        """
        # 1. 在上下文末尾添加引导性提示
        guide_message = {"role": "user", "content": OPTION_GENERATION_PROMPT}
        generation_input = conversation_history + [guide_message]

        # 2. 第一次调用SillyTavern API，获取用于调用LLM的干净提示
        request = ChatRequest(
            session_id=session_id,
            config_id=config_id,
            input=generation_input,
            output_formats=["clean"]
        )
        response = self.chat_api.chat_input_json(request)
        st_response1 = json.loads(response.to_json())

        if "error" in st_response1:
            logger.error(f"第一次SillyTavern调用失败 (会话: {session_id}): {st_response1.get('error')}")
            return []
        
        messages_for_llm = st_response1.get("clean_prompt", {}).get("assistant_view")
        if not messages_for_llm:
            logger.error(f"第一次SillyTavern调用后未能获取到干净的提示 (会话: {session_id})。")
            return []

        # 3. 异步调用外部LLM生成包含选项的回复
        headers = {
            "Authorization": f"Bearer {self.external_llm_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.external_llm_model,
            "messages": messages_for_llm,
            "temperature": 0.7,
            "max_tokens": 300
        }
        
        # 打印将要发送给LLM的完整提示词
        logger.info(f"发送给选项生成LLM的完整提示词: {json.dumps(messages_for_llm, ensure_ascii=False, indent=2)}")
        
        try:
            # 使用 aiohttp 或类似的库进行异步HTTP请求
            # 为简单起见，我们暂时在事件循环中运行同步请求，但在生产环境中应替换为真正的异步HTTP客户端
            import asyncio
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(self.external_llm_url, headers=headers, json=payload, timeout=45)
            )
            response.raise_for_status()
            llm_response_data = response.json()
            llm_response_content = llm_response_data['choices'][0]['message']['content']
            logger.debug(f"从外部LLM收到响应: {llm_response_content}")

        except requests.RequestException as e:
            logger.error(f"调用外部LLM失败 (会话: {session_id}): {e}")
            return []
        except (KeyError, IndexError) as e:
            logger.error(f"外部LLM响应格式不正确 (会话: {session_id}): {e}")
            return []

        # 4. 第二次调用SillyTavern API处理LLM的回复
        assistant_response_payload = {"role": "assistant", "content": llm_response_content}
        request = ChatRequest(
            session_id=session_id,
            config_id=config_id,
            input=conversation_history,  # 使用原始上下文
            assistant_response=assistant_response_payload,
            output_formats=["clean"]
        )
        response = self.chat_api.chat_input_json(request)
        st_response2 = json.loads(response.to_json())

        if "error" in st_response2:
            logger.error(f"第二次SillyTavern调用失败 (会话: {session_id}): {st_response2.get('error')}")
            return []

        # 5. 从最终响应中提取处理后的内容并解析
        final_messages = st_response2.get("clean_prompt", {}).get("user_view", [])
        if not final_messages:
            logger.error(f"第二次SillyTavern调用后未能获取到最终的用户视图 (会话: {session_id})。")
            return []

        last_message_content = final_messages[-1].get("content", "")
        return self._parse_options_from_xml(last_message_content)

    async def generate_options_for_session(self, session_id: str, discord_id: Optional[str] = None) -> List[str]:
        """
        为给定的session生成、处理并存储回答选项。
        """
        session = self.session_manager.get_or_create_session(session_id, discord_id=discord_id)
        if not session or not session.context_user or not session.config_id_a: # Check for config_id_a
            logger.warning(f"无法为会话 {session_id} 生成选项：缺少上下文或配置ID。")
            return []

        try:
            user_context = json.loads(session.context_user)
            if not isinstance(user_context, list): user_context = []
        except (json.JSONDecodeError, TypeError):
            logger.error(f"解析会话 {session_id} 的用户上下文失败。")
            return []

        # Use a random config from the session for option generation
        config_id_to_use = random.choice([session.config_id_a, session.config_id_b])
        extracted_options = await self._generate_options_from_history(session_id, config_id_to_use, user_context)
        
        self.session_manager.update_session(
            session_id,
            updates={"generated_options": json.dumps(extracted_options, ensure_ascii=False)}
        )
        logger.info(f"为会话 {session_id} 成功生成并存储了 {len(extracted_options)} 个选项。")
        return extracted_options

    async def generate_options_for_response(self, session_id: str, config_id: str, conversation_history: List[Dict]) -> List[str]:
        """
        为一个给定的、临时的对话历史生成回答选项，不存储结果。
        """
        if not config_id or not conversation_history:
            logger.warning(f"无法为会话 {session_id} 生成选项：缺少 config_id 或对话历史。")
            return []
        
        logger.info(f"为会话 {session_id} 的临时上下文生成选项...")
        extracted_options = await self._generate_options_from_history(session_id, config_id, conversation_history)
        logger.info(f"为会话 {session_id} 的临时上下文成功生成了 {len(extracted_options)} 个选项。")
        return extracted_options

# 创建一个全局实例，方便其他模块调用
response_option_generator = ResponseOptionGenerator()