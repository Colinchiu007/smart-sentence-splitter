# PM-PRD-v0.4 — LLM Tier 完整实做

**版本**: v0.4.0
**日期**: 2026-06-13
**作者**: PM (COO role)
**关联**: v0.3 LLMSplitter stub 兑现 + v0.4.0 路线图

---

## 1. 背景

v0.3 留了 `LLMSplitter` stub（`is_available()=False`），承诺 v0.3.1+ 实做。
本迭代兑现承诺，将 LLM Tier 从 stub 升级为**真实可用的 Tier 1**。

## 2. 目标

| 目标 | 描述 |
|------|------|
| **G1 真实 LLM 调用** | LLMSplitter.split() 真正能跑（不再抛 NotImplementedError） |
| **G2 多 Provider 适配** | OpenAI / xfyun MAAS / Ollama 三大主流 LLM 服务 |
| **G3 自动降级** | LLM 不可用时自动 fallback 到 Tier 2/3 |
| **G4 API Key 安全管理** | 走环境变量，不硬编码 |
| **G5 prompt 模板化** | 分句 prompt 可调，配置化 |
| **G6 响应容错** | LLM 返回非 JSON / 解析失败 → fallback 而非崩溃 |

## 3. 文件改动清单

| 文件 | 操作 | 工期 |
|------|------|------|
| `src/splitter/llm/__init__.py` | 新建（package 入口） | 0.05 |
| `src/splitter/llm/base.py` | 新建（Provider 抽象基类） | 0.15 |
| `src/splitter/llm/openai_provider.py` | 新建（OpenAI 适配） | 0.2 |
| `src/splitter/llm/xfyun_provider.py` | 新建（讯飞 MAAS 适配） | 0.2 |
| `src/splitter/llm/ollama_provider.py` | 新建（Ollama 本地适配） | 0.1 |
| `src/splitter/llm/prompts.py` | 新建（prompt 模板） | 0.1 |
| `src/splitter/tiers/tier1_llm.py` | 重构（stub → 实做） | 0.3 |
| `src/splitter/pipeline.py` | 集成（mode=precise 加 LLM） | 0.2 |
| `src/splitter/utils/config_loader.py` | 增强（api_key_env 加载） | 0.1 |
| `config/splitter.yaml` | 加 llm 段 | 0.05 |
| `tests/unit/test_llm_base.py` | 新建（10 测试） | 0.1 |
| `tests/unit/test_llm_providers.py` | 新建（15 测试 + mock） | 0.2 |
| `tests/unit/test_tier1_llm.py` | 新建（10 测试，重构） | 0.1 |
| `tests/integration/test_v4.py` | 新建（8 集成测试） | 0.1 |
| | | **总计 2.0 天** |

## 4. 详细设计

### 4.1 Provider 抽象基类

```python
class LLMProvider(ABC):
    name: str  # "openai" / "xfyun" / "ollama"
    tier: str = "tier1_llm"

    @abstractmethod
    def is_available(self) -> bool:
        """检查 API key 是否配置。"""

    @abstractmethod
    def chat(self, messages: List[Dict], **kwargs) -> str:
        """调用 LLM，返回文本。"""

    @property
    @abstractmethod
    def model(self) -> str:
        """模型名。"""
```

### 4.2 OpenAI Provider

```python
class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, model="gpt-4o-mini", api_key=None, base_url=None, timeout=30):
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url
        self.timeout = timeout

    def is_available(self) -> bool:
        return self.api_key is not None

    def chat(self, messages, **kwargs):
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout)
        resp = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=kwargs.get("temperature", 0.0),
            max_tokens=kwargs.get("max_tokens", 4096),
        )
        return resp.choices[0].message.content
```

### 4.3 xfyun Provider

讯飞 MAAS API（OpenAI 兼容）。`base_url` 默认 `https://maas-api.cn-huabei-1.xf-yun.com/v1`。

