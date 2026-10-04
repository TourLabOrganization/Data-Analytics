"""장소 표의 도시 · 좌표 수정과 유네스코 표시를 표대로 맞춘다(앱 frontend scripts/apply-place-fixes.mjs · apply-badge-lists.mjs의 un과 같은 규칙).

    python -m tools.apply_place_fixes            # 바뀔 행 수만 찍는다
    python -m tools.apply_place_fixes --apply    # analysis/tour-places.csv를 고친다

  analysis/place_fixes.csv  열: id · city(새 지역, 비면 그대로) · lat · lng(새 좌표, 비면 그대로) · reason
  analysis/unesco_list.csv  열: site · year · placeIds(공백으로 여럿) · names — 한국의 유네스코 세계유산 17건과 구성요소 장소.
                            표에 든 장소만 「유네스코」 칸이 Y, 나머지는 빈칸
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACES = ROOT / "analysis" / "tour-places.csv"
FIXES = ROOT / "analysis" / "place_fixes.csv"
UNESCO = ROOT / "analysis" / "unesco_list.csv"


def read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def apply(rows: list[dict], fixes: list[dict], unesco: set[str]) -> int:
    by_id = {r["id"]: r for r in rows}
    missing = [f["id"] for f in fixes if f["id"] not in by_id] + sorted(i for i in unesco if i not in by_id)
    if missing:
        raise SystemExit(f"장소 표에 없는 id: {', '.join(missing)}")
    changed = 0
    for f in fixes:
        r = by_id[f["id"]]
        before = dict(r)
        if f.get("city", "").strip():
            r["지역"] = f["city"].strip()
        if f.get("lat", "").strip() and f.get("lng", "").strip():
            r["위도"], r["경도"] = f"{float(f['lat']):.5f}", f"{float(f['lng']):.5f}"
        changed += r != before
    for r in rows:
        flag = "Y" if r["id"] in unesco else ""
        if r["유네스코"] != flag:
            r["유네스코"] = flag
            changed += 1
    return changed


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    rows = read(PLACES)
    cols = list(rows[0].keys())
    unesco = {i for r in read(UNESCO) for i in r["placeIds"].split()}
    n = apply(rows, read(FIXES), unesco)
    print(f"수정 {n}건 · 유네스코 {len(unesco)}곳")
    if a.apply:
        with PLACES.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"썼다: {PLACES}")


if __name__ == "__main__":
    main()
