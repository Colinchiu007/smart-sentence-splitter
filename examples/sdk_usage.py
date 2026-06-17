"""SDK usage example for PROJECT-012 Smart Sentence Splitter."""

from splitter import SmartSentenceSplitter
from splitter.utils import to_json


def main():
    # === 1. 最简调用 ===
    print("=" * 60)
    print("示例 1: 最简调用")
    print("=" * 60)

    splitter = SmartSentenceSplitter()
    text = "今天天气真好。我们去公园散步。路上遇到了朋友。"
    result = splitter.split(text)

    print(f"语言: {result.language}")
    print(f"使用 tier: {result.tier_used}")
    print(f"句子数: {len(result.sentences)}")
    print(f"场景数: {result.total_scenes}")
    print(f"总时长: {result.total_duration:.1f}s")

    print("\n分句结果:")
    for s in result.sentences:
        print(f"  [{s.index}] {s.text}")

    print("\n场景结构:")
    for scene in result.scenes:
        print(f"  Scene {scene.segment_id}: {scene.text[:30]}... "
              f"({scene.target_words}字, {scene.estimated_duration:.1f}s, "
              f"{len(scene.subtitles)} 字幕块)")
        if scene.era_info:
            print(f"    └─ era: {scene.era_info.era} "
                  f"(conf: {scene.era_info.confidence:.2f}, "
                  f"keywords: {scene.era_info.keywords[:3]})")

    # === 2. 自定义配置 ===
    print("\n" + "=" * 60)
    print("示例 2: 自定义配置（更短的场景）")
    print("=" * 60)

    custom = {
        "scene": {
            "target_seconds": 3.0,  # 3秒一段
            "min_words_per_segment": 5,
            "max_words_per_segment": 20,
        },
        "enable_era": True,
    }
    splitter2 = SmartSentenceSplitter(custom)
    result2 = splitter2.split(text)
    print(f"场景数: {result2.total_scenes}（应当比示例 1 多）")

    # === 3. 英文输入 ===
    print("\n" + "=" * 60)
    print("示例 3: 英文输入")
    print("=" * 60)

    en_text = (
        "Dr. Smith and Mr. Wang went to the U.S. yesterday. "
        'They were discussing the latest research in artificial intelligence. '
        '"The results were amazing," Dr. Smith said.'
    )
    result3 = splitter2.split(en_text)
    print(f"语言: {result3.language}")
    print(f"句子数: {len(result3.sentences)}")
    for s in result3.sentences:
        print(f"  [{s.index}] {s.text}")

    # === 4. 输出 JSON ===
    print("\n" + "=" * 60)
    print("示例 4: JSON 输出")
    print("=" * 60)

    json_str = to_json(result.to_dict())
    print(json_str[:500] + "...")


if __name__ == "__main__":
    main()
