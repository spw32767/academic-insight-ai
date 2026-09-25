from academic_insight_ai.models.providers.ollama import OllamaProvider
from academic_insight_ai.models.types import GenerateRequest


def test_structured_format_is_sent_only_when_requested(monkeypatch):
    sent = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": "{}"}

    def fake_post(url, json, timeout):
        sent.append(json)
        return Response()

    monkeypatch.setattr("academic_insight_ai.models.providers.ollama.requests.post", fake_post)
    provider = OllamaProvider("http://ollama.test")
    schema = {"type": "object", "properties": {}}
    provider.generate(GenerateRequest("model", "prompt", json_schema=schema))
    provider.generate(GenerateRequest("model", "prompt", json_mode=True))
    assert sent[0]["format"] == schema
    assert sent[1]["format"] == "json"