```python
class XfyunProvider(LLMProvider):
    name = "xfyun"
    DEFAULT_BASE = "https://maas-api.cn-huabei-1.xf-yun.com/v1"

    def __init__(self, model="astron-code-latest", api_key=None, base_url=None, timeout=30):
        self.model = model
        self.api_key = api_key or os.getenv("XFYUN_API_KEY")
        self.base_url = base_url or self.DEFAULT_BASE
        self.timeout = timeout

    def is_available(self):
        return self.api_key is not None

    def chat(self, messages, **kwargs):
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout)
        # 讯飞 MAAS 与 OpenAI 协议兼容
        resp = client.chat.completions.create(model=self.model, messages=messages, ...)
        return resp.choices[0].message.content
```

### 4.4 Ollama Provider

本地 LLM（零成本、零数据外传）。

```python
class OllamaProvider(LLMProvider):
    name = "ollama"
    DEFAULT_BASE = "http://localhost:11434/v1"

    def __init__(self, model="qwen2.5:7b", base_url=None, timeout=60):
        self.model = model
        self.base_url = base_url or self.DEFAULT_BASE
        self.timeout = timeout

    def is_available(self):
        # 检查 /api/tags 端点
        try:
            requests.get(self.base_url + "/api/tags", timeout=2)
            return True
        except Exception:
            return False
```

### 4.5 Prompt 模板

```python
SPLIT_PROMPT = """你是一个文本分句专家。请将以下文本切分为语义完整的句子。

要求：
1. 按句末标点（。！？.!?;）切分
2. 保留引号/括号完整性
3. 不要修改原文
4. 输出 JSON 数组，每个元素是一个完整句子

示例：
输入: "今天天气真好。我们去公园。路上遇到了朋友。"
输出: ["今天天气真好。", "我们去公园。", "路上遇到了朋友。"]

输入: "Dr. Smith said 'Hello.' Then he left."
输出: ["Dr. Smith said 'Hello.'", "Then he left."]

请处理以下文本（用 JSON 数组输出，不要任何其他内容）：
{text}
"""
```

### 4.6 重构后的 LLMSplitter

```python
class LLMSplitter(BaseSentenceSplitter):
    language = "auto"
    tier = "tier1_llm"

    def __init__(self, config=None):
        cfg = config or {}
        provider_name = cfg.get("provider", "openai")
        self.provider = self._build_provider(provider_name, cfg)
        self.max_retries = cfg.get("max_retries", 2)
        self.timeout = cfg.get("timeout", 30)

    def _build_provider(self, name, cfg):
        if name == "openai":
            return OpenAIProvider(
                model=cfg.get("model", "gpt-4o-mini"),
                base_url=cfg.get("base_url"),
                timeout=cfg.get("timeout", 30),
            )
        elif name == "xfyun":
            return XfyunProvider(
                model=cfg.get("model", "astron-code-latest"),
                base_url=cfg.get("base_url"),
                timeout=cfg.get("timeout", 30),
            )
        elif name == "ollama":
            return OllamaProvider(
                model=cfg.get("model", "qwen2.5:7b"),
                base_url=cfg.get("base_url"),
                timeout=cfg.get("timeout", 60),
            )
        else:
            raise ValueError(f"Unknown LLM provider: {name}")

    def is_available(self) -> bool:
        return self.provider.is_available()

    def split(self, text) -> List[SentenceBlock]:
        if not self.is_available():
            raise NotImplementedError(
                "LLM Tier not available (no API key). "
                "Set OPENAI_API_KEY env var or disable mode=precise."
            )
        prompt = SPLIT_PROMPT.format(text=text)
        messages = [
            {"role": "system", "content": "你是一个文本分句专家。"},
            {"role": "user", "content": prompt},
        ]
        # 重试
        for attempt in range(self.max_retries + 1):
            try:
                response = self.provider.chat(messages)
                sentences = self._parse_response(response, text)
                return [self._make_block(s, i) for i, s in enumerate(sentences)]
            except Exception as e:
                if attempt < self.max_retries:
                    continue
                raise
        raise RuntimeError("Unreachable")

    def _parse_response(self, response: str, original_text: str) -> List[str]:
        """解析 LLM 响应，容错。"""
        # 1. 尝试直接 JSON 解析
        try:
            data = json.loads(response)
            if isinstance(data, list):
                return [str(s) for s in data if s]
        except json.JSONDecodeError:
            pass
        # 2. 尝试从响应中提取 JSON 数组
        match = re.search(r"\[.*?\]", response, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, list):
                    return [str(s) for s in data if s]
            except json.JSONDecodeError:
                pass
        # 3. 兜底：按行切分
        return [line.strip() for line in response.split("\n") if line.strip()]
```

