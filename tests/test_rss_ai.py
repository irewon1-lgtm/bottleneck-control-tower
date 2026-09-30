import json

from sqlalchemy import select

from bct.models import RadarItem
from bct.rss_ai import RSSAIReview, openai_review, run


def test_signal_only_idempotent_error_and_versioned_retry(setup, tmp_path):
    settings, sf = setup
    feeds = tmp_path / "feeds.yaml"
    feeds.write_text("feeds:\n  news: https://news.example.org/feed\n")
    with sf.begin() as db:
        for id_, title, host in (
            ("one", "Transformer lead time remains elevated", "news.example.org"),
            ("two", "If diesel shortage occurs, ports may slow", "news.example.org"),
            ("three", "Factory opens today", "news.example.org"),
            ("four", "Steel shortage", "other.example.org"),
        ):
            db.add(RadarItem(id=id_, source=host, external_id=id_, title=title,
                url=f"https://{host}/{id_}", source_type="NEWS"))
    seen = []
    def reviewer(payload, *, model):
        seen.append(payload)
        if payload["title"].startswith("If"):
            raise RuntimeError("model unavailable")
        return {"TARGET_TYPE": "COMPONENT", "TARGET_NAME": "transformer",
            "SCOPE": "UNRESOLVED", "FACT_STATUS": "CURRENT_FACT",
            "SIGNAL_DIRECTION": "PRESSURE", "SIGNAL_TYPE": "LEAD_TIME",
            "UPSTREAM_SOURCE": "UNRESOLVED", "EVIDENCE_NOTE": "Lead time remains elevated."}
    first = run(settings, feeds, model="test-model", reviewer=reviewer)
    assert (first["processed"], first["success"], first["error"], len(seen)) == (2, 1, 1, 3)
    assert set(seen[0]) == {"title", "snippet", "signals"}
    assert run(settings, feeds, model="test-model", reviewer=reviewer)["processed"] == 0
    with sf() as db:
        rows = db.scalars(select(RSSAIReview)).all()
        assert {r.radar_item_id: (r.status, r.attempts) for r in rows} == {
            "one": ("OK", 1), "two": ("ERROR", 2)}
        assert json.loads(next(r.result_json for r in rows if r.status == "OK"))["TARGET_NAME"] == "transformer"
        assert db.get(RadarItem, "two").status == "active"
    changed = run(settings, feeds, model="test-model", prompt_version="v2", limit=1,
        reviewer=reviewer)
    assert changed["processed"] == 1
    assert changed["success"] == 1


def test_invalid_output_retries_then_terminal_error(setup, tmp_path):
    settings, sf = setup
    feeds = tmp_path / "feeds.yaml"
    feeds.write_text("feeds:\n  news: https://news.example.org/feed\n")
    with sf.begin() as db:
        db.add(RadarItem(id="one", source="news.example.org", external_id="one",
                         title="Steel shortage", url="https://news.example.org/one", source_type="NEWS"))
    calls = []
    def bad(payload, *, model):
        calls.append(payload)
        return {"PROMOTE": True}
    result = run(settings, feeds, model="test-model", reviewer=bad)
    assert (result["processed"], result["error"], len(calls)) == (1, 1, 2)
    assert run(settings, feeds, model="test-model", reviewer=bad)["processed"] == 0


def test_provider_sends_only_allowed_input_and_parses_structured_output(monkeypatch):
    result = {"TARGET_TYPE": "UNRESOLVED", "TARGET_NAME": "UNRESOLVED",
              "SCOPE": "UNRESOLVED", "FACT_STATUS": "CONDITIONAL",
              "SIGNAL_DIRECTION": "NEUTRAL", "SIGNAL_TYPE": "OTHER",
              "UPSTREAM_SOURCE": "UNRESOLVED", "EVIDENCE_NOTE": "The stated claim is conditional."}
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, *args):
            return json.dumps({"status": "completed", "output": [
                {"type": "message", "content": [{"type": "output_text", "text": json.dumps(result)}]}]}).encode()
    def fake_urlopen(request, timeout):
        body = json.loads(request.data)
        assert body["store"] is False and "tools" not in body
        assert set(json.loads(body["input"])) == {"title", "snippet", "signals"}
        assert body["text"]["format"]["strict"] is True
        return Response()
    monkeypatch.setattr("bct.rss_ai.urlopen", fake_urlopen)
    assert openai_review({"title": "If steel shortage", "snippet": None,
                          "signals": [{"signal": "SHORTAGE", "candidate_term": "steel"}]},
                         model="test-model", api_key="test-key") == result
