#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
正则脚本系统全面测试脚本

测试内容包括：
1. 酒馆正则转换功能验证
2. RegexRule数据模型验证
3. RegexRuleManager功能测试
4. 不同placement类型测试
5. 不同views类型测试
6. 深度和次序范围控制测试
7. 与其他系统组件的集成测试
8. 边界条件和错误处理测试
"""

import sys
import os
import json
import tempfile
from typing import Dict, List, Any, Optional
from pathlib import Path

# 确保可以导入项目模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.regex_rule_manager import RegexRuleManager
from src.services.data_models import ContentPart, ChatMessage, MessageRole, RegexRule
from scripts.convert_tavern_regex import convert_tavern_regex, map_placement_to_targets

# 颜色常量
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

class ComprehensiveRegexTester:
    """全面的正则系统测试器"""
    
    def __init__(self):
        self.test_results = {}
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        
    def print_header(self, title: str, level: int = 1):
        """打印测试标题"""
        if level == 1:
            print(f"\n{BLUE}{BOLD}{'='*60}{RESET}")
            print(f"{BLUE}{BOLD}{title.center(60)}{RESET}")
            print(f"{BLUE}{BOLD}{'='*60}{RESET}")
        else:
            print(f"\n{CYAN}--- {title} ---{RESET}")
    
    def print_result(self, test_name: str, passed: bool, message: str = ""):
        """打印测试结果"""
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
            print(f"{GREEN}✓ {test_name}{RESET}")
            if message:
                print(f"  {message}")
        else:
            self.failed_tests += 1
            print(f"{RED}✗ {test_name}{RESET}")
            if message:
                print(f"  {RED}{message}{RESET}")
    
    def print_test_case(self, title: str, original: str, result: str):
        """打印测试用例对比"""
        print(f"\n{title}:")
        print(f"  原始: {original}")
        print(f"  结果: {result}")
        if original != result:
            print(f"  {GREEN}替换成功，内容已更改{RESET}")
            return True
        else:
            print(f"  {YELLOW}内容未更改{RESET}")
            return False
    
    def test_tavern_conversion(self):
        """测试酒馆正则转换功能"""
        self.print_header("测试酒馆正则转换功能", 1)
        
        # 测试placement映射
        self.print_header("测试placement映射", 2)
        test_cases = [
            ([1], ["user"], "用户消息"),
            ([2], ["assistant_response"], "AI回复"),
            ([5], ["world_book"], "世界书"),
            ([6], ["assistant_thinking"], "AI思考"),
            ([1, 2], ["user", "assistant_response"], "用户和AI回复"),
            ([99], [], "无效placement"),
            ([], ["user", "assistant_response", "world_book", "preset", "assistant_thinking"], "空placement")
        ]
        
        for placement_list, expected, description in test_cases:
            result = map_placement_to_targets(placement_list)
            # 对于空结果的特殊处理
            if not expected:
                expected = ["user", "assistant_response", "world_book", "preset", "assistant_thinking"]
            
            passed = result == expected
            self.print_result(f"映射{description}: {placement_list} -> {result}", passed)
        
        # 测试完整的酒馆正则转换
        self.print_header("测试完整的酒馆正则转换", 2)
        tavern_regex_examples = [
            {
                "id": "test_1",
                "scriptName": "测试规则1",
                "findRegex": r"测试",
                "replaceString": "[测试]",
                "placement": [1, 2],
                "disabled": False,
                "minDepth": 1,
                "maxDepth": 5,
                "promptOnly": True
            },
            {
                "scriptName": "无ID规则",
                "findRegex": r"无ID",
                "replaceString": "[无ID]",
                "placement": [5],
                "disabled": True,
                "markdownOnly": True
            }
        ]
        
        for i, tavern_regex in enumerate(tavern_regex_examples):
            odysseia_regex = convert_tavern_regex(tavern_regex)
            
            # 验证必要字段
            required_fields = ["id", "name", "enabled", "find_regex", "replace_regex", "targets", "placement", "views"]
            all_fields_present = all(field in odysseia_regex for field in required_fields)
            self.print_result(f"转换示例{i+1}: 包含所有必要字段", all_fields_present)
            
            # 验证具体转换
            if tavern_regex.get("disabled", False):
                expected_enabled = False
            else:
                expected_enabled = True
            actual_enabled = odysseia_regex.get("enabled", True)
            self.print_result(f"转换示例{i+1}: enabled字段正确 ({expected_enabled})", actual_enabled == expected_enabled)
            
            # 验证depth范围转换
            if "minDepth" in tavern_regex:
                has_min_depth = "min_depth" in odysseia_regex
                self.print_result(f"转换示例{i+1}: min_depth字段转换", has_min_depth)
            if "maxDepth" in tavern_regex:
                has_max_depth = "max_depth" in odysseia_regex
                self.print_result(f"转换示例{i+1}: max_depth字段转换", has_max_depth)
    
    def test_regex_rule_data_model(self):
        """测试RegexRule数据模型"""
        self.print_header("测试RegexRule数据模型", 1)
        
        # 测试基本创建
        try:
            rule = RegexRule(
                id="test_rule",
                name="测试规则",
                find_regex=r"test(\d+)",
                replace_regex=r"TEST_$1",
                targets=["user", "assistant_response"],
                placement="after_macro",
                views=["original", "user_view"],
                min_depth=1,
                max_depth=10,
                min_order=50,
                max_order=150
            )
            self.print_result("RegexRule基本创建", True)
            
            # 验证默认值
            default_rule = RegexRule(id="default", name="默认", find_regex="test", replace_regex="TEST")
            expected_defaults = {
                "enabled": True,
                "targets": ["user", "assistant_response", "world_book", "preset", "assistant_thinking"],
                "placement": "after_macro",
                "views": ["original"],
                "min_depth": None,
                "max_depth": None
            }
            
            defaults_correct = all(
                getattr(default_rule, field) == expected_value 
                for field, expected_value in expected_defaults.items()
            )
            self.print_result("RegexRule默认值正确", defaults_correct)
            
        except Exception as e:
            self.print_result("RegexRule创建", False, str(e))
    
    def test_regex_rule_manager_basic(self):
        """测试RegexRuleManager基本功能"""
        self.print_header("测试RegexRuleManager基本功能", 1)
        
        # 创建临时规则管理器
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = RegexRuleManager(rules_directory=temp_dir)
            
            # 测试添加规则
            test_rule = RegexRule(
                id="manager_test",
                name="管理器测试",
                find_regex=r"manager",
                replace_regex="MANAGER",
                views=["original"]
            )
            
            add_success = manager.add_rule(test_rule)
            self.print_result("添加规则", add_success)
            
            # 测试获取规则
            retrieved_rule = manager.get_rule("manager_test")
            get_success = retrieved_rule is not None and retrieved_rule.id == "manager_test"
            self.print_result("获取规则", get_success)
            
            # 测试启用/禁用规则
            disable_success = manager.enable_rule("manager_test", False)
            enable_success = manager.enable_rule("manager_test", True)
            self.print_result("启用/禁用规则", disable_success and enable_success)
            
            # 测试移除规则
            remove_success = manager.remove_rule("manager_test")
            self.print_result("移除规则", remove_success)
            
            # 验证规则已移除
            removed_rule = manager.get_rule("manager_test")
            removal_verified = removed_rule is None
            self.print_result("验证规则已移除", removal_verified)
    
    def test_regex_application(self):
        """测试正则应用功能"""
        self.print_header("测试正则应用功能", 1)
        
        # 创建规则管理器
        manager = RegexRuleManager(rules_directory="")
        manager.clear()
        
        # 添加测试规则
        rules = [
            RegexRule(
                id="original_rule",
                name="原始视图规则",
                find_regex=r"原始",
                replace_regex="[原始]",
                placement="after_macro",
                views=["original"]
            ),
            RegexRule(
                id="user_view_rule", 
                name="用户视图规则",
                find_regex=r"用户",
                replace_regex="[用户]",
                placement="after_macro", 
                views=["user_view"]
            ),
            RegexRule(
                id="assistant_view_rule",
                name="AI视图规则",
                find_regex=r"AI",
                replace_regex="[AI]",
                placement="after_macro",
                views=["assistant_view"]
            ),
            RegexRule(
                id="depth_rule",
                name="深度限制规则",
                find_regex=r"深度",
                replace_regex="[深度限制]",
                placement="after_macro",
                views=["original"],
                min_depth=2,
                max_depth=5
            )
        ]
        
        for rule in rules:
            manager.add_rule(rule)
        
        # 测试不同视图的应用
        test_content = "这是一个包含原始、用户、AI和深度的测试内容"
        
        # 测试原始视图
        original_result = manager.apply_regex_to_content(
            content=test_content,
            source_type="preset", 
            placement="after_macro",
            view="original"
        )
        original_changed = self.print_test_case("原始视图应用", test_content, original_result)
        self.print_result("原始视图规则应用", "[原始]" in original_result)
        
        # 测试用户视图  
        user_result = manager.apply_regex_to_content(
            content=test_content,
            source_type="preset",
            placement="after_macro", 
            view="user_view"
        )
        user_changed = self.print_test_case("用户视图应用", test_content, user_result)
        self.print_result("用户视图规则应用", "[用户]" in user_result)
        
        # 测试AI视图
        assistant_result = manager.apply_regex_to_content(
            content=test_content,
            source_type="preset",
            placement="after_macro",
            view="assistant_view"
        )
        assistant_changed = self.print_test_case("AI视图应用", test_content, assistant_result)
        self.print_result("AI视图规则应用", "[AI]" in assistant_result)
        
        # 测试深度限制 
        # 深度在范围内
        depth_in_range = manager.apply_regex_to_content(
            content=test_content,
            source_type="preset",
            depth=3,
            placement="after_macro",
            view="original"
        )
        depth_applied = self.print_test_case("深度在范围内(depth=3)", test_content, depth_in_range)
        self.print_result("深度范围内规则应用", "[深度限制]" in depth_in_range)
        
        # 深度超出范围
        depth_out_range = manager.apply_regex_to_content(
            content=test_content,
            source_type="preset", 
            depth=10,
            placement="after_macro",
            view="original"
        )
        depth_not_applied = self.print_test_case("深度超出范围(depth=10)", test_content, depth_out_range)
        self.print_result("深度超出范围规则不应用", "[深度限制]" not in depth_out_range)
    
    def test_placement_types(self):
        """测试不同的placement类型"""
        self.print_header("测试不同的placement类型", 1)
        
        manager = RegexRuleManager(rules_directory="")
        manager.clear()
        
        # 添加不同placement类型的规则
        placement_rules = [
            RegexRule(
                id="before_skip",
                name="宏处理前跳过",
                find_regex=r"宏前跳过",
                replace_regex="[宏前跳过]",
                placement="before_macro_skip",
                views=["original"]
            ),
            RegexRule(
                id="before_include", 
                name="宏处理前包含",
                find_regex=r"\{\{test\}\}",
                replace_regex="【TEST宏】",
                placement="before_macro_include",
                views=["original"]
            ),
            RegexRule(
                id="after_macro",
                name="宏处理后",
                find_regex=r"宏后",
                replace_regex="[宏后]",
                placement="after_macro",
                views=["original"]
            )
        ]
        
        for rule in placement_rules:
            manager.add_rule(rule)
        
        test_content = "这是宏前跳过和{{test}}宏以及宏后的测试"
        
        # 测试before_macro_skip
        before_skip_result = manager.apply_regex_to_content(
            content=test_content,
            source_type="preset",
            placement="before_macro_skip",
            view="original"
        )
        self.print_test_case("before_macro_skip", test_content, before_skip_result)
        
        # 测试before_macro_include
        before_include_result = manager.apply_regex_to_content(
            content=test_content,
            source_type="preset",
            placement="before_macro_include", 
            view="original"
        )
        self.print_test_case("before_macro_include", test_content, before_include_result)
        
        # 测试after_macro
        after_result = manager.apply_regex_to_content(
            content=test_content,
            source_type="preset",
            placement="after_macro",
            view="original"
        )
        self.print_test_case("after_macro", test_content, after_result)
    
    def test_edge_cases(self):
        """测试边界条件和错误处理"""
        self.print_header("测试边界条件和错误处理", 1)
        
        manager = RegexRuleManager(rules_directory="")
        manager.clear()
        
        # 测试空内容
        empty_result = manager.apply_regex_to_content("", "preset", placement="after_macro", view="original")
        self.print_result("空内容处理", empty_result == "")
        
        # 测试None内容
        none_result = manager.apply_regex_to_content(None, "preset", placement="after_macro", view="original")  
        self.print_result("None内容处理", none_result is None)
        
        # 测试无效正则表达式
        try:
            invalid_rule = RegexRule(
                id="invalid_regex",
                name="无效正则",
                find_regex=r"[unclosed",  # 无效的正则表达式
                replace_regex="replaced"
            )
            add_result = manager.add_rule(invalid_rule)
            self.print_result("无效正则表达式处理", not add_result)  # 应该添加失败
        except Exception as e:
            self.print_result("无效正则表达式异常处理", True)
        
        # 测试重复ID
        rule1 = RegexRule(id="duplicate", name="第一个", find_regex="test1", replace_regex="TEST1")
        rule2 = RegexRule(id="duplicate", name="第二个", find_regex="test2", replace_regex="TEST2") 
        
        add1 = manager.add_rule(rule1)
        add2 = manager.add_rule(rule2)
        self.print_result("重复ID处理", add1 and not add2)
    
    def test_integration_with_converted_tavern_regex(self):
        """测试与转换后的酒馆正则的集成"""
        self.print_header("测试与转换后的酒馆正则的集成", 1)
        
        # 读取转换后的酒馆正则文件
        try:
            with open("data/regex_rules/final_输入tag.json", "r", encoding="utf-8") as f:
                converted_rules_data = json.load(f)
            
            manager = RegexRuleManager(rules_directory="")
            manager.clear()
            
            # 加载转换后的规则
            for rule_data in converted_rules_data:
                rule = RegexRule(**rule_data)
                manager.add_rule(rule)
            
            # 测试转换后规则的应用
            test_input = "这是一个测试输入内容"
            # 由于转换后的规则target是["user"]，需要使用能映射到user的source_type
            # 根据RegexRuleManager中的映射逻辑，需要直接传入匹配的target名称作为source_type
            result = manager.apply_regex_to_content(
                content=test_input,
                source_type="user",  # 直接使用user，因为规则的target是["user"]
                placement="after_macro",
                view="original",
                depth=1  # 在max_depth=1范围内
            )
            
            expected_output = "<input>\n这是一个测试输入内容\n</input>"
            integration_success = result == expected_output
            
            self.print_test_case("转换后酒馆正则应用", test_input, result)
            self.print_result("酒馆正则集成测试", integration_success)
            
        except Exception as e:
            self.print_result("酒馆正则集成测试", False, str(e))
    
    def run_all_tests(self):
        """运行所有测试"""
        self.print_header("正则脚本系统全面测试", 1)
        print(f"{CYAN}测试开始时间: {__import__('datetime').datetime.now()}{RESET}")
        
        try:
            self.test_tavern_conversion()
            self.test_regex_rule_data_model()
            self.test_regex_rule_manager_basic()
            self.test_regex_application()
            self.test_placement_types()
            self.test_edge_cases()
            self.test_integration_with_converted_tavern_regex()
            
        except Exception as e:
            self.print_result("测试执行", False, f"测试过程中发生意外错误: {e}")
            import traceback
            traceback.print_exc()
        
        # 打印测试总结
        self.print_header("测试总结", 1)
        pass_rate = (self.passed_tests / self.total_tests * 100) if self.total_tests > 0 else 0
        
        print(f"{BOLD}总测试数: {self.total_tests}{RESET}")
        print(f"{GREEN}通过: {self.passed_tests}{RESET}")
        print(f"{RED}失败: {self.failed_tests}{RESET}")
        print(f"{CYAN}通过率: {pass_rate:.1f}%{RESET}")
        
        if self.failed_tests == 0:
            print(f"\n{GREEN}{BOLD}🎉 所有测试通过！正则脚本系统功能完全正常。{RESET}")
        else:
            print(f"\n{YELLOW}{BOLD}⚠️  有 {self.failed_tests} 个测试未通过，请检查上述错误信息。{RESET}")
        
        return self.failed_tests == 0


if __name__ == "__main__":
    tester = ComprehensiveRegexTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
