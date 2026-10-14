"""Package the existing read-only dashboard for an owner-private Sites Worker.

No engine, API inference, collection or source DB writes. Deployment data is
derived exclusively through ResearchReader and is never committed to GitHub.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from bct.v4.dashboard import ASSETS, ResearchReader


class FrozenReader(ResearchReader):
    def _state(self, db):
        if not hasattr(self, "frozen_state"):
            self.frozen_state = super()._state(db)
        return self.frozen_state

    def _industry_maps(self):
        if not hasattr(self, "frozen_maps"):
            self.frozen_maps = super()._industry_maps()
        return self.frozen_maps


def build(repo, output):
    reader = FrozenReader(repo)
    before = hashlib.sha256(reader.path.read_bytes()).hexdigest()
    dashboard = reader.dashboard()
    generated = datetime.now(timezone.utc).isoformat()
    dashboard["source"].update(snapshot=True, mode="검증된 연구 기록의 고정 스냅샷")
    dashboard["snapshot_generated_at"] = generated
    details = {r["id"]: reader.evidence(r["id"]) for r in dashboard["records"]}
    assert len(details) == dashboard["counts"]["evidence"]
    assert before == hashlib.sha256(reader.path.read_bytes()).hexdigest(), "Source DB changed"
    assets = {"/": (ASSETS / "index.html").read_text(),
              "/app.js": (ASSETS / "app.js").read_text(),
              "/style.css": (ASSETS / "style.css").read_text()}
    assets["/app.js"] = assets["/app.js"].replace(
        "render();notify(data.source.snapshot?", "data.loaded_at=new Date().toISOString();render();notify(data.source.snapshot?")
    assets["/app.js"] = assets["/app.js"].replace(
        "검증된 연구 백업을 보고 있습니다. 현재 수집기의 실시간 상태를 뜻하지 않습니다.",
        "고정 스냅샷 · 데이터 기준 " + "${date(data.data_at)}" + " · 배포 자료 생성 ${date(data.snapshot_generated_at)}. 새로 읽어도 수집·분석은 실행되지 않습니다.")
    # Use a template literal only for the existing snapshot notice.
    assets["/app.js"] = assets["/app.js"].replace('"고정 스냅샷 · 데이터 기준 ', '`고정 스냅샷 · 데이터 기준 ').replace(
        '새로 읽어도 수집·분석은 실행되지 않습니다.":""', '새로 읽어도 수집·분석은 실행되지 않습니다.`:""')
    worker = "const assets=" + json.dumps(assets, ensure_ascii=False) + ";\n"
    worker += "const dashboard=" + json.dumps(dashboard, ensure_ascii=False, allow_nan=False) + ";\n"
    worker += "const details=" + json.dumps(details, ensure_ascii=False, allow_nan=False) + ";\n"
    worker += '''
// All routes are behind the owner-private Sites dispatch authentication boundary.
// No SQLite, raw source archive, secret, collector or inference route is hosted.
const headers = {
  "Cache-Control":"private, no-store",
  "X-Content-Type-Options":"nosniff",
  "Referrer-Policy":"no-referrer",
  "Content-Security-Policy":"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
  "X-Robots-Tag":"noindex, nofollow, noarchive"
};
export default { async fetch(request) {
  const path = new URL(request.url).pathname;
  const method = request.method;
  const respond = (body, type, status=200, extra={}) => new Response(
    method === "HEAD" ? null : body, {status, headers:{...headers,"Content-Type":type,...extra}});
  const json = (data, status=200, extra={}) => respond(JSON.stringify(data), "application/json; charset=utf-8", status, extra);
  if (!["GET","HEAD"].includes(method)) return json({error:"읽기 전용 화면입니다."},405,{Allow:"GET, HEAD"});
  if (path === "/api/dashboard") return json(dashboard);
  if (path === "/api/export") return json(dashboard,200,{"Content-Disposition":'attachment; filename="bct-v4-research.json"'});
  if (path === "/api/health") return json({status:"검증된 고정 연구 자료 연결됨",read_only:true,snapshot:true,data_at:dashboard.data_at});
  if (/^\\/api\\/evidence\\/[a-f0-9]{64}$/.test(path)) {
    const id=path.split("/").pop();
    return Object.hasOwn(details,id) ? json(details[id]) : json({error:"이 근거 기록을 찾을 수 없습니다."},404);
  }
  const asset = path === "/index.html" ? "/" : path;
  if (Object.hasOwn(assets,asset)) return respond(assets[asset],asset === "/" ? "text/html; charset=utf-8" : asset.endsWith(".js") ? "text/javascript; charset=utf-8" : "text/css; charset=utf-8");
  return json({error:"요청한 화면이나 근거를 찾을 수 없습니다."},404);
}};
'''
    (output / "worker").mkdir(parents=True, exist_ok=True)
    (output / "worker/index.js").write_text(worker, encoding="utf-8")
    manifest = {"generated_at": generated, "data_at": dashboard["data_at"],
                "source_db_sha256": before, "counts": dashboard["counts"],
                "detail_count": len(details),
                "verified_detail_count": sum(d["all_references_verified"] for d in details.values()),
                "worker_sha256": hashlib.sha256(worker.encode()).hexdigest(),
                "mode": "OWNER_PRIVATE_FIXED_SNAPSHOT", "AI_calls": 0}
    (output / "snapshot-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, default=Path.cwd())
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    build(a.repo, a.output)
