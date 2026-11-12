"""Public 16-inch laptop view: large readable CSS, account-free, mobile preserved."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "src/bct/v4/dashboard_web/index.html"
CSS = ROOT / "src/bct/v4/dashboard_web/style.css"

def test_account_free_reader_toggle_and_original_navigation():
    html = HTML.read_text(encoding="utf-8")
    assert 'lang="ko"' in html
    assert 'id="bct-large-text" type="checkbox"' in html
    assert 'for="bct-large-text"' in html
    assert "글씨 더 크게" in html
    assert "로그인 없는 공개 읽기 전용" in html
    for route in ("overview", "evidence", "automation", "candidates"):
        assert f'data-nav="{route}"' in html
    assert "accounts.google" not in html and "login" not in html.lower()
    assert "https://fonts." not in html

def test_16_inch_responsive_readability_and_mobile_unchanged():
    css = CSS.read_text(encoding="utf-8")
    assert "16-inch laptop readability, 2026-11-12" in css
    assert "@media (min-width:741px)" in css
    assert "@media (min-width:741px) and (max-width:1500px)" in css
    assert "@media (min-width:741px) and (max-width:1350px)" in css
    assert "body:has(#bct-large-text:checked)" in css
    for class_name in (
        ".bct-rank-columns", ".bct-rank-table", ".bct-sector-name",
        ".bct-evidence-open", ".bct-process-note", ".bct-metric-label",
        ".research-table", ".bct-refresh", "#detail",
    ):
        assert class_name in css
    assert "Mobile: preserve the approved desktop table" in css
    assert ".bct-first-app .bct-reader-toggle{display:none}" in css
    assert "grid-template-columns:minmax(0,1fr)" in css
    assert "min-height:46px" in css
