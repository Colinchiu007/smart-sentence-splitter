"""CLI 入口：sentence-splitter.

Usage:
    sentence-splitter -i input.txt -o output.json
    sentence-splitter -i input.txt -o output.json --language en
    sentence-splitter -i input.txt -o output.json --enable-llm --enable-era
    sentence-splitter -i input.txt -o output.json --config my-config.yaml
    cat input.txt | sentence-splitter > output.json
"""

from __future__ import annotations
import argparse
import sys
import json
from pathlib import Path
from typing import Optional

from ..pipeline import SmartSentenceSplitter
from ..utils.config_loader import load_config
from ..utils.serializer import to_json


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sentence-splitter",
        description="PROJECT-012 语义分句引擎 CLI",
    )
    parser.add_argument("-i", "--input", help="输入文件路径（默认 stdin）", default=None)
    parser.add_argument("-o", "--output", help="输出文件路径（默认 stdout）", default=None)
    parser.add_argument("--language", choices=["auto", "zh", "en", "ja", "mixed"], default="auto", help="目标语言")
    parser.add_argument("--config", help="配置文件路径（YAML 或 JSON）", default=None)
    parser.add_argument("--enable-llm", action="store_true", help="启用 LLM tier（需配置 API key）")
    parser.add_argument("--enable-era", action="store_true", help="启用时代检测")
    parser.add_argument("--min-tier", type=int, choices=[1, 2, 3], default=2, help="最低允许的 tier")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--pretty", action="store_true", default=True, help="格式化 JSON 输出")
    parser.add_argument("--compact", action="store_true", help="紧凑 JSON 输出（覆盖 --pretty）")

    args = parser.parse_args(argv)

    # 1. 加载配置
    if args.config:
        config = load_config(args.config)
    else:
        config = load_config(None)

    # 2. 覆盖 CLI 参数
    config["language"] = args.language
    config["min_tier"] = args.min_tier
    if args.enable_llm:
        config["enable_llm"] = True
    if args.enable_era:
        config["enable_era"] = True

    # 3. 读取输入
    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"❌ 输入文件不存在: {args.input}", file=sys.stderr)
            return 1
        text = input_path.read_text(encoding="utf-8")
    else:
        if sys.stdin.isatty():
            print("⚠️  未指定 --input，进入交互模式。输入文本后按 Ctrl+Z 结束：", file=sys.stderr)
        text = sys.stdin.read()

    if not text or not text.strip():
        print("❌ 输入文本为空", file=sys.stderr)
        return 1

    # 4. 处理
    if args.verbose:
        print(
            f"⚙️  配置: language={config['language']}, min_tier={config['min_tier']}, "
            f"enable_era={config['enable_era']}, enable_llm={config['enable_llm']}",
            file=sys.stderr,
        )

    splitter = SmartSentenceSplitter(config)
    result = splitter.split(text)

    if args.verbose:
        print(
            f"✅ 处理完成: language={result.language}, tier={result.tier_used}, "
            f"sentences={len(result.sentences)}, scenes={result.total_scenes}, "
            f"duration={result.total_duration:.1f}s",
            file=sys.stderr,
        )

    # 5. 序列化输出
    indent = None if args.compact else 2
    output_text = to_json(result.to_dict(), indent=indent)

    if args.output:
        Path(args.output).write_text(output_text, encoding="utf-8")
        if args.verbose:
            print(f"📄 已保存到: {args.output}", file=sys.stderr)
    else:
        print(output_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
