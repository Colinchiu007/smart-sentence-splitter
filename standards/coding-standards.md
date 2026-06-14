# Codeing Standards for PROJECT-012

## 命名规范
- **Python**: 模块/包名小写+下划线, 类名大驼峰, 函数/变量小写+下划线
- **测试**: `test_<模块名>.py`, 测试函数 `test_<行为>_当_<条件>_则_<结果>`

## 代码结构
- 一个文件只做一件事, 超 200 行考虑拆分
- 目录按功能分组 (Feature-First): `languages/zh/` 而非 `tokenizers/`
- 禁止跨层级导入

## 函数规范
- 函数 ≤ 30 行, 参数 ≤ 3 个
- 单一职责, 不嵌套超 3 层

## 错误处理
- 禁止 `except: pass`, 必须指定异常类型
- 外部调用必须有 try-catch
- 异常消息要有上下文

## 新增 Postprocessor 流程
1. 继承 `BasePostprocessor`
2. 实现 `adjust(result)` 和 `is_available()`
3. 注册到 `SmartSentenceSplitter._init_postprocessors()`

## 新增 Tier 流程
1. 继承 `BaseSentenceSplitter`
2. 实现 `split()` + `is_available()`
3. 设置 language + tier 属性
4. 注册到 `_zh_chain` / `_en_chain`
