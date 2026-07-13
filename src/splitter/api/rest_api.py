"""REST API (FastAPI) - v0.5 新增.

端点:
- GET  /health          — 健康检查
- GET  /capabilities    — 能力声明 (tiers/languages/modes)
- POST /v1/split        — 文本分句
- POST /v1/split/batch  — 批量分句 (v0.9.6)
- GET  /v1/info         — 版本 + 配置信息

启动:
    uvicorn splitter.api.rest_api:app --reload
    # 或
    python -m splitter.api.rest_api
"""

from __future__ import annotations
import os
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .. import __version__
from ..pipeline import SmartSentenceSplitter
from ..models import SplitResult
from ..core.base_splitter import BaseSentenceSplitter


# === Pydantic 请求/响应模型 ===


class SplitRequest(BaseModel):
    """POST /v1/split 请求体。"""

    text: str = Field(..., min_length=1, description="待分句的文本")
    language: str = Field(default="auto", description="auto | zh | en")
    mode: str = Field(default="balanced", description="fast | balanced | precise")
    enable_era: bool = Field(default=False, description="是否启用时代检测")
    enable_topic_segmentation: bool = Field(default=False, description="是否启用 TextTiling")
    enable_llm: bool = Field(default=False, description="是否启用 LLM Tier")
    config: Optional[Dict[str, Any]] = Field(default=None, description="额外配置覆盖")


class SentenceResponse(BaseModel):
    """分句结果中的单个句子。"""

    index: int
    text: str
    language: str
    tier: str
    confidence: float
    char_count: int
    is_topic_boundary: bool = False
    topic_depth_score: float = 0.0


class SceneResponse(BaseModel):
    """分句结果中的单个场景。"""

    segment_id: int
    text: str
    estimated_duration: float
    target_words: int
    era: Optional[str] = None
    era_confidence: Optional[float] = None
    subtitle_count: int = 0


class SplitResponse(BaseModel):
    """POST /v1/split 响应体。"""

    text_length: int
    language: str
    tier_used: str
    total_duration: float
    total_scenes: int
    sentences: List[SentenceResponse]
    scenes: List[SceneResponse]
    config_snapshot: Dict[str, Any]


class HealthResponse(BaseModel):
    """GET /health 响应。"""

    status: str
    version: str


class CapabilityInfo(BaseModel):
    """能力声明。"""

    name: str
    available: bool
    description: str


class CapabilitiesResponse(BaseModel):
    """GET /capabilities 响应。"""

    version: str
    languages: List[str]
    tiers: List[CapabilityInfo]
    modes: List[str]
    features: List[str]


class InfoResponse(BaseModel):
    """GET /v1/info 响应。"""

    version: str
    llm_available: bool
    llm_provider: Optional[str] = None
    era_enabled: bool
    topic_segmentation_enabled: bool


class SplitBatchRequest(BaseModel):
    """POST /v1/split/batch 请求体 (v0.9.6)."""

    texts: List[str] = Field(..., min_length=0, description="待分句的文本列表")
    config: Optional[Dict[str, Any]] = Field(default=None, description="统一配置覆盖")


class SplitBatchResponse(BaseModel):
    """POST /v1/split/batch 响应体 (v0.9.6)."""

    results: List[SplitResponse]


# === FastAPI app ===

app = FastAPI(
    title="Smart Sentence Splitter API",
    description="PROJECT-012 智能语义分句引擎 REST API",
    version=__version__,
)


def _detect_capabilities() -> CapabilitiesResponse:
    """动态检测能力。"""
    # 检测 LLM
    llm_openai = bool(os.getenv("OPENAI_API_KEY"))
    llm_xfyun = bool(os.getenv("XFYUN_API_KEY"))
    llm_ollama = False
    try:
        import requests

        resp = requests.get("http://localhost:11434/api/tags", timeout=1)
        llm_ollama = resp.status_code == 200
    except Exception:
        pass
    llm_any = llm_openai or llm_xfyun or llm_ollama

    tiers = [
        CapabilityInfo(name="tier1_llm", available=llm_any, description="LLM 语义分句（OpenAI/讯飞/Ollama）"),
        CapabilityInfo(
            name="tier2_texttiling",
            available=True,
            description="TextTiling 主题边界识别（需 enable_topic_segmentation）",
        ),
        CapabilityInfo(name="tier2_jieba", available=True, description="jieba 分词+词性标注（中文）"),
        CapabilityInfo(name="tier3_rule", available=True, description="规则分句（零依赖 fallback）"),
    ]

    return CapabilitiesResponse(
        version=__version__,
        languages=["zh", "en", "ja", "mixed", "auto"],
        tiers=tiers,
        modes=["fast", "balanced", "precise"],
        features=[
            "sentence_segmentation",
            "scene_segmentation",
            "subtitle_segmentation",
            "era_detection (optional)",
            "topic_boundary_detection (optional)",
            "user_dictionary (AC automaton)",
        ],
    )


