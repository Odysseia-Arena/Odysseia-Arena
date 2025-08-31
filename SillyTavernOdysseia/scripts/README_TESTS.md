# 测试脚本说明

## 🧪 正则脚本测试

### comprehensive_regex_test.py
**最全面的正则系统测试脚本** ✅

- **测试覆盖**: 30个测试用例，100%通过率
- **功能范围**: 
  - 酒馆正则转换验证
  - RegexRule数据模型测试  
  - RegexRuleManager基础功能测试
  - 正则应用功能测试
  - 不同placement类型测试
  - 多视图支持测试
  - 深度和次序范围控制测试
  - 边界条件和错误处理测试
  - 酒馆正则集成测试

- **使用方法**:
  ```bash
  python scripts/comprehensive_regex_test.py
  ```

- **输出特点**:
  - 彩色输出，易于阅读
  - 详细的测试结果对比
  - 完整的错误信息
  - 测试总结统计

## 📁 已清理的文件

以下测试脚本已被删除，因为功能重复或过时：

- ~~`test_regex_views.py`~~ - 功能已被comprehensive_regex_test.py完全覆盖
- ~~`test_regex_rules.py`~~ - 使用了过时的API，功能重复

## 📋 保留的转换结果

- `final_输入tag.json` - 酒馆正则转换的最终正确版本
- `example_rules.json` - 正则规则示例文件
- `test_views.json` - 用于视图功能测试的规则文件

已删除的中间版本：
- ~~`converted_输入tag.json`~~ - 第一次转换版本（字段映射错误）
- ~~`corrected_输入tag.json`~~ - 第二次转换版本（正则格式问题）

## 🎯 推荐使用

建议使用 `comprehensive_regex_test.py` 作为标准测试脚本，它提供了最全面的功能验证和最好的用户体验。
