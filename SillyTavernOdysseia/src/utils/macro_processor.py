import json
import re
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Generator, Tuple
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Python < 3.9 兼容性
    from datetime import timezone as ZoneInfo

class MacroError(ValueError):
    """自定义宏处理异常，用于报告语法错误或运行时错误。"""
    pass

class MacroProcessor:
    """
    宏处理器类，负责解析和替换 JSON 文本中的宏。
    """
    # 掷骰子公式的正则表达式 (例如: 1d6 或 d6)
    ROLL_REGEX = re.compile(r"^(\d*)d(\d+)$", re.IGNORECASE)
    
    # 掷骰子限制
    MAX_DICE = 100
    MAX_SIDES = 1000

    def __init__(self, context: Dict[str, Any]):
        """
        初始化宏处理器。
        :param context: 包含系统级宏所需的上下文信息。
        """
        self.context = context
        # 存储局部变量 (setvar/getvar)。
        self._variables: Dict[str, str] = {}
        # 存储全局变量 (setglobalvar/getglobalvar)。
        self._global_variables: Dict[str, str] = {}
        # 存储持久化选择 (pick)。用于在一次聊天中保持选择结果不变
        self._pick_cache: Dict[str, str] = {}

    def process_json(self, json_string: str) -> str:
        """
        处理输入的 JSON 字符串，替换其中的宏，同时保持 JSON 结构完整。
        """
        # 每次处理开始时重置局部变量状态，但保持全局变量和持久化选择
        self._variables = {}
        # 注意：_global_variables 和 _pick_cache 在整个会话中保持持久

        try:
            # 1. 解析 JSON
            data = json.loads(json_string)
        except json.JSONDecodeError as e:
            raise MacroError(f"输入的 JSON 格式无效: {e}")

        # 2. 遍历并处理 JSON 数据结构
        # 依赖于现代 Python 字典（3.7+）保持顺序的特性来实现跨结构的从左到右执行
        processed_data = self._traverse_and_process(data)

        # 3. 返回处理后的 JSON 字符串
        return json.dumps(processed_data, ensure_ascii=False)

    def _traverse_and_process(self, data: Any) -> Any:
        """
        递归遍历 JSON 数据结构，对字符串类型的值应用宏替换。
        保证从左到右的顺序（键先于值）。
        """
        if isinstance(data, dict):
            processed_dict = {}
            for k, v in data.items():
                # 1. 先处理键 (Key)
                processed_k = self._traverse_and_process(k)
                
                # 检查处理后的键是否可哈希
                try:
                    hash(processed_k)
                except TypeError:
                   # 防御性编程, 宏替换后必须是可hash类型
                   raise MacroError(f"宏替换后，JSON 键 '{k}' 变为不可哈希的类型: {type(processed_k).__name__}。")

                # 2. 再处理值 (Value)
                processed_v = self._traverse_and_process(v)
                
                # 如果两个键替换后相同，后者覆盖前者，符合 LTR 原则
                processed_dict[processed_k] = processed_v
            return processed_dict
            
        elif isinstance(data, list):
            return [self._traverse_and_process(i) for i in data]
        elif isinstance(data, str):
            return self._process_string(data)
        else:
            # 其他类型（数字、布尔值等）保持不变
            return data

    def _find_macros(self, text: str) -> Generator[Tuple[int, int, str], None, None]:
        """
        自定义宏解析器。
        查找文本中所有最外层的宏，正确处理嵌套深度。
        按顺序生成 (start_index, end_index, macro_content)。
        """
        i = 0
        n = len(text)
        while i < n:
            # 查找潜在宏的开始位置 {{
            start = text.find("{{", i)
            if start == -1:
                break

            # 查找对应的结束位置 }}，同时处理嵌套
            depth = 1
            # j 是搜索光标，从 {{ 之后开始
            j = start + 2
            content_start = j
            
            while j < n:
                # 使用切片检查 {{ 或 }}
                if text[j:j+2] == "{{":
                    depth += 1
                    j += 2
                elif text[j:j+2] == "}}":
                    depth -= 1
                    if depth == 0:
                        # 找到了最外层的结束位置 }}
                        content_end = j
                        end = j + 2
                        yield (start, end, text[content_start:content_end])
                        i = end
                        break # 退出内部循环，继续外部循环查找下一个宏
                    j += 2
                else:
                    # 普通字符
                    j += 1
            else:
                # 内部循环结束（到达字符串末尾）但 depth 不为 0 (宏未关闭)
                # 忽略不完整的双括号。我们停止在此字符串中继续查找宏，保留剩余部分原样。
                break # 退出外部循环

    def _process_string(self, text: str) -> str:
        """
        在字符串中执行宏替换。实现从左到右处理，且非递归。
        """
        result = []
        last_index = 0
        # 使用自定义解析器 _find_macros
        for start, end, macro_content in self._find_macros(text):
            
            # 添加当前宏之前的文本
            result.append(text[last_index:start])
            
            # 宏内容去除首尾空白
            stripped_content = macro_content.strip()

            # 如果宏内容为空 ({{}} 或 {{ }}), 视为普通文本
            if not stripped_content:
                result.append(text[start:end])
                last_index = end
                continue

            try:
                # 评估并处理宏。这一步可能会修改 self._variables (例如 setvar)
                replacement = self._evaluate_macro(stripped_content)
                
                # 处理trim宏的特殊逻辑
                if replacement == "{{__TRIM_MARKER__}}":
                    # trim宏：移除此位置前后的换行符
                    # 移除前面的换行符
                    if result and result[-1].endswith('\n'):
                        result[-1] = result[-1].rstrip('\n')
                    
                    # 查找后面的换行符并移除
                    remaining_text = text[end:]
                    stripped_remaining = remaining_text.lstrip('\n')
                    newlines_removed = len(remaining_text) - len(stripped_remaining)
                    
                    if newlines_removed > 0:
                        # 更新last_index以跳过被移除的换行符
                        last_index = end + newlines_removed
                    else:
                        last_index = end
                    
                    # trim宏本身不产生任何输出
                    replacement = ""
                # 处理操作性宏（返回空字符串的宏）的智能换行符清理
                elif replacement == "" and self._is_operation_macro(stripped_content):
                    # 检查是否应该清理周围的换行符
                    should_trim = self._should_trim_around_operation_macro(text, start, end, result)
                    
                    if should_trim:
                        # 类似trim宏的处理
                        if result and result[-1].endswith('\n'):
                            result[-1] = result[-1].rstrip('\n')
                        
                        remaining_text = text[end:]
                        stripped_remaining = remaining_text.lstrip('\n')
                        newlines_removed = len(remaining_text) - len(stripped_remaining)
                        
                        if newlines_removed > 0:
                            last_index = end + newlines_removed
                        else:
                            last_index = end
                    else:
                        last_index = end
                else:
                    last_index = end
                
                # 将替换结果拼接到输出字符串中。替换后的文本不会再次被扫描 (禁止递归)
                result.append(str(replacement))
            except MacroError as e:
                # 捕获宏处理过程中的错误，抛出异常并停止整个流程
                # 使用原始的宏文本（包含可能的嵌套结构）进行报错
                macro_display = text[start:end]
                raise MacroError(f"处理宏 '{macro_display}' 时出错: {e}")
                
            # 注意：last_index 在trim宏处理中已经更新，其他情况在else分支中更新

        # 添加最后一个宏之后的剩余文本（或者在 _find_macros 因不完整括号停止后的文本）
        result.append(text[last_index:])
        return "".join(result)

    def _is_operation_macro(self, content: str) -> bool:
        """判断是否为操作性宏（执行操作但返回空字符串的宏）"""
        # 操作性宏列表：这些宏执行操作但不应该留下视觉内容
        operation_macros = [
            "setvar::", "setglobalvar::", "addvar::", "addglobalvar::",
            "incvar::", "incglobalvar::", "decvar::", "decglobalvar::",
            "noop", "//"
        ]
        
        # 检查是否为操作性宏
        for macro_prefix in operation_macros:
            if content.startswith(macro_prefix):
                return True
            if content == "noop":
                return True
            if content.startswith("//"):  # 注释宏
                return True
        
        return False
    
    def _should_trim_around_operation_macro(self, text: str, start: int, end: int, result: list) -> bool:
        """判断是否应该清理操作性宏周围的换行符"""
        # 检查宏前面是否有换行符
        has_newline_before = result and result[-1].endswith('\n')
        
        # 检查宏后面是否有换行符
        remaining_text = text[end:]
        has_newline_after = remaining_text.startswith('\n')
        
        # 如果宏独占一行（前后都有换行符），则应该清理
        if has_newline_before and has_newline_after:
            return True
        
        # 如果宏前面是换行符，后面是空白内容，也应该清理
        if has_newline_before and remaining_text.strip() == "":
            return True
        
        # 如果宏在行首且后面是换行符，也应该清理
        line_start = text.rfind('\n', 0, start) + 1  # 找到当前行的开始
        line_content_before_macro = text[line_start:start].strip()
        if not line_content_before_macro and has_newline_after:
            return True
        
        return False

    def _evaluate_macro(self, content: str) -> str:
        """
        评估单个宏内容并返回替换后的值。
        """
        # 1. 系统范围的简单替换宏
        if content == "user":
            return str(self.context.get("user", ""))
        elif content == "char":
            return str(self.context.get("char", ""))
        elif content == "lastUserMessage":
            return str(self.context.get("lastUserMessage", ""))
        elif content == "time":
            # 返回当前时间
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        elif content == "date":
            # 返回当前日期
            return datetime.now().strftime("%Y-%m-%d")
        elif content == "weekday":
            # 返回当前星期
            weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
            return weekdays[datetime.now().weekday()]
        elif content == "isodate":
            # 返回ISO日期格式
            return datetime.now().strftime("%Y-%m-%d")
        elif content == "isotime":
            # 返回ISO时间格式
            return datetime.now().strftime("%H:%M:%S")
        elif content == "newline":
            # 返回换行符
            return "\n"
        elif content == "trim":
            # trim宏：修剪此宏周围的换行符，在实际应用中由外层处理
            # 这里返回一个特殊标记，外层处理时会识别并处理
            return "{{__TRIM_MARKER__}}"
        elif content == "noop":
            # 空操作，返回空字符串
            return ""
        elif content.startswith("//"):
            # 注释宏，返回空字符串
            return ""
        elif content == "description":
            return str(self.context.get("description", ""))
        elif content == "personality":
            return str(self.context.get("personality", ""))
        elif content == "scenario":
            return str(self.context.get("scenario", ""))
        elif content == "lastMessage":
            return str(self.context.get("lastMessage", ""))
        elif content == "lastCharMessage":
            return str(self.context.get("lastCharMessage", ""))
        elif content == "messageCount":
            return str(self.context.get("messageCount", "0"))
        elif content == "userMessageCount":
            return str(self.context.get("userMessageCount", "0"))
        elif content == "conversationLength":
            return str(self.context.get("conversationLength", "0"))

        # 2. 优先处理使用 :: 分隔符的宏 (变量操作和替代语法 random)
        if content.startswith("getvar::"):
            return self._handle_getvar(content)
        elif content.startswith("setvar::"):
            return self._handle_setvar(content)
        elif content.startswith("random::"):
             # 对于 random::，我们将 'random' 之后的部分 (例如 "::arg1::arg2") 传递给统一的 handler
             return self._handle_random(content[len("random"):])
        elif content.startswith("addvar::"):
            return self._handle_addvar(content)
        elif content.startswith("incvar::"):
            return self._handle_incvar(content)
        elif content.startswith("decvar::"):
            return self._handle_decvar(content)
        elif content.startswith("addglobalvar::"):
            return self._handle_addglobalvar(content)
        elif content.startswith("incglobalvar::"):
            return self._handle_incglobalvar(content)
        elif content.startswith("decglobalvar::"):
            return self._handle_decglobalvar(content)
        elif content.startswith("getglobalvar::"):
            return self._handle_getglobalvar(content)
        elif content.startswith("setglobalvar::"):
            return self._handle_setglobalvar(content)

        # 3. 处理使用 : 分隔符的功能性宏
        parts = content.split(':', 1)
        command = parts[0]

        if command == "roll":
            if len(parts) < 2 or not parts[1].strip():
                raise MacroError("roll 宏缺少公式参数。应为 {{roll:1d6}}。")
            return self._handle_roll(parts[1].strip())
        elif command == "random":
            if len(parts) < 2:
                 raise MacroError("random 宏缺少列表参数。应为 {{random:1,2,3}}。")
            # 将参数部分 (例如 "arg1,arg2") 传递给统一的 handler
            return self._handle_random(parts[1])
        elif command == "pick":
            if len(parts) < 2:
                raise MacroError("pick 宏缺少列表参数。应为 {{pick:1,2,3}}。")
            # 处理持久化选择
            return self._handle_pick(parts[1])
        elif command == "upper":
            if len(parts) < 2:
                raise MacroError("upper 宏缺少文本参数。应为 {{upper:text}}。")
            return parts[1].upper()
        elif command == "lower":
            if len(parts) < 2:
                raise MacroError("lower 宏缺少文本参数。应为 {{lower:text}}。")
            return parts[1].lower()
        elif command == "length":
            if len(parts) < 2:
                raise MacroError("length 宏缺少文本参数。应为 {{length:text}}。")
            return str(len(parts[1]))
        elif command == "reverse":
            if len(parts) < 2:
                raise MacroError("reverse 宏缺少文本参数。应为 {{reverse:text}}。")
            return parts[1][::-1]
        elif command == "add":
            return self._handle_math(parts, lambda a, b: a + b, "add")
        elif command == "sub":
            return self._handle_math(parts, lambda a, b: a - b, "sub")
        elif command == "mul":
            return self._handle_math(parts, lambda a, b: a * b, "mul")
        elif command == "div":
            return self._handle_math(parts, lambda a, b: a / b if b != 0 else 0, "div")
        elif command == "max":
            return self._handle_math(parts, max, "max")
        elif command == "min":
            return self._handle_math(parts, min, "min")
        elif command == "datetimeformat":
            if len(parts) < 2:
                raise MacroError("datetimeformat 宏缺少格式参数。应为 {{datetimeformat:DD.MM.YYYY HH:mm}}。")
            return self._handle_datetimeformat(parts[1])
        elif command.startswith("time_UTC"):
            # 处理 time_UTC±# 格式
            return self._handle_time_utc(command)
        elif command == "timeDiff":
            if len(parts) < 2:
                raise MacroError("timeDiff 宏缺少时间参数。应为 {{timeDiff::(time1)::(time2)}}。")
            return self._handle_time_diff(parts[1])

        # 检查是否是Python宏格式，如果是则跳过处理
        if content.startswith("python:"):
            return "{{" + content + "}}"  # 返回原始格式，交给Python宏处理器处理
        # 未知宏（要求5：视为语法错误）
        raise MacroError(f"未知的宏命令或无效的语法。")

    def _handle_roll(self, formula: str) -> str:
        """
        处理掷骰子宏 {{roll:(formula)}}。
        """
        match = self.ROLL_REGEX.match(formula)
        if not match:
            raise MacroError(f"无效的掷骰公式: '{formula}'。期望格式如 '1d6' 或 'd6'。")

        try:
            # group(1) 是骰子数量，如果为空字符串 (例如 'd6')，则默认为 1
            num_dice_str = match.group(1)
            num_dice = int(num_dice_str) if num_dice_str else 1
            # group(2) 是骰子面数
            num_sides = int(match.group(2))
        except ValueError:
             raise MacroError(f"掷骰公式中的数字无效: '{formula}'。")

        if num_dice <= 0 or num_sides <= 0:
            raise MacroError("骰子数量和面数必须为正整数。")

        # 添加限制检查
        if num_dice > self.MAX_DICE:
            raise MacroError(f"骰子数量 ({num_dice}) 超过最大限制 ({self.MAX_DICE})。")
        if num_sides > self.MAX_SIDES:
            raise MacroError(f"骰子面数 ({num_sides}) 超过最大限制 ({self.MAX_SIDES})。")

        # 计算总点数
        total = sum(random.randint(1, num_sides) for _ in range(num_dice))
        return str(total)

    # _handle_random, _handle_getvar, _handle_setvar 的实现逻辑正确，无需修改
    def _handle_random(self, args_string: str) -> str:
        """
        统一处理随机选择宏。支持两种语法。
        {{random:(args)}} 和 {{random::(arg1)::(arg2)}}
        """
        if args_string.startswith(":"):
             # 处理 {{random::...}} 语法 (传入的字符串形如 "::arg1::arg2")
             # 移除开头的两个冒号
             args_string = args_string[2:]
             # 使用 :: 分隔参数
             args = args_string.split("::")
        else:
            # 处理 {{random:...}} 语法 (传入的字符串形如 "arg1,arg2")
            # 使用逗号分隔参数
            args = args_string.split(",")

        # 过滤掉空字符串参数，防止选择空结果
        valid_args = [arg for arg in args if arg]

        if not valid_args:
            # 如果过滤后列表为空（例如 {{random:}} 或 {{random::}}），则报错
            raise MacroError("random 宏的有效参数列表为空。")

        return random.choice(valid_args)

    def _handle_getvar(self, content: str) -> str:
        """
        处理 getvar 宏 {{getvar::name}}。
        """
        # 移除 'getvar::' 前缀
        name = content[len("getvar::"):]

        if not name:
             raise MacroError("getvar 宏的变量名不能为空。")

        # 强制要求变量必须先设置才能获取 (要求4和5)
        if name not in self._variables:
            raise MacroError(f"变量 '{name}' 不存在。请确保先使用 setvar 设置后再访问。")

        return self._variables[name]

    def _handle_setvar(self, content: str) -> str:
        """
        处理 setvar 宏 {{setvar::name::value}}。
        """
        # 移除 'setvar::' 前缀
        remaining = content[len("setvar::"):]

        # 按 :: 分割，最多分割 1 次，以获取 name 和 value
        parts = remaining.split("::", 1)

        if len(parts) < 2:
             # 如果少于2部分，说明缺少 name 或 value
             raise MacroError("setvar 宏语法无效。期望格式 {{setvar::name::value}}。")

        name = parts[0]
        value = parts[1]

        if not name:
            raise MacroError("setvar 宏的变量名不能为空。")

        # 设置变量
        self._variables[name] = value
        # setvar 宏本身替换为空字符串
        return ""

    def _handle_addvar(self, content: str) -> str:
        """
        处理 addvar 宏 {{addvar::name::increment}}。
        """
        # 移除 'addvar::' 前缀
        remaining = content[len("addvar::"):]

        # 按 :: 分割，最多分割 1 次，以获取 name 和 increment
        parts = remaining.split("::", 1)

        if len(parts) < 2:
             raise MacroError("addvar 宏语法无效。期望格式 {{addvar::name::increment}}。")

        name = parts[0]
        increment_str = parts[1]

        if not name:
            raise MacroError("addvar 宏的变量名不能为空。")

        # 检查变量是否存在
        if name not in self._variables:
            raise MacroError(f"变量 '{name}' 不存在。请确保先使用 setvar 设置后再访问。")

        try:
            # 尝试将当前值和增量转换为数字（数值运算）
            current_value = float(self._variables[name])
            increment = float(increment_str)
            new_value = current_value + increment
            
            # 如果结果是整数，以整数形式存储
            if new_value.is_integer():
                new_value = int(new_value)
            
            self._variables[name] = str(new_value)
        except ValueError:
            # 数值转换失败，执行字符串拼接（兼容SillyTavern预设的常见误用）
            # 注意：官方addvar是数值运算，但很多预设误用它做字符串拼接
            current_str = str(self._variables[name])
            increment_str = str(increment_str)
            
            # 字符串拼接
            new_value = current_str + increment_str
            self._variables[name] = new_value
            
            # 可选：输出调试信息
            # print(f"[DEBUG] addvar字符串拼接: {name} = '{current_str}' + '{increment_str}' = '{new_value}'")

        # addvar 宏本身替换为空字符串
        return ""

    def _handle_incvar(self, content: str) -> str:
        """
        处理 incvar 宏 {{incvar::name}}。
        """
        # 移除 'incvar::' 前缀
        name = content[len("incvar::"):]

        if not name:
             raise MacroError("incvar 宏的变量名不能为空。")

        # 检查变量是否存在
        if name not in self._variables:
            raise MacroError(f"变量 '{name}' 不存在。请确保先使用 setvar 设置后再访问。")

        try:
            # 尝试将当前值转换为数字并加1
            current_value = float(self._variables[name])
            new_value = current_value + 1
            
            # 如果结果是整数，以整数形式存储
            if new_value.is_integer():
                new_value = int(new_value)
            
            self._variables[name] = str(new_value)
            return str(new_value)  # incvar 返回新值
        except ValueError:
            raise MacroError(f"incvar 宏中的数值无效。当前值: '{self._variables[name]}'。")

    def _handle_decvar(self, content: str) -> str:
        """
        处理 decvar 宏 {{decvar::name}}。
        """
        # 移除 'decvar::' 前缀
        name = content[len("decvar::"):]

        if not name:
             raise MacroError("decvar 宏的变量名不能为空。")

        # 检查变量是否存在
        if name not in self._variables:
            raise MacroError(f"变量 '{name}' 不存在。请确保先使用 setvar 设置后再访问。")

        try:
            # 尝试将当前值转换为数字并减1
            current_value = float(self._variables[name])
            new_value = current_value - 1
            
            # 如果结果是整数，以整数形式存储
            if new_value.is_integer():
                new_value = int(new_value)
            
            self._variables[name] = str(new_value)
            return str(new_value)  # decvar 返回新值
        except ValueError:
            raise MacroError(f"decvar 宏中的数值无效。当前值: '{self._variables[name]}'。")

    def _handle_math(self, parts: list, operation, command: str) -> str:
        """
        处理数学运算宏。
        """
        if len(parts) < 2:
            raise MacroError(f"{command} 宏缺少参数。应为 {{{{{command}:a:b}}}}。")
        
        args_string = parts[1]
        args = args_string.split(':')
        
        if len(args) < 2:
            raise MacroError(f"{command} 宏需要两个数值参数。")
        
        try:
            a = float(args[0])
            b = float(args[1])
            result = operation(a, b)
            
            # 如果结果是整数，以整数形式返回
            if isinstance(result, float) and result.is_integer():
                result = int(result)
            
            return str(result)
        except ValueError:
            raise MacroError(f"{command} 宏中的数值无效: '{args[0]}', '{args[1]}'。")
        except Exception as e:
            raise MacroError(f"{command} 宏计算错误: {e}。")

    def _handle_pick(self, args_string: str) -> str:
        """
        处理持久化选择宏。类似于random，但在一次会话中保持选择结果不变。
        """
        # 使用参数字符串作为缓存键，确保相同的选项列表得到相同的结果
        cache_key = args_string.strip()
        
        # 如果已经选择过，直接返回缓存的结果
        if cache_key in self._pick_cache:
            return self._pick_cache[cache_key]
        
        # 第一次选择，使用与random相同的逻辑
        if "::" in args_string:
            # 处理 {{pick::...}} 语法 (传入的字符串形如 ":arg1::arg2")
            # 使用 :: 分隔参数
            args = args_string.split("::")
        else:
            # 处理 {{pick:...}} 语法 (传入的字符串形如 "arg1,arg2")
            # 使用逗号分隔参数
            args = args_string.split(",")
        
        # 过滤掉空字符串参数
        valid_args = [arg.strip() for arg in args if arg.strip()]
        
        if not valid_args:
            raise MacroError("pick 宏的有效参数列表为空。")
        
        # 进行选择并缓存结果
        chosen_result = random.choice(valid_args)
        self._pick_cache[cache_key] = chosen_result
        
        return chosen_result

    def _handle_addglobalvar(self, content: str) -> str:
        """
        处理 addglobalvar 宏 {{addglobalvar::name::increment}}。
        """
        # 移除 'addglobalvar::' 前缀
        remaining = content[len("addglobalvar::"):]
        
        # 按 :: 分割，最多分割 1 次，以获取 name 和 increment
        parts = remaining.split("::", 1)
        
        if len(parts) < 2:
            raise MacroError("addglobalvar 宏语法无效。期望格式 {{addglobalvar::name::increment}}。")
        
        name = parts[0]
        increment_str = parts[1]
        
        if not name:
            raise MacroError("addglobalvar 宏的变量名不能为空。")
        
        # 检查变量是否存在
        if name not in self._global_variables:
            raise MacroError(f"全局变量 '{name}' 不存在。请确保先使用 setglobalvar 设置后再访问。")
        
        try:
            # 尝试将当前值和增量转换为数字
            current_value = float(self._global_variables[name])
            increment = float(increment_str)
            new_value = current_value + increment
            
            # 如果结果是整数，以整数形式存储
            if new_value.is_integer():
                new_value = int(new_value)
            
            self._global_variables[name] = str(new_value)
        except ValueError:
            raise MacroError(f"addglobalvar 宏中的数值无效。当前值: '{self._global_variables[name]}', 增量: '{increment_str}'。")
        
        # addglobalvar 宏本身替换为空字符串
        return ""

    def _handle_incglobalvar(self, content: str) -> str:
        """
        处理 incglobalvar 宏 {{incglobalvar::name}}。
        """
        # 移除 'incglobalvar::' 前缀
        name = content[len("incglobalvar::"):]
        
        if not name:
            raise MacroError("incglobalvar 宏的变量名不能为空。")
        
        # 检查变量是否存在
        if name not in self._global_variables:
            raise MacroError(f"全局变量 '{name}' 不存在。请确保先使用 setglobalvar 设置后再访问。")
        
        try:
            # 尝试将当前值转换为数字并加1
            current_value = float(self._global_variables[name])
            new_value = current_value + 1
            
            # 如果结果是整数，以整数形式存储
            if new_value.is_integer():
                new_value = int(new_value)
            
            self._global_variables[name] = str(new_value)
            return str(new_value)  # incglobalvar 返回新值
        except ValueError:
            raise MacroError(f"incglobalvar 宏中的数值无效。当前值: '{self._global_variables[name]}'。")

    def _handle_decglobalvar(self, content: str) -> str:
        """
        处理 decglobalvar 宏 {{decglobalvar::name}}。
        """
        # 移除 'decglobalvar::' 前缀
        name = content[len("decglobalvar::"):]
        
        if not name:
            raise MacroError("decglobalvar 宏的变量名不能为空。")
        
        # 检查变量是否存在
        if name not in self._global_variables:
            raise MacroError(f"全局变量 '{name}' 不存在。请确保先使用 setglobalvar 设置后再访问。")
        
        try:
            # 尝试将当前值转换为数字并减1
            current_value = float(self._global_variables[name])
            new_value = current_value - 1
            
            # 如果结果是整数，以整数形式存储
            if new_value.is_integer():
                new_value = int(new_value)
            
            self._global_variables[name] = str(new_value)
            return str(new_value)  # decglobalvar 返回新值
        except ValueError:
            raise MacroError(f"decglobalvar 宏中的数值无效。当前值: '{self._global_variables[name]}'。")

    def _handle_datetimeformat(self, format_str: str) -> str:
        """
        处理 datetimeformat 宏 {{datetimeformat:DD.MM.YYYY HH:mm}}。
        """
        try:
            # 转换格式字符串从SillyTavern格式到Python strftime格式
            python_format = self._convert_datetime_format(format_str)
            return datetime.now().strftime(python_format)
        except Exception as e:
            raise MacroError(f"datetimeformat 宏格式错误: {e}")

    def _convert_datetime_format(self, format_str: str) -> str:
        """
        将SillyTavern的日期时间格式转换为Python strftime格式。
        """
        # SillyTavern到Python格式的映射
        format_mapping = {
            'YYYY': '%Y',  # 四位年份
            'YY': '%y',    # 两位年份
            'MM': '%m',    # 两位月份
            'DD': '%d',    # 两位日期
            'HH': '%H',    # 24小时制小时
            'hh': '%I',    # 12小时制小时
            'mm': '%M',    # 分钟
            'ss': '%S',    # 秒
            'SSS': '%f',   # 微秒（近似毫秒）
            'A': '%p',     # AM/PM
        }
        
        python_format = format_str
        for tavern_format, python_equivalent in format_mapping.items():
            python_format = python_format.replace(tavern_format, python_equivalent)
        
        return python_format

    def _handle_time_utc(self, command: str) -> str:
        """
        处理 time_UTC±# 宏，如 time_UTC+8, time_UTC-4。
        """
        try:
            # 提取时区偏移
            if 'UTC+' in command:
                offset_str = command.split('UTC+')[1]
                offset_hours = int(offset_str)
            elif 'UTC-' in command:
                offset_str = command.split('UTC-')[1]
                offset_hours = -int(offset_str)
            else:
                raise MacroError(f"无效的UTC时区格式: {command}")
            
            # 创建时区偏移
            tz_offset = timezone(timedelta(hours=offset_hours))
            
            # 获取指定时区的当前时间
            utc_time = datetime.now(timezone.utc)
            target_time = utc_time.astimezone(tz_offset)
            
            return target_time.strftime("%H:%M:%S")
            
        except ValueError:
            raise MacroError(f"time_UTC 宏的时区偏移无效: {command}")
        except Exception as e:
            raise MacroError(f"time_UTC 宏处理错误: {e}")

    def _handle_time_diff(self, args_string: str) -> str:
        """
        处理 timeDiff 宏 {{timeDiff::time1::time2}}。
        计算两个时间之间的差值。
        """
        try:
            # 分解参数，args_string的格式是 ":time1::time2"（注意只有一个冒号开头）
            if not args_string.startswith(":"):
                raise MacroError("timeDiff 宏需要使用 :: 分隔符。期望格式 {{timeDiff::time1::time2}}")
            
            # 移除开头的 :
            remaining = args_string[1:]
            parts = remaining.split("::", 1)
            
            if len(parts) < 2:
                raise MacroError("timeDiff 宏需要两个时间参数。")
            
            time1_str = parts[0].strip()
            time2_str = parts[1].strip()
            
            # 解析时间字符串
            time1 = self._parse_time_string(time1_str)
            time2 = self._parse_time_string(time2_str)
            
            # 计算时间差
            diff = abs((time2 - time1).total_seconds())
            
            # 格式化输出
            return self._format_time_difference(diff)
            
        except Exception as e:
            raise MacroError(f"timeDiff 宏处理错误: {e}")

    def _parse_time_string(self, time_str: str) -> datetime:
        """
        解析时间字符串，支持多种格式。
        """
        # 支持的时间格式
        time_formats = [
            "%Y-%m-%d %H:%M:%S",  # 2024-01-01 12:30:00
            "%Y/%m/%d %H:%M:%S",  # 2024/01/01 12:30:00
            "%Y-%m-%d",           # 2024-01-01
            "%Y/%m/%d",           # 2024/01/01
            "%H:%M:%S",           # 12:30:00
            "%H:%M",              # 12:30
        ]
        
        for fmt in time_formats:
            try:
                if '%Y' not in fmt:
                    # 只有时间，添加今天的日期
                    time_part = datetime.strptime(time_str, fmt).time()
                    return datetime.combine(datetime.now().date(), time_part)
                else:
                    return datetime.strptime(time_str, fmt)
            except ValueError:
                continue
        
        raise ValueError(f"无法解析时间格式: {time_str}")

    def _format_time_difference(self, total_seconds: float) -> str:
        """
        格式化时间差输出。
        """
        if total_seconds < 60:
            return f"{int(total_seconds)}秒"
        elif total_seconds < 3600:
            minutes = int(total_seconds // 60)
            seconds = int(total_seconds % 60)
            return f"{minutes}分{seconds}秒"
        elif total_seconds < 86400:
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            return f"{hours}小时{minutes}分"
        else:
            days = int(total_seconds // 86400)
            hours = int((total_seconds % 86400) // 3600)
            return f"{days}天{hours}小时"

    def _handle_getglobalvar(self, content: str) -> str:
        """
        处理 getglobalvar 宏 {{getglobalvar::name}}。
        """
        # 移除 'getglobalvar::' 前缀
        name = content[len("getglobalvar::"):]

        if not name:
             raise MacroError("getglobalvar 宏的变量名不能为空。")

        # 强制要求变量必须先设置才能获取
        if name not in self._global_variables:
            raise MacroError(f"全局变量 '{name}' 不存在。请确保先使用 setglobalvar 设置后再访问。")

        return self._global_variables[name]

    def _handle_setglobalvar(self, content: str) -> str:
        """
        处理 setglobalvar 宏 {{setglobalvar::name::value}}。
        """
        # 移除 'setglobalvar::' 前缀
        remaining = content[len("setglobalvar::"):]

        # 按 :: 分割，最多分割 1 次，以获取 name 和 value
        parts = remaining.split("::", 1)

        if len(parts) < 2:
             # 如果少于2部分，说明缺少 name 或 value
             raise MacroError("setglobalvar 宏语法无效。期望格式 {{setglobalvar::name::value}}。")

        name = parts[0]
        value = parts[1]

        if not name:
            raise MacroError("setglobalvar 宏的变量名不能为空。")

        # 设置全局变量
        self._global_variables[name] = value
        # setglobalvar 宏本身替换为空字符串
        return ""