@app.get("/health", response_model=HealthResponse)
def health():
    """健康检查。"""
    return HealthResponse(status="ok", version=__version__)


@app.get("/capabilities", response_model=CapabilitiesResponse)
def capabilities():
    """能力声明。"""
    return _detect_capabilities()


@app.get("/v1/info", response_model=InfoResponse)
def info():
    """运行时配置信息。"""
    # 临时构造 splitter 检测 LLM
    llm_avail = False
    llm_provider = None
    try:
        from splitter.tiers.tier1_llm import LLMSplitter

        s = LLMSplitter()
        llm_avail = s.is_available()
        llm_provider = s.provider_name if llm_avail else None
    except Exception:
        pass
    return InfoResponse(
        version=__version__,
        llm_available=llm_avail,
        llm_provider=llm_provider,
        era_enabled=False,  # 启动时默认不启用
        topic_segmentation_enabled=False,
    )


@app.post("/v1/split", response_model=SplitResponse)
def split(req: SplitRequest):
    """POST /v1/split — 核心分句端点。"""
    config: Dict[str, Any] = {}
    if req.config:
        config.update(req.config)
    config["language"] = req.language
    config["mode"] = req.mode
    config["enable_era"] = req.enable_era
    config["enable_topic_segmentation"] = req.enable_topic_segmentation
    config["enable_llm"] = req.enable_llm

    try:
        splitter = SmartSentenceSplitter(config)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Config error: {e}")

    try:
        result: SplitResult = splitter.split(req.text)
    except NotImplementedError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Split error: {e}")

    return _to_response(result, req)


@app.post("/v1/split/batch", response_model=SplitBatchResponse)
def split_batch(req: SplitBatchRequest):
    """POST /v1/split/batch — 批量分句 (v0.9.6)."""
    if not req.texts:
        return SplitBatchResponse(results=[])

    # 构造统一配置
    config: Dict[str, Any] = {}
    if req.config:
        config.update(req.config)

    try:
        splitter = SmartSentenceSplitter(config)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Config error: {e}")

    results: List[SplitResponse] = []
    for text in req.texts:
        if not text.strip():
            # 空文本跳过, 保持索引对应
            results.append(
                SplitResponse(
                    text_length=0,
                    language="",
                    tier_used="",
                    total_duration=0.0,
                    total_scenes=0,
                    sentences=[],
                    scenes=[],
                    config_snapshot={},
                )
            )
            continue
        try:
            result = splitter.split(text)
            # 构造一个最小 SplitRequest 给 _to_response (仅用于 text_length)
            dummy_req = SplitRequest(text=text)
            results.append(_to_response(result, dummy_req))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Split error for text #{len(results)}: {e}")

    return SplitBatchResponse(results=results)


