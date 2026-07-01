"""端到端实测: PROJECT-012 剧本 → 真实 PROJECT-011 优化。

需要 PROJECT-011 跑在 8013 端口:
    cd /c/Users/邱领/projects/prompt-engine
    uvicorn prompt_engine.api.rest:app --port 8013
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from splitter import SmartSentenceSplitter
from splitter.exporter.prompt_engine import PromptEngineExporter
from splitter.exporter.prompt_engine_client import PromptEngineClient

print("=" * 60)
print("PROJECT-012 → PROJECT-011 端到端 (真实 HTTP)")
print("=" * 60)

# 1. 检查 PROJECT-011 健康
client = PromptEngineClient(base_url="http://127.0.0.1:8013", timeout=60)
if not client.health_check():
    print("❌ PROJECT-011 未运行")
    print("启动: cd /c/Users/邱领/projects/prompt-engine && uvicorn prompt_engine.api.rest:app --port 8013")
    sys.exit(1)
print("✅ PROJECT-011 在线")

# 2. 分句 + 剧本分析
text = """小明走进超市。他拿了一瓶水。小红在公园等他。

小明回到家。妈妈说：学校停课了。

第二天，小明和小红决定去公园碰碰运气。"""

splitter = SmartSentenceSplitter({
    "length": {"strategy": "A", "min_chars": 3, "max_chars": 15},
    "enable_script_analysis": True,
})
result = splitter.split(text)
print(f"\n✂️ 分句: {len(result.sentences)} 句 / {len(result.scenes)} 场")

# 3. 构造优化请求
exporter = PromptEngineExporter()
requests = []
for scene in result.scenes:
    for sentence in scene.sentences:
        requests.append(exporter.to_optimize_request(sentence))
print(f"📦 构造 {len(requests)} 条优化请求")

# 4. 真实批量调用 PROJECT-011
print(f"\n🚀 调 PROJECT-011 /v1/optimize/batch ...")
try:
    results = client.optimize_batch(requests)
    print(f"✅ 收到 {len(results)} 条响应")
    print(f"\n📝 优化结果:")
    for i, (req, resp) in enumerate(zip(requests[:3], results[:3])):
        print(f"\n  [{i+1}] 输入: {req['prompt'][:30]}")
        opt = resp.get('optimized_prompt', '')[:80]
        print(f"      输出: {opt}...")
        print(f"      tokens: {resp.get('tokens_used', 0)}")
except Exception as e:
    print(f"❌ 调用失败: {e}")
    import traceback
    traceback.print_exc()