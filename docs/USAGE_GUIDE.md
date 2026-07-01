# PROJECT-012 — AI 使用指南 (USAGE GUIDE)

> 给开发者 / AI Agent 看的集成手册。覆盖全部 4 种调用方式。

---

## 一、快速总览

| 方式 | 适合场景 | 一句话 |
|------|---------|--------|
| **Python SDK** | Python 项目内嵌 | `pip install -e .` → `import SmartSentenceSplitter` |
| **REST API** | 任何语言 | `docker compose up` → `POST /v1/split` |
| **CLI** | 命令行/管道 | `cat input.txt | sentence-splitter` |
| **MCP Server** | AI Agent 工具调用 | `python -m splitter.api.mcp_server` |

---

## 二、Python SDK（推荐）

### 安装

```bash
# 核心（仅 pydantic + PyYAML，300KB）
pip install -e .

# 含语义分句（jieba，推荐）
pip install -e ".[semantic]"

# 全量（含 streamlit/fastapi）
pip install -e ".[all]"
```

### 基本用法

```python
from splitter import SmartSentenceSplitter

splitter = SmartSentenceSplitter()
result = splitter.split("今天天气真好。我们去公园。")

for s in result.sentences:
    print(f"[{s.index}] {s.text}  {s.length_status}")
```

### 完整配置

```python
config = {
    "language": "auto",            # auto | zh | en | ja
    "mode": "balanced",            # fast | balanced | precise
    "enable_script_analysis": True,# 角色/场景提取
    "enable_topic_segmentation": True,  # 语义段落检测
    "enable_era": False,           # 时代检测（古/现）
    "enable_llm": False,           # LLM 分句（需 API key）
    "length": {
        "strategy": "B",           # A=重切 | B=标尺 | off=透传
        "min_chars": 3,
        "max_chars": 15,
    },
}
result = SmartSentenceSplitter(config).split("你的文本")
```

### 输出结构

```python
result.language        # "zh" | "en" | "ja" | "mixed"
result.tier_used       # 实际使用的 tier 名称
result.sentences       # List[SentenceBlock]
result.scenes          # List[SceneSegment]
result.script_analysis # dict | None: {characters, settings, synopsis}

# SentenceBlock:
s.text                # str
s.index               # int
s.tier                # str
s.language            # str
s.length_status       # "ok"|"too_long"|"too_short"
s.is_topic_boundary   # bool (语义段落边界)
s.confidence          # float

# SceneSegment:
sc.text               # str
sc.segment_id         # int
sc.characters         # List[str]（脚本分析填充）
sc.setting            # str（脚本分析填充）
sc.mood               # str（情绪推断）
sc.estimated_duration # float（秒）
sc.sentences          # List[SentenceBlock]
sc.subtitles          # List[SubtitleBlock]
```

### 导出格式

```python
from splitter.exporter.subtitle_exporter import SubtitleExporter
from splitter.exporter.storyboard import StoryboardExporter
from splitter.exporter.prompt_engine import PromptEngineExporter

sub = SubtitleExporter()
srt = sub.to_srt(result.scenes)   # str
ass = sub.to_ass(result.scenes)   # str

sb = StoryboardExporter()
story = sb.to_storyboard(result.scenes)  # dict

pe = PromptEngineExporter()
batch = pe.from_split_result(result)  # List[dict] → PROJECT-011
```

### 与 PROJECT-011 桥接

```python
from splitter.exporter.prompt_engine import PromptEngineExporter
from splitter.exporter.prompt_engine_client import PromptEngineClient

exp = PromptEngineExporter()
batch = exp.from_split_result(result)
# 每条请求含 context: {synopsis, character, setting, character_list}

client = PromptEngineClient("http://localhost:8013")
client.optimize_batch(batch)
```

---

## 三、REST API（跨语言）

### 启动

```bash
# 方式 1: 直接运行
uvicorn splitter.api.rest_api:app --host 0.0.0.0 --port 8000

# 方式 2: 通过模块
python -m splitter.api.rest_api

# 环境变量
PORT=8000 HOST=0.0.0.0 python -m splitter.api.rest_api
```

### 端点

```
GET  /health              → {"status": "ok", "version": "0.9.10"}
GET  /capabilities        → 能力声明 (tiers/languages/modes)
GET  /v1/info             → 运行时配置
POST /v1/split            → 单文本分句
POST /v1/split/batch      → 批量分句 (v0.9.6)
```

### POST /v1/split 示例

```bash
curl -X POST http://localhost:8000/v1/split \
  -H "Content-Type: application/json" \
  -d '{"text": "今天天气真好。我们去公园散步。",
       "mode": "balanced",
       "enable_script_analysis": true}'
```

响应:
```json
{
  "text_length": 14,
  "language": "zh",
  "tier_used": "tier2_semantic",
  "total_scenes": 1,
  "sentences": [{"index": 0, "text": "今天天气真好。", ...}],
  "scenes": [{"segment_id": 0, "text": "...", "characters": [], ...}]
}
```

### POST /v1/split/batch 示例