@app.post("/v1/split/stream")
def split_stream(req: SplitRequest):
    """POST /v1/split/stream — SSE 流式分句端点。

    对超出 max_input_length 的大文本，按块处理并推送进度事件。
    小文本直接返回结果。

    SSE 事件:
      event: progress  → {"chunk_index": int, "chunks_total": int, "sentences_so_far": int}
      event: result    → SplitResponse JSON（最终完整结果）
      event: error     → {"detail": str}
    """
    config: Dict[str, Any] = {}
    if req.config:
        config.update(req.config)
    config["language"] = req.language
    config["mode"] = req.mode
    config["enable_era"] = req.enable_era
    config["enable_topic_segmentation"] = req.enable_topic_segmentation
    config["enable_llm"] = req.enable_llm

    try:
        splitter = SmartSentenceSplitter(config)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Config error: {e}")

    text = req.text
    max_length = config.get("max_input_length", 200000)

    import json

    def event_stream():
        # --- 小文本：一次处理，直接返回 ---
        if len(text) <= max_length:
            try:
                result = splitter.split(text)
            except NotImplementedError as e:
                yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
                return
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'detail': f'Split error: {e}'})}\n\n"
                return
            resp = _to_response(result, req)
            yield f"event: result\ndata: {resp.model_dump_json()}\n\n"
            return

        # --- 大文本：分块处理，推送进度 ---
        import re as _re

        # 与 pipeline.py _handle_large_text 一致的分块逻辑
        sent_chars = r"。！？；!?.\n…"
        sent_re = _re.compile(rf".*?[{sent_chars}]")
        blocks = sent_re.findall(text)

        if not blocks:
            blocks = [text[i : i + max_length] for i in range(0, len(text), max_length)]
        else:
            merged = "".join(blocks)
            remaining = text[len(merged) :]
            if remaining:
                blocks.append(remaining)

        chunked = []
        current = ""
        for block in blocks:
            if len(current) + len(block) > max_length:
                if current.strip():
                    chunked.append(current.strip())
                if len(block) > max_length:
                    for i in range(0, len(block), max_length):
                        sub = block[i : i + max_length]
                        if sub.strip():
                            chunked.append(sub.strip())
                    current = ""
                else:
                    current = block
            else:
                current += block
        if current.strip():
            chunked.append(current.strip())

        all_sentences = []
        chunks_total = len(chunked)
        last_tier = ""

        for i, chunk in enumerate(chunked):
            try:
                chunk_result = splitter.split(chunk)
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'detail': f'Chunk {i} error: {e}'})}\n\n"
                return

            all_sentences.extend(chunk_result.sentences)
            if chunk_result.tier_used:
                last_tier = chunk_result.tier_used

            # 推送进度
            progress = {
                "chunk_index": i,
                "chunks_total": chunks_total,
                "sentences_so_far": len(all_sentences),
            }
            yield f"event: progress\ndata: {json.dumps(progress)}\n\n"

        # 合并结果
        if all_sentences:
            scenes = splitter.scene_segmenter.segment(all_sentences)
            for scene in scenes:
                subtitles = splitter.subtitle_segmenter.segment(scene)
                scene.subtitles = subtitles

            from splitter.models import SplitResult as SR

            merged_result = SR(
                sentences=all_sentences,
                scenes=scenes,
                tier_used=last_tier,
                language=splitter._detect_lang(text),
                config_snapshot=splitter.config,
            )
            # 应用 postprocessor
            merged_result = splitter.postprocessor_chain.run(merged_result)
            resp = _to_response(merged_result, req)
            yield f"event: result\ndata: {resp.model_dump_json()}\n\n"
        else:
            yield f"event: result\ndata: {json.dumps({'text_length': len(text), 'sentences': [], 'scenes': []})}\n\n"

    from fastapi.responses import StreamingResponse

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _to_response(result: SplitResult, req: SplitRequest) -> SplitResponse:
    """SplitResult → SplitResponse。"""
    sentences = [
        SentenceResponse(
            index=s.index,
            text=s.text,
            language=s.language,
            tier=s.tier,
            confidence=s.confidence,
            char_count=s.char_count,
            is_topic_boundary=s.is_topic_boundary,
            topic_depth_score=s.topic_depth_score,
        )
        for s in result.sentences
    ]
    scenes = []
    for sc in result.scenes:
        era = sc.era_info.era if sc.era_info else None
        era_conf = sc.era_info.confidence if sc.era_info else None
        scenes.append(
            SceneResponse(
                segment_id=sc.segment_id,
                text=sc.text,
                estimated_duration=sc.estimated_duration,
                target_words=sc.target_words,
                era=era,
                era_confidence=era_conf,
                subtitle_count=len(sc.subtitles),
            )
        )

    return SplitResponse(
        text_length=len(req.text),
        language=result.language,
        tier_used=result.tier_used,
        total_duration=result.total_duration,
        total_scenes=result.total_scenes,
        sentences=sentences,
        scenes=scenes,
        config_snapshot=result.config_snapshot,
    )


def main():
    """CLI 启动入口。"""
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("splitter.api.rest_api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
