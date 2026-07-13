"""SSE streaming endpoint tests for POST /v1/split/stream."""
import pytest
from fastapi.testclient import TestClient

from splitter.api.rest_api import app


@pytest.fixture
def client():
    return TestClient(app)


def _parse_sse(text: str):
    """Parse SSE text into list of (event, data) tuples."""
    events = []
    current_event = "message"
    current_data = []
    for line in text.strip().split("\n"):
        if line.startswith("event: "):
            current_event = line[7:]
        elif line.startswith("data: "):
            current_data.append(line[6:])
        elif line == "" and current_data:
            events.append((current_event, "\n".join(current_data)))
            current_event = "message"
            current_data = []
    if current_data:
        events.append((current_event, "\n".join(current_data)))
    return events


class TestSplitStream:
    """POST /v1/split/stream — SSE streaming."""

    def test_stream_simple_text(self, client):
        """Normal text returns a single result event."""
        resp = client.post(
            "/v1/split/stream",
            json={"text": "今天天气真好。明天会下雨。"},
            headers={"Accept": "text/event-stream"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("text/event-stream")

        events = _parse_sse(resp.text)
        assert len(events) >= 1

        # Last event should be 'result'
        last_event, last_data = events[-1]
        assert last_event == "result", f"Expected result event, got {last_event}"

        import json
        data = json.loads(last_data)
        assert data["text_length"] > 0
        assert len(data["sentences"]) == 2
        assert data["language"] in ("zh", "mixed")

    def test_stream_large_text_progress_events(self, client):
        """Large text should emit progress events before result."""
        text = "".join(f"句子{i:03d}。" for i in range(300))
        resp = client.post(
            "/v1/split/stream",
            json={"text": text, "language": "zh", "config": {"max_input_length": 200}},
            headers={"Accept": "text/event-stream"},
        )
        assert resp.status_code == 200

        events = _parse_sse(resp.text)
        assert len(events) >= 2

        # Should have at least one progress event
        progress_events = [e for e in events if e[0] == "progress"]
        assert len(progress_events) >= 1

        # Last event should be result
        last_event, last_data = events[-1]
        assert last_event == "result"

        import json
        data = json.loads(last_data)
        assert len(data["sentences"]) > 200
        assert data["text_length"] > 0

    def test_stream_english_text(self, client):
        """English text works with streaming."""
        resp = client.post(
            "/v1/split/stream",
            json={"text": "Hello world. This is a test. How are you?"},
            headers={"Accept": "text/event-stream"},
        )
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        last_event, last_data = events[-1]
        assert last_event == "result"

        import json
        data = json.loads(last_data)
        assert len(data["sentences"]) >= 2

    def test_stream_empty_text(self, client):
        """Empty text should return 422."""
        resp = client.post(
            "/v1/split/stream",
            json={"text": ""},
            headers={"Accept": "text/event-stream"},
        )
        assert resp.status_code == 422

    def test_stream_mode_precise(self, client):
        """Mode parameter should be respected."""
        resp = client.post(
            "/v1/split/stream",
            json={"text": "测试文本。分句处理。", "mode": "precise"},
            headers={"Accept": "text/event-stream"},
        )
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        last_event, last_data = events[-1]
        assert last_event == "result"

        import json
        data = json.loads(last_data)
        assert len(data["sentences"]) >= 2

    def test_stream_very_large_text(self, client):
        """Very large text should complete without error."""
        sentences = [f"这是第{i}个句子用于测试流式分句功能。" for i in range(500)]
        text = "".join(sentences)
        resp = client.post(
            "/v1/split/stream",
            json={"text": text, "language": "zh", "config": {"max_input_length": 2000}},
            headers={"Accept": "text/event-stream"},
        )
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        last_event, last_data = events[-1]
        assert last_event == "result"

        import json
        data = json.loads(last_data)
        assert len(data["sentences"]) >= 400
