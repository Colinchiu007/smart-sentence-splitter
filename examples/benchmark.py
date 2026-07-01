"""性能基准测试 — PROJECT-012 全链路 (v0.8.2 新增).

测试场景:
- 短文: 100 字
- 中文: 1000 字
- 长文: 5000 字
- 超长: 50000 字

测量:
- 延迟 (ms)
- 内存峰值 (MB)
- 吞吐量 (字/秒)
- 各阶段耗时占比

用法:
    python examples/benchmark.py [--scenario all|short|medium|long|xlarge]
"""

import sys
import gc
import time
import json
import tracemalloc
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from splitter import SmartSentenceSplitter


# ===== 测试文本 =====

SHORT_TEXT = """
今天天气真好。阳光明媚。

小明走进超市。他拿了一瓶水。小红在公园等他。

小明回到家。妈妈说：学校停课了。
""" * 1

MEDIUM_TEXT = """
清军在甲午战争中死磕到底。这场战争影响深远。中华民族从此陷入深渊。

然而，正是在这样的民族危亡时刻，无数仁人志士开始了救亡图存的探索。

从洋务运动到戊戌变法，从辛亥革命到新文化运动，一代又一代的中国人前仆后继，谱写了一曲曲可歌可泣的壮丽史诗。

他们中有的人主张改良，有的人主张革命。康有为、梁启超、孙中山，这些名字如雷贯耳。他们在黑暗中探索，在困境中前行。

最终，中国共产党在1921年成立了。这给中华民族带来了新的希望。
""" * 3

LONG_TEXT = """
人工智能技术发展迅速。深度学习是其中的核心技术。神经网络模型经历了从CNN到RNN再到Transformer的演进。

大语言模型的崛起，彻底改变了人机交互的方式。GPT、BERT、LLaMA等模型层出不穷。它们在文本生成、问答、翻译等任务上表现出色。

AI生成图片技术也飞速发展。DALL·E、Midjourney、Stable Diffusion等工具让创作者如虎添翼。文生图、图生图、图生视频，整个创作流程都被AI重塑了。

AI短剧是最新风口。通过剧本分镜、自动配图、批量生成视频等技术，一个人就能制作一部短剧。这是创业者的蓝海。

未来，AI Agent将更深入到工作流中。从简单工具到协作伙伴，AI的形态正在发生根本变化。
""" * 8

XLARGE_TEXT = LONG_TEXT * 10


# ===== 基准器 =====

class Benchmark:
    def __init__(self, name, text, config=None):
        self.name = name
        self.text = text
        self.config = config or {}
        self.results = {}

    def run(self):
        gc.collect()
        # 第一次跑时 jieba 加载慢, 预热
        try:
            SmartSentenceSplitter({"mode": "fast"}).split("预热。")
        except Exception:
            pass

        tracemalloc.start()
        t0 = time.perf_counter()
        try:
            splitter = SmartSentenceSplitter(self.config)
            t_init = time.perf_counter() - t0

            t1 = time.perf_counter()
            result = splitter.split(self.text)
            t_split = time.perf_counter() - t1

            t2 = time.perf_counter()
            result_dict = result.to_dict()
            t_serialize = time.perf_counter() - t2

            t_total = time.perf_counter() - t0
            current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        text_len = len(self.text)
        return {
            "scenario": self.name,
            "text_length": text_len,
            "scenes": len(result.scenes),
            "sentences": len(result.sentences),
            "tier_used": result.tier_used,
            "timing": {
                "init_s": round(t_init, 4),
                "split_s": round(t_split, 4),
                "serialize_s": round(t_serialize, 4),
                "total_s": round(t_total, 4),
            },
            "throughput_chars_per_s": round(text_len / t_total, 1) if t_total > 0 else 0,
            "memory_mb": {
                "current": round(current / 1024 / 1024, 2),
                "peak": round(peak / 1024 / 1024, 2),
            },
        }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="all",
                       choices=["all", "short", "medium", "long", "xlarge"])
    args = parser.parse_args()

    scenarios = {
        "short": (SHORT_TEXT, 100),
        "medium": (MEDIUM_TEXT, 1500),
        "long": (LONG_TEXT, 5000),
        "xlarge": (XLARGE_TEXT, 50000),
    }

    if args.scenario == "all":
        selected = scenarios.keys()
    else:
        selected = [args.scenario]

    print("=" * 80)
    print("PROJECT-012 性能基准测试")
    print("=" * 80)

    # 启动时预热 (jieba 加载, tracemalloc 初始化, lazy 分词器预热)
    gc.collect()
    tracemalloc.start()
    try:
        # 预热 jieba 词性标注 (length A 模式 + 剧本分析都用到)
        SmartSentenceSplitter({"length": {"strategy": "A", "max_chars": 15}}).split("中文分句预热。这是一段包含各种标点（。、！？）的测试文本。")
        SmartSentenceSplitter({"enable_script_analysis": True}).split("小明走进超市。")
    except Exception:
        pass
    tracemalloc.stop()

    all_results = []
    for name in selected:
        text, expected_len = scenarios[name]
        actual_len = len(text)
        if actual_len > 10000:
            config = {"mode": "fast"}
        else:
            config = {"length": {"strategy": "A", "max_chars": 15}}

        gc.collect()
        tracemalloc.start()
        bench = Benchmark(name, text, config)
        result = bench.run()  # 内部会 stop tracemalloc
        all_results.append(result)
        print(f"\n--- {name.upper()} ({actual_len} 字) ---")
        print(f"  句子: {result['sentences']} | 场景: {result['scenes']} | tier: {result['tier_used']}")
        print(f"  耗时:")
        print(f"    init:      {result['timing']['init_s']*1000:>8.1f} ms")
        print(f"    split:     {result['timing']['split_s']*1000:>8.1f} ms")
        print(f"    serialize: {result['timing']['serialize_s']*1000:>8.1f} ms")
        print(f"    total:     {result['timing']['total_s']*1000:>8.1f} ms")
        print(f"  吞吐量: {result['throughput_chars_per_s']:>8.1f} 字/秒")
        print(f"  内存 (peak): {result['memory_mb']['peak']:>6.1f} MB")

    # 总结
    print(f"\n{'='*80}")
    print("基准测试总结")
    print(f"{'='*80}")
    print(f"{'场景':<10} {'字数':<8} {'延迟(ms)':<12} {'吞吐量(字/s)':<14} {'内存(MB)':<10}")
    for r in all_results:
        print(f"{r['scenario']:<10} {r['text_length']:<8} "
              f"{r['timing']['total_s']*1000:<12.1f} "
              f"{r['throughput_chars_per_s']:<14.1f} "
              f"{r['memory_mb']['peak']:<10.1f}")

    report_path = Path("/tmp/p012_benchmark.json")
    report_path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2))
    print(f"\n报告已保存: {report_path}")


if __name__ == "__main__":
    main()