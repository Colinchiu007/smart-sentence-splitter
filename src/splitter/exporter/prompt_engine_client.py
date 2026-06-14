"""PromptEngineClient — PROJECT-011 HTTP 桥接客户端 (v0.8 新增).

封装 PROJECT-011 REST API:
- POST /v1/optimize — 单条优化
- POST /v1/optimize/batch — 批量优化
- GET /health — 健康检查

无网络依赖 (`requests` 是 optional); 不传 client 时可纯本地用 exporter。
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional


class PromptEngineClient:
    """PROJECT-011 (prompt-engine) HTTP 客户端。

    Args:
        base_url: PROJECT-011 服务地址 (默认 http://localhost:8013)
        timeout: HTTP 超时 (秒)
        api_key: 可选, 用于鉴权 (PROJECT-011 暂时不需要)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8013",
        timeout: float = 60.0,
        api_key: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key
        self._session = None

    def _get_session(self):
        """懒加载 requests session。"""
        if self._session is None:
            try:
                import requests
                self._session = requests.Session()
            except ImportError:
                raise ImportError(
                    "requests not installed. Run: pip install requests"
                )
        return self._session

    def health_check(self) -> bool:
        """检查 PROJECT-011 服务是否在线。"""
        try:
            s = self._get_session()
            r = s.get(f"{self.base_url}/health", timeout=5)
            return r.status_code == 200 and r.json().get("status") == "ok"
        except Exception:
            return False

    def optimize(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """调用 POST /v1/optimize 优化单条提示词。"""
        s = self._get_session()
        payload = self.build_optimize_payload(request)
        r = s.post(
            f"{self.base_url}/v1/optimize",
            json=payload,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return self.parse_optimize_response(r.json())

    def optimize_batch(self, requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量优化。"""
        s = self._get_session()
        payload = [self.build_optimize_payload(r) for r in requests]
        r = s.post(
            f"{self.base_url}/v1/optimize/batch",
            json=payload,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return [self.parse_optimize_response(item) for item in r.json()]

    def build_optimize_payload(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """构造 PROJECT-011 /v1/optimize 请求体。

        将 PROJECT-012 内部格式转换为 PROJECT-011 OptimizeRequest 格式。
        """
        # 透传所有字段, 补充 PROJECT-011 要求的必需字段
        payload = dict(request)
        # num_candidates 缺省 1
        payload.setdefault("num_candidates", 1)
        # auto_detect_style 缺省 True
        payload.setdefault("auto_detect_style", True)
        return payload

    def parse_optimize_response(self, resp: Dict[str, Any]) -> Dict[str, Any]:
        """解析 PROJECT-011 /v1/optimize 响应。"""
        return {
            "optimized_prompt": resp.get("optimized_prompt", ""),
            "platform": resp.get("platform", ""),
            "style": resp.get("style"),
            "model_used": resp.get("model_used", ""),
            "tokens_used": resp.get("tokens_used", 0),
            "duration_ms": resp.get("duration_ms", 0.0),
            "candidates": resp.get("candidates", []),
            "error": resp.get("error"),
            "raw": resp,
        }