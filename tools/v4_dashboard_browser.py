"""Actual Chromium UI checks against the local, read-only V4 dashboard.

Uses an already installed Playwright/Chromium; no browser download or API calls.
HTTP failures below are isolated browser test injections, never saved research.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.request import urlopen

from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    parser.add_argument("--output", type=Path, default=Path("docs/v4/dashboard"))
    parser.add_argument("--chromium", default="/usr/bin/chromium")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "screenshots").mkdir(exist_ok=True)
    with urlopen(args.url + "/api/dashboard", timeout=30) as response:
        actual = json.load(response)
    root = Path.cwd()
    protected = [root / "var/v4/cross-industry/ledger/v4.sqlite3", root / "docs/index.html", root / "docs/app.js", root / "docs/style.css", root / "docs/view-model.js"]
    protected += list((root / ".github/workflows").glob("*"))
    hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected if p.is_file()}
    checks, screenshots, errors, requests = [], [], [], []
    def passed(name):
        checks.append({"name": name, "status": "PASS"})
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium, headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 1080}, device_scale_factor=1, locale="ko-KR", accept_downloads=True)
        page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("request", lambda r: requests.append(r.url))
        page.goto(args.url, wait_until="networkidle")
        expect(page.locator("h1")).to_have_text("한눈에 보기")
        assert page.locator(".stat-value").all_text_contents() == ["40건", "110건", "23건", "295건"]
        assert actual["counts"]["evidence"] == 549
        assert "9.73%" in page.locator("#content").inner_text()
        passed("SQLite 집계와 한눈에 보기 수치·부분 판독 표시 일치")

        def navigate(name):
            page.locator("nav").get_by_role("link", name=name, exact=True).click()
            expect(page.locator("h1")).to_have_text(name)
            expect(page.locator('nav a[aria-current="page"]')).to_contain_text(name)
        def screenshot(name):
            path = args.output / "screenshots" / name
            page.screenshot(path=str(path), full_page="detail" not in name)
            screenshots.append(str(path))
        for route, title in [("overview", "한눈에 보기"), ("candidates", "미래 병목 후보"), ("evidence", "판단 근거"), ("automation", "자동화 현황")]:
            navigate(title)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), route
            screenshot(route + "-desktop.png")
        passed("PC 네 화면 이동·현재 메뉴·가로 넘침 없음")

        navigate("한눈에 보기")
        page.get_by_role("link", name="검토 중인 변화 살펴보기").click()
        expect(page.locator("h1")).to_have_text("미래 병목 후보")
        expect(page.locator("#candidates-list tbody tr")).to_have_count(12)
        page.get_by_role("button", name="다음 →", exact=True).click()
        expect(page.locator("#candidates-list tbody tr")).to_have_count(11)
        page.get_by_role("button", name="← 이전", exact=True).click()
        page.locator("#candidates-search").fill("FOX")
        expected_fox = [r for r in actual["records"] if r["category"] == "reviewed" and "fox" in r["product"].lower()]
        expect(page.locator("#candidates-list tbody tr")).to_have_count(len(expected_fox))
        page.locator("#candidates-industry").select_option(label="반도체·광통신·AI 기반시설")
        page.locator("#candidates-role").select_option("DEMAND_INCREASE")
        expect(page.locator("#candidates-list tbody tr")).to_have_count(len(expected_fox))
        page.locator("#candidates-search").fill("검색 결과가 없는 입력")
        expect(page.get_by_text("조건에 맞는 기록이 없습니다", exact=True)).to_be_visible()
        page.get_by_role("button", name="초기화", exact=True).click()
        expect(page.locator("#candidates-list tbody tr")).to_have_count(12)
        page.get_by_role("tab", name=re.compile("미래 병목 후보")).click()
        expect(page.get_by_text("저장된 평가 범위의 미래 병목 후보 0건", exact=True)).to_be_visible()
        page.get_by_role("button", name="검토 중인 변화 보기", exact=True).click()
        passed("후보·변화 탭, 검색, 산업·역할 필터, 초기화, 빈 결과, 이전·다음 페이지")

        page.locator("#candidates-search").fill("FOX-XP TM")
        page.locator("button[data-evidence]").first.click()
        expect(page.locator("#detail-title")).to_contain_text("FOX-XP", timeout=30000)
        expect(page.get_by_text("저장된 원문·해시·위치 일치", exact=True).first).to_be_visible()
        assert "$1.4 million" in page.locator("#detail-body").inner_text()
        page.get_by_text("인용 앞뒤 문맥 보기", exact=True).first.click()
        page.get_by_text("원문 식별 정보 보기", exact=True).first.click()
        screenshot("evidence-detail-desktop.png")
        # Test the browser's new-tab destination without recollecting originals.
        outbound = []
        ctx.route("https://**", lambda route: (outbound.append(route.request.url), route.abort()))
        with page.expect_popup() as opened:
            page.get_by_role("link", name="원문 사이트 열기 ↗", exact=True).first.click()
        popup = opened.value
        page.wait_for_timeout(100)
        assert outbound and outbound[-1].startswith("https://www.aehr.com/")
        popup.close()
        ctx.unroute("https://**")
        page.get_by_role("button", name="상세 닫기", exact=True).click()
        expect(page.locator("dialog")).not_to_be_visible()
        page.locator("button[data-evidence]").first.click()
        expect(page.locator("#detail-title")).to_be_visible()
        page.keyboard.press("Escape")
        expect(page.locator("dialog")).not_to_be_visible()
        passed("실제 FOX-XP 인용·위치·앞뒤 문맥·해시 표시와 상세 닫기·Esc")
        passed("원문 링크 새 탭·실제 저장 URL 목적지 일치 (외부 응답 재수집 안 함)")

        navigate("판단 근거")
        page.locator("#evidence-category").select_option("discovery")
        page.locator("button[data-evidence]").first.click()
        expect(page.get_by_text("제품명과 역할은 CPU가 제안한 값입니다. 수요·공급 사실로 채택하지 않은 탐색 기록입니다.", exact=True)).to_be_visible(timeout=30000)
        page.get_by_role("button", name="상세 닫기").click()
        page.locator("#evidence-category").select_option("structured")
        page.locator("button[data-evidence]").first.click()
        expect(page.get_by_text("보존된 공식 표의 행·셀·해시 일치", exact=True).first).to_be_visible(timeout=90000)
        expect(page.locator("#detail-body .reference-box")).to_have_count(2)
        assert "2026-06" in page.locator("#detail-body").inner_text()
        assert "2026-07" in page.locator("#detail-body").inner_text()
        screenshot("structured-detail-desktop.png")
        page.get_by_role("button", name="상세 닫기").click()
        page.locator("#evidence-category").select_option("reviewed")
        page.locator("#evidence-search").fill("h160")
        assert page.locator(".evidence-card").count() >= 1
        page.get_by_role("button", name="초기화", exact=True).click()
        page.get_by_role("button", name="다음 →", exact=True).click()
        expect(page.locator(".pagination")).to_contain_text("2 / 46")
        page.get_by_role("button", name="← 이전", exact=True).click()
        with page.expect_download() as dl:
            page.get_by_role("link", name="연구 자료 내려받기 ↓", exact=True).click()
        download = dl.value
        payload = json.loads(Path(download.path()).read_text())
        assert payload["counts"] == actual["counts"]
        assert len(payload["records"]) == 549
        passed("근거 목록·상태 필터·미채택 안내·공식 표 두 시점 대조·전체 자료 다운로드")

        navigate("자동화 현황")
        expect(page.get_by_text("자동 판독 중단", exact=True)).to_be_visible()
        expect(page.get_by_text("HTTP 400 오류 1건", exact=True)).to_be_visible()
        expect(page.get_by_text("원문 검증 거부 항목 8개", exact=True)).to_be_visible()
        assert page.locator(".error-row").count() == 4
        page.get_by_role("button", name="오류 12건 모두 보기", exact=True).click()
        expect(page.locator(".error-row")).to_have_count(12)
        page.get_by_role("button", name="오류 접기", exact=True).click()
        expect(page.locator(".error-row")).to_have_count(4)
        expect(page.locator(".run-row")).to_have_count(5)  # Three AI trials + two collections.
        passed("자동화 설정·수동 실행 두 건·오류 목록 펼치기와 접기")

        page.get_by_role("button", name="기록 새로 읽기").click()
        expect(page.locator("#notice")).to_contain_text("새 수집은 실행하지 않았습니다", timeout=30000)
        old_data_at = actual["data_at"]
        with urlopen(args.url + "/api/dashboard", timeout=30) as r:
            assert json.load(r)["data_at"] == old_data_at
        page.route("**/api/dashboard", lambda route: route.fulfill(status=503, content_type="application/json", body=json.dumps({"error":"시험용 연결 중단"})))
        page.get_by_role("button", name="기록 새로 읽기").click()
        expect(page.locator("#notice")).to_contain_text("마지막으로 읽은 자료를 표시", timeout=30000)
        assert page.locator(".run-row").count() == 5
        page.unroute("**/api/dashboard")
        page.get_by_role("button", name="기록 새로 읽기").click()
        expect(page.locator("#notice")).to_contain_text("새 수집은 실행하지 않았습니다", timeout=30000)
        passed("새로 읽기·실패 시 기존 자료 표시·연결 복구 (503은 시험 주입)")
        fresh = ctx.new_page()
        fresh.route("**/api/dashboard", lambda route: route.fulfill(status=503, content_type="application/json", body=json.dumps({"error":"시험용 첫 연결 실패"})))
        fresh.goto(args.url, wait_until="networkidle")
        expect(fresh.get_by_role("heading", name="연구 자료를 읽지 못했습니다")).to_be_visible()
        fresh.unroute("**/api/dashboard")
        fresh.get_by_role("button", name="다시 읽기", exact=True).click()
        expect(fresh.locator("h1")).to_have_text("한눈에 보기", timeout=30000)
        fresh.close()
        passed("첫 연결 실패·다시 읽기 복구 (실패는 시험 주입, 가짜 정상 데이터 없음)")

        page.set_viewport_size({"width":390,"height":844})
        for route, title in [("overview","한눈에 보기"),("candidates","미래 병목 후보"),("evidence","판단 근거"),("automation","자동화 현황")]:
            navigate(title)
            if route=="candidates":
                page.get_by_role("button",name="초기화",exact=True).click()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), route
            screenshot(route + "-mobile.png")
        navigate("미래 병목 후보")
        page.locator("#candidates-search").fill("H160")
        page.locator("button[data-evidence]").first.click()
        expect(page.locator("#detail-title")).to_contain_text("H160", timeout=30000)
        assert page.locator("dialog").evaluate("n=>n.scrollWidth<=n.clientWidth")
        screenshot("evidence-detail-mobile.png")
        page.get_by_role("button",name="상세 닫기").click()
        page.set_viewport_size({"width":320,"height":720})
        for title in ["한눈에 보기","미래 병목 후보","판단 근거","자동화 현황"]:
            navigate(title)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), title
        passed("390px 휴대폰 네 화면·검색·상세, 320px 네 화면 가로 넘침 없음")
        assert not errors, errors
        assert not any("api.groq.com" in u for u in requests)
        passed("브라우저 실행 오류 0건 · 화면 동작 중 Groq 요청 0회")
        browser.close()
    after = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected if p.is_file()}
    assert hashes == after
    passed("브라우저 검증 전후 연구 SQLite·기존 운영 UI·Actions 파일 해시 불변")
    result = {"at":datetime.now(timezone.utc).isoformat(),"browser":"Chromium via Playwright", "url_scope":"Local loopback only; no production deployment", "viewports":[[1440,1080],[390,844],[320,720]], "checks":checks, "passed":len(checks),"failed":0,"page_errors":errors,"source_data_at":actual["data_at"],"source_counts":actual["counts"],"screenshots":screenshots,"protected_hashes":hashes,"new_Groq_calls":0,"external_site_response":"NOT_RECOLLECTED; browser destination and popup tested","performance_or_prediction_validation":"NOT_RUN","failure_test_note":"503 responses injected only in the browser; never research data"}
    (args.output / "BROWSER_RESULTS.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"passed":len(checks),"screenshots":len(screenshots),"page_errors":errors},ensure_ascii=False))


if __name__ == "__main__":
    main()
