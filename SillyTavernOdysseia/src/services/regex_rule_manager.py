#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
正则规则管理器 (Regex Rule Manager)

负责管理正则表达式替换规则，包括：
- 加载和解析规则文件
- 按优先级排序规则
- 应用规则到不同类型的内容
- 处理宏与正则的交互
- 支持不同的作用效果（修改原始提示词/用户视图/AI模型视图）
"""

from __future__ import annotations

import os
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from pathlib import Path

from .data_models import RegexRule, ContentPart


class RegexRuleManager:
    """正则表达式规则管理器"""

    def __init__(self, rules_directory: str = None):
        """初始化规则管理器"""
        self.rules: List[RegexRule] = []
        self.compiled_rules: Dict[str, Dict[str, Any]] = {}  # 缓存编译后的正则表达式
        self.rules_directory = rules_directory or "data/regex_rules"
        
        # 规则被应用后的统计信息
        self.applied_stats: Dict[str, Dict[str, int]] = {}  # rule_id -> {applied_count, matched_count}
        
        # 默认自动加载规则
        if os.path.exists(self.rules_directory):
            self.load_rules()

    def load_rules(self) -> int:
        """
        从规则目录加载所有规则文件
        
        Returns:
            加载的规则数量
        """
        loaded_count = 0
        self.rules = []
        
        if not os.path.exists(self.rules_directory):
            print(f"⚠️ 规则目录不存在: {self.rules_directory}")
            return 0
            
        try:
            # 遍历目录中的所有JSON文件
            for file_path in Path(self.rules_directory).glob("*.json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        rules_data = json.load(f)
                        
                    # 支持单个规则或规则列表
                    if isinstance(rules_data, list):
                        for rule_data in rules_data:
                            self._add_rule_from_dict(rule_data)
                            loaded_count += 1
                    else:
                        self._add_rule_from_dict(rules_data)
                        loaded_count += 1
                        
                except Exception as e:
                    print(f"⚠️ 加载规则文件失败 {file_path}: {e}")
            
            # 重新编译和排序规则
            self._compile_rules()
            self._sort_rules()
            
            print(f"📝 成功加载 {loaded_count} 个正则规则")
            return loaded_count
            
        except Exception as e:
            print(f"⚠️ 规则加载失败: {e}")
            return 0

    def _add_rule_from_dict(self, rule_data: Dict[str, Any]) -> None:
        """从字典中创建规则并添加到规则列表"""
        try:
            rule = RegexRule(
                id=rule_data.get("id", f"rule_{len(self.rules)}"),
                name=rule_data.get("name", "未命名规则"),
                enabled=rule_data.get("enabled", True),
                find_regex=rule_data.get("find_regex", ""),
                replace_regex=rule_data.get("replace_regex", ""),
                targets=rule_data.get("targets", ["user", "assistant_response", "world_book", "preset", "assistant_thinking"]),
                min_depth=rule_data.get("min_depth"),
                max_depth=rule_data.get("max_depth"),
                min_order=rule_data.get("min_order"),
                max_order=rule_data.get("max_order"),
                placement=rule_data.get("placement", "after_macro"),
                views=rule_data.get("views", ["original"]),
                description=rule_data.get("description", ""),
                enabled_expression=rule_data.get("enabled_expression")
            )
            self.rules.append(rule)
        except Exception as e:
            print(f"⚠️ 创建规则失败: {e}")

    def _compile_rules(self) -> None:
        """编译所有规则的正则表达式"""
        self.compiled_rules = {}
        
        for rule in self.rules:
            if not rule.enabled:
                continue
                
            try:
                compiled_regex = re.compile(rule.find_regex)
                self.compiled_rules[rule.id] = {
                    "pattern": compiled_regex,
                    "replace": rule.replace_regex
                }
            except Exception as e:
                print(f"⚠️ 正则表达式编译失败 [{rule.id}]: {e}")

    def _sort_rules(self) -> None:
        """按targets数量和id排序规则"""
        self.rules.sort(key=lambda r: (len(r.targets), r.id))

    def add_rule(self, rule: RegexRule) -> bool:
        """
        添加一条新规则
        
        Args:
            rule: 要添加的规则
            
        Returns:
            是否添加成功
        """
        # 检查ID是否已存在
        if any(r.id == rule.id for r in self.rules):
            print(f"⚠️ 规则ID已存在: {rule.id}")
            return False
            
        try:
            # 测试编译正则表达式
            re.compile(rule.find_regex)
            
            # 添加规则
            self.rules.append(rule)
            
            # 更新编译和排序
            self._compile_rules()
            self._sort_rules()
            
            return True
        except Exception as e:
            print(f"⚠️ 添加规则失败: {e}")
            return False

    def remove_rule(self, rule_id: str) -> bool:
        """
        移除一条规则
        
        Args:
            rule_id: 要移除的规则ID
            
        Returns:
            是否移除成功
        """
        original_length = len(self.rules)
        self.rules = [r for r in self.rules if r.id != rule_id]
        
        if len(self.rules) < original_length:
            # 移除成功，更新编译规则
            if rule_id in self.compiled_rules:
                del self.compiled_rules[rule_id]
            return True
        else:
            print(f"⚠️ 规则不存在: {rule_id}")
            return False

    def enable_rule(self, rule_id: str, enabled: bool = True) -> bool:
        """
        启用或禁用规则
        
        Args:
            rule_id: 规则ID
            enabled: 是否启用
            
        Returns:
            是否操作成功
        """
        for rule in self.rules:
            if rule.id == rule_id:
                rule.enabled = enabled
                self._compile_rules()  # 重新编译规则
                return True
                
        print(f"⚠️ 规则不存在: {rule_id}")
        return False

    def get_rules(self) -> List[RegexRule]:
        """获取所有规则"""
        return self.rules.copy()

    def get_rule(self, rule_id: str) -> Optional[RegexRule]:
        """获取指定ID的规则"""
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None

    def save_rules(self, file_path: str) -> bool:
        """
        将规则保存到文件
        
        Args:
            file_path: 保存的文件路径
            
        Returns:
            是否保存成功
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 将规则转换为字典
            rules_data = []
            for rule in self.rules:
                rule_dict = {
                    "id": rule.id,
                    "name": rule.name,
                    "enabled": rule.enabled,
                    "find_regex": rule.find_regex,
                    "replace_regex": rule.replace_regex,
                    "targets": rule.targets,
                    "min_depth": rule.min_depth,
                    "max_depth": rule.max_depth,
                    "min_order": rule.min_order,
                    "max_order": rule.max_order,
                    "placement": rule.placement,
                    "views": rule.views,
                    "description": rule.description
                }
                
                if rule.enabled_expression is not None:
                    rule_dict["enabled_expression"] = rule.enabled_expression
                    
                rules_data.append(rule_dict)
                
            # 写入文件
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(rules_data, f, ensure_ascii=False, indent=2)
                
            return True
        except Exception as e:
            print(f"⚠️ 保存规则失败: {e}")
            return False

    def apply_regex_to_content(self,
                              content: str,
                              source_type: str,
                              depth: Optional[int] = None,
                              order: Optional[int] = None,
                              placement: str = "after_macro",
                              view: str = "original") -> str:
        """
        将适用的正则表达式规则应用到内容
        
        Args:
            content: 要处理的内容
            source_type: 内容的来源类型
            depth: 内容的depth值
            order: 内容的order值
            placement: 处理阶段 ("before_macro_skip", "before_macro_include", "after_macro")
            view: 应用的视图类型 ("original", "user_view", "assistant_view")
            
        Returns:
            处理后的内容
        """
        if not content or not self.rules:
            return content
            
        # 将source_type映射到目标类型
        target_mapping = {
            "user": "user",  # 直接映射
            "assistant_response": "assistant_response",  # 直接映射
            "conversation": "user" if "user_message" in content else "assistant_response",
            "world": "world_book",
            "world_book": "world_book",  # 直接映射
            "preset": "preset",
            "char": "assistant_thinking",
            "assistant_thinking": "assistant_thinking"  # 直接映射
        }
        
        target = target_mapping.get(source_type, source_type)  # 如果没有映射，直接使用原值
        
        # 筛选适用于当前内容、处理阶段和深度/次序的规则
        applicable_rules = []
        for rule in self.rules:
            if not rule.enabled:
                continue
                
            # 检查目标类型是否匹配
            if target not in rule.targets:
                continue
                
            # 检查处理阶段是否匹配
            if rule.placement != placement:
                continue
                
            # 检查视图类型是否匹配
            if view not in rule.views:
                continue
                
            # 检查depth和order是否在范围内
            if depth is not None:
                if rule.min_depth is not None and depth < rule.min_depth:
                    continue
                if rule.max_depth is not None and depth > rule.max_depth:
                    continue
            
            if order is not None:
                if rule.min_order is not None and order < rule.min_order:
                    continue
                if rule.max_order is not None and order > rule.max_order:
                    continue
                
            applicable_rules.append(rule)
        
        # 如果没有适用的规则，直接返回原始内容
        if not applicable_rules:
            return content
            
        # 按优先级应用规则
        result = content
        for rule in applicable_rules:
            if rule.id not in self.compiled_rules:
                continue
                
            try:
                compiled_pattern = self.compiled_rules[rule.id]["pattern"]
                replace_pattern = self.compiled_rules[rule.id]["replace"]
                
                # 应用正则替换
                before_result = result
                result = compiled_pattern.sub(replace_pattern, result)
                
                # 更新统计信息
                if rule.id not in self.applied_stats:
                    self.applied_stats[rule.id] = {"applied_count": 0, "matched_count": 0}
                    
                self.applied_stats[rule.id]["applied_count"] += 1
                if before_result != result:
                    self.applied_stats[rule.id]["matched_count"] += 1
                    
            except Exception as e:
                print(f"⚠️ 应用规则失败 [{rule.id}]: {e}")
                
        return result

    def apply_regex_to_content_part(self, content_part: ContentPart, placement: str, depth: Optional[int] = None, order: Optional[int] = None, view: str = "original") -> str:
        """
        将适用的正则表达式规则应用到内容部分
        
        Args:
            content_part: 要处理的内容部分
            placement: 处理阶段
            depth: 内容的depth值
            order: 内容的order值
            view: 应用的视图类型 ("original", "user_view", "assistant_view")
            
        Returns:
            处理后的内容
        """
        return self.apply_regex_to_content(
            content=content_part.content,
            source_type=content_part.source_type,
            depth=depth,
            order=order,
            placement=placement,
            view=view
        )

    def get_stats(self) -> Dict[str, Dict[str, int]]:
        """获取规则应用统计信息"""
        return self.applied_stats.copy()

    def reset_stats(self) -> None:
        """重置统计信息"""
        self.applied_stats = {}

    def clear(self) -> None:
        """清空所有规则"""
        self.rules = []
        self.compiled_rules = {}
        self.applied_stats = {}