#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
动态评估器 (Dynamic Evaluator)

负责评估预设和世界书条目中的动态 `enabled` 字段。
"""

from __future__ import annotations

from typing import Any, Union

from .data_models import PresetPrompt, WorldBookEntry
from .macro_manager import MacroManager


class DynamicEvaluator:
    """评估动态enabled字段的专用类"""

    def __init__(self, macro_manager: MacroManager):
        """
        初始化动态评估器。

        :param macro_manager: 用于处理enabled表达式中宏的管理器。
        """
        self.macro_manager = macro_manager

    def evaluate_enabled(self, item: Union[WorldBookEntry, PresetPrompt]) -> bool:
        """
        评估条目的enabled状态（支持动态计算）。

        :param item: 要评估的世界书条目或预设提示。
        :return: 评估后的布尔值结果。
        """
        # 1. 检查缓存
        if item.enabled_cached is not None:
            return item.enabled_cached

        # 2. 获取原始表达式
        expression = getattr(item, 'enabled_expression', None)
        if expression is None:
            expression = item.enabled

        # 3. 根据类型处理
        result = self._evaluate_expression(expression, item.name)

        # 4. 缓存并返回结果
        item.enabled_cached = bool(result)
        return item.enabled_cached

    def _evaluate_expression(self, expression: Any, item_name: str) -> bool:
        """根据表达式的类型和内容进行评估"""
        try:
            if isinstance(expression, bool):
                return expression
            elif isinstance(expression, str):
                # 统一使用宏处理器处理字符串表达式
                # MacroManager会处理传统宏和Python宏
                processed_result = self.macro_manager.process_string(expression, 'preset') # 默认使用preset作用域
                return self._to_bool(processed_result)
            else:
                # 其他类型默认转换为布尔值
                return bool(expression)
        except Exception as e:
            # 错误时默认为False，记录错误但不中断流程
            print(f"⚠️ enabled评估失败 ({item_name}): {e}")
            return False

    def _to_bool(self, value: Any) -> bool:
        """将不同类型的值转换为布尔值"""
        if isinstance(value, bool):
            return value
        
        if isinstance(value, str):
            val_lower = value.strip().lower()
            if val_lower in ('true', '1', 'yes', 'on'):
                return True
            if val_lower in ('false', '0', 'no', 'off', ''):
                return False
        
        # 对于其他情况（包括非空字符串），尝试转换为数字
        try:
            return float(value) != 0
        except (ValueError, TypeError):
            # 如果转换失败，则按Python的默认规则转换
            return bool(value)

    def clear_enabled_cache(self, items: list[Union[WorldBookEntry, PresetPrompt]]) -> None:
        """清空一组条目的enabled缓存"""
        for item in items:
            item.enabled_cached = None
