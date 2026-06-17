"""LLM 分句 prompt 模板。"""

SPLIT_PROMPT_ZH = """你是一个文本分句专家。请将以下文本切分为语义完整的句子。

要求：
1. 按句末标点（。！？.!?;）切分
2. 保留引号/括号完整性
3. 不要修改原文（包括标点、空白）
4. 输出严格的 JSON 数组，每个元素是一个完整句子

示例 1：
输入: "今天天气真好。我们去公园。路上遇到了朋友。"
输出: ["今天天气真好。", "我们去公园。", "路上遇到了朋友。"]

示例 2：
输入: 'Dr. Smith said "Hello." Then he left.'
输出: ["Dr. Smith said \"Hello.\"", "Then he left."]

请处理以下文本（仅输出 JSON 数组，不要任何其他内容）：
{text}
"""


def build_split_prompt(text: str, language: str = "auto") -> str:
    """构造分句 prompt。

    Args:
        text: 待分句的文本
        language: zh / en / auto
    """
    if language == "en":
        # 英文版（更简短的指令）
        return f"""You are a sentence segmentation expert. Split the following text into semantically complete sentences.

Rules:
1. Split at sentence-ending punctuation (.!?;)
2. Preserve quotes and brackets
3. Do NOT modify the original text
4. Output a strict JSON array, each element is a complete sentence

Example:
Input: "Hello world. How are you? I'm fine."
Output: ["Hello world.", "How are you?", "I'm fine."]

Now process this text (output ONLY the JSON array, nothing else):
{text}
"""
    # 默认用中文 prompt
    return SPLIT_PROMPT_ZH.format(text=text)