```bash
curl -X POST http://localhost:8000/v1/split/batch \
  -H "Content-Type: application/json" \
  -d '{"texts": ["今天天气真好。", "Hello world."],
       "config": {"mode": "fast"}}'
```

---

## 四、MCP Server（AI Agent 专用）

### 启动

```bash
python -m splitter.api.mcp_server
```

### 暴露的工具

```
smart_splitter(text: str, config: dict = None) -> dict
  - 分句工具，返回完整 SplitResult JSON

text_to_sentences(text: str) -> list[str]
  - 快速分句，只返回句子文本列表
```

### 在 Hermes / Claude Code / Codex 中使用

```
# 在 MCP 配置中注册
{
  "mcpServers": {
    "smart-sentence-splitter": {
      "command": "python",
      "args": ["-m", "splitter.api.mcp_server"],
      "cwd": "/path/to/PROJECT-012"
    }
  }
}
```

---

## 五、CLI

```bash
# 文件输入
sentence-splitter -i input.txt -o output.json

# 管道输入
cat input.txt | sentence-splitter --language auto

# 指定配置
sentence-splitter -i input.txt --mode fast --enable-era

# 语言指定
sentence-splitter -i input.txt --language en
```

---

## 六、Streamlit 工作台

```bash
streamlit run workbench/app.py --server.port 8501
```

打开 `http://localhost:8501`。4 个标签页：
- 📝 分句 — 实时分句 + 剧本分析
- 📺 字幕 — SRT + ASS 导出
- 🎬 分镜 — Storyboard 视图
- 🔗 提示词 — PROJECT-011 导出

---

## 七、导出/分发给其他软件

### 方式 A: pip 包（推荐）

```bash
# 构建 wheel
pip install build
python -m build

# 产物在 dist/ 目录
# smart_sentence_splitter-0.9.10-py3-none-any.whl

# 其他软件安装
pip install smart_sentence_splitter-0.9.10-py3-none-any.whl
```

### 方式 B: Docker 镜像

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e ".[all]"
EXPOSE 8000
CMD ["uvicorn", "splitter.api.rest_api:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t smart-sentence-splitter .
docker run -p 8000:8000 smart-sentence-splitter
```

### 方式 C: REST API 服务（最通用）

不依赖 Python 环境，任何语言通过 HTTP 调用：

```javascript
// JavaScript / Node.js
fetch('http://localhost:8000/v1/split', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({text: "今天天气真好。", mode: "fast"})
}).then(r => r.json()).then(console.log);
```

```java
// Java (OkHttp)
OkHttpClient client = new OkHttpClient();
String json = "{\"text\":\"今天天气真好。\",\"mode\":\"fast\"}";
Request request = new Request.Builder()
  .url("http://localhost:8000/v1/split")
  .post(RequestBody.create(json, MediaType.parse("application/json")))
  .build();
Response response = client.newCall(request).execute();
```

```go
// Go
resp, _ := http.Post("http://localhost:8000/v1/split",
  "application/json",
  strings.NewReader(`{"text":"今天天气真好。","mode":"fast"}`))
defer resp.Body.Close()
body, _ := io.ReadAll(resp.Body)
fmt.Println(string(body))
```

---

## 八、性能参考

| 文本大小 | 耗时 | 适用场景 |
|---------|------|---------|
| 50 字 | 15ms | 实时字幕 |
| 1KB | 56ms | 短剧本 |
| 100KB | 418ms | 长文章 |
| 1MB | 5.8s | 大文件 |
| 25,000 字 | 200ms | 批量处理 |

---

## 九、AI Agent 集成清单

如果你是一个 AI Agent 要集成 PROJECT-012，请按此步骤：

1. **安装**: `pip install -e "C:/path/to/PROJECT-012"` 或 REST API
2. **测试**: `from splitter import SmartSentenceSplitter; s = SmartSentenceSplitter(); r = s.split("测试"); print(len(r.sentences))`
3. **核心调用**: `SmartSentenceSplitter(config).split(text)` → `SplitResult`
4. **获取句子**: `result.sentences[i].text`
5. **获取场景**: `result.scenes[i].text`
6. **获取角色**: `result.script_analysis["characters"]`
7. **生成字幕**: `SubtitleExporter().to_srt(result.scenes)`
8. **生成分镜**: `StoryboardExporter().to_storyboard(result.scenes)`
9. **桥接 011**: `PromptEngineExporter().from_split_result(result)` → 带 context 的 batch

---

## 十、文件结构（集成关注点）

```
PROJECT-012/
├── src/splitter/
│   ├── pipeline.py        ← 主编排入口 (你只需要这个)
│   ├── api/
│   │   ├── rest_api.py    ← FastAPI (如需 HTTP)
│   │   └── mcp_server.py  ← MCP (如需 Agent 工具)
│   ├── exporter/
│   │   ├── subtitle_exporter.py  ← SRT/ASS
│   │   ├── storyboard.py         ← 分镜
│   │   └── prompt_engine.py      ← 011 桥接
│   └── scene_subtitle/
│       ├── scene_segmenter.py    ← 场景分割
│       └── subtitle_segmenter.py ← 字幕分割
├── tests/                 ← 353 个测试
└── workbench/app.py       ← Streamlit GUI
```