### 4.7 Pipeline 集成

```python
# pipeline.py 中
zh_splitters: List[BaseSentenceSplitter] = []
if self.llm_enabled and LLMSplitter({...}).is_available():
    zh_splitters.append(LLMSplitter(self.config.get("llm", {})))
if self.enable_topic_seg:
    zh_splitters.append(TextTilingSemanticSplitter(...))
zh_splitters.append(ChineseSplitter(...))
zh_splitters.append(ChineseRuleSplitter())
```

## 5. 配置设计

```yaml
# config/splitter.yaml
llm:
  provider: "openai"  # openai | xfyun | ollama
  model: "gpt-4o-mini"
  api_key_env: "OPENAI_API_KEY"  # 环境变量名
  base_url: null  # 自定义 base_url（xfyun/ollama 自动设置）
  timeout: 30
  max_retries: 2
  temperature: 0.0  # 分句要确定性 → 0
  max_tokens: 4096
```

## 6. 验收测试矩阵

| # | 测试 | 期望 |
|---|------|------|
| T1 | OpenAIProvider.is_available() 无 key → False | ✅ |
| T2 | OpenAIProvider.is_available() 有 key → True | ✅ |
| T3 | OpenAIProvider.chat() 成功 (mocked) → 返回字符串 | ✅ |
| T4 | xfyun base_url 默认值正确 | ✅ |
| T5 | OllamaProvider.is_available() 探测端点 | ✅ |
| T6 | LLMSplitter is_available() 集成 | ✅ |
| T7 | LLMSplitter split() 成功 → 返回 SentenceBlock 列表 | ✅ |
| T8 | LLMSplitter split() LLM 返回非 JSON → 兜底行切分 | ✅ |
| T9 | LLMSplitter split() 重试机制 | ✅ |
| T10 | Pipeline mode=precise + llm enabled 走 LLM | ✅ |
| T11 | Pipeline LLM 不可用 → 自动降级到 Tier 2 | ✅ |
| T12 | 配置加载 api_key_env | ✅ |
| T13 | Prompt 模板包含必要指令 | ✅ |

## 7. 风险

| 风险 | 缓解 |
|------|------|
| LLM 响应格式不稳定 | 多层 fallback：JSON → 正则提取 → 行切分 |
| API key 泄露 | 只读环境变量，不写入日志/异常 |
| LLM 慢/超时 | timeout 配置 + 重试 + 自动降级到 Tier 2/3 |
| LLM 幻觉（修改原文） | prompt 明确"不要修改原文" + 输出与原文对账 |
| LLM 依赖体积 | `openai` 是 optional dependency，pyproject 已声明 |

## 8. 工期

| 日期 | 工作 |
|------|------|
| 6-14 上午 | PM-PRD + Provider 抽象 + 3 个 Provider 实现 |
| 6-14 下午 | LLMSplitter 重构 + pipeline 集成 + 配置 |
| 6-14 晚 | 测试（含 mock）+ 文档同步 |
| 6-15 上午 | commit + tag v0.4.0 + push |

---

**下一步**：CEO 签字后进入 TDD 实现。
