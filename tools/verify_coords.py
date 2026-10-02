# -*- coding: utf-8 -*-
"""장소 표(analysis/tour-places.csv) 전체의 좌표를 한국관광공사 국문 관광정보(KorService2/searchKeyword2)와 대조한다.

    DATA_GO_KR_KEY=<공공데이터포털 인증키> python tools/verify_coords.py                 # 전체 3,109곳
    DATA_GO_KR_KEY=<키> python tools/verify_coords.py --regions 경주 서울 --out analysis/coord_check
    python tools/verify_coords.py --from-json <폴더>                                     # 받아 둔 응답으로(점검용)

장소마다 이름(앞의 도시 이름을 뗀 이름도)으로 관광정보를 검색해 같은 시군구(analysis/place_signgu.json 코드) ·
이름 점수 2 이상인 항목을 고르고(tools/add_popular_places.py의 pick_spot_item), 그 좌표와의 거리를 잰다.
숙박 · 음식은 관광정보에 없는 곳이 많아 못 찾으면 그대로 둔다. 좌표를 바꾸지는 않는다 — 판정표만 쓴다.

산출(--out 폴더, 기본 analysis/coord_check):
  coord_check_<날짜>.csv     장소마다 관광정보 이름 · 좌표 · 거리(m) · 판정(일치 ≤300m · 차이 · 못 찾음)
  coord_fix_<날짜>.csv       거리 300m 초과만: 장소ID, 현재 좌표, 관광정보 좌표, contentid — 눈으로 확인해 반영할 후보
인증키는 환경변수로만 받는다.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.add_popular_places import (  # noqa: E402
    Api, JsonDirApi, PLACES_CSV, SIGNGU_JSON, kto_coords, meters, pick_spot_item, read_places, read_signgu, without_city,
)

OUT_DIR = Path(__file__).resolve().parents[1] / "analysis" / "coord_check"
MATCH_M = 300


def queries(name: str, city: str) -> list[str]:
    out = [name]
    rest = without_city(name, city)
    if rest:
        out.append(rest)
    return out


def check_place(api, place: dict, code: str, log=print) -> dict:
    spot = {"name": place["이름(한국어)"], "signgu": code}
    item = None
    for q in queries(place["이름(한국어)"], place["지역"]):
        try:
            found, _ = api.fetch("KorService2/searchKeyword2", {"numOfRows": "30", "pageNo": "1", "arrange": "A", "keyword": q})
        except Exception as e:  # 한 곳 실패해도 계속
            log(f"{place['id']} {q}: 검색 실패 {e}")
            found = []
        item = pick_spot_item(found, spot)
        if item:
            break
    row = {"장소ID": place["id"], "지역": place["지역"], "범주": place["카테고리"], "이름": place["이름(한국어)"],
           "위도": place["위도"], "경도": place["경도"], "시군구 코드": code,
           "관광정보 이름": "", "관광정보 위도": "", "관광정보 경도": "", "contentid": "", "거리(m)": "", "판정": "못 찾음"}
    coords = kto_coords(item) if item else None
    if not item or not coords:
        return row
    lat, lng = coords
    try:
        d = meters(float(place["위도"]), float(place["경도"]), lat, lng)
    except ValueError:
        return row
    row.update({"관광정보 이름": str(item.get("title", "")).strip(), "관광정보 위도": f"{lat:.5f}", "관광정보 경도": f"{lng:.5f}",
                "contentid": str(item.get("contentid", "")).strip(), "거리(m)": str(int(round(d))),
                "판정": "일치" if d <= MATCH_M else "차이"})
    return row


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--places", type=Path, default=PLACES_CSV)
    ap.add_argument("--signgu", type=Path, default=SIGNGU_JSON)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--regions", nargs="*", help="이 지역만")
    ap.add_argument("--skip-cat", nargs="*", default=[], help="건너뛸 범주(예: stay food)")
    ap.add_argument("--from-json", type=Path, help="받아 둔 응답 JSON 폴더(search_<검색어>.json)")
    a = ap.parse_args(argv)
    if a.from_json:
        api = JsonDirApi(a.from_json)
    else:
        key = os.environ.get("DATA_GO_KR_KEY")
        if not key:
            print("DATA_GO_KR_KEY 환경변수에 공공데이터포털 인증키를 넣어 주세요(또는 --from-json).", file=sys.stderr)
            return 2
        api = Api(key)
    places = read_places(a.places)
    signgu = read_signgu(a.signgu)
    rows = []
    for i, p in enumerate(places, 1):
        if a.regions and p["지역"] not in a.regions:
            continue
        if p["카테고리"] in a.skip_cat:
            continue
        rows.append(check_place(api, p, signgu.get(p["id"], "")))
        if i % 100 == 0:
            print(f"{i:,}/{len(places):,}")
    tag = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y%m%d")
    a.out.mkdir(parents=True, exist_ok=True)
    cols = list(rows[0].keys()) if rows else []
    with open(a.out / f"coord_check_{tag}.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    fix = [r for r in rows if r["판정"] == "차이"]
    with open(a.out / f"coord_fix_{tag}.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(fix)
    n = len(rows)
    print(f"점검 {n:,}곳: 일치 {sum(r['판정'] == '일치' for r in rows):,} · 차이 {len(fix):,} · 못 찾음 {sum(r['판정'] == '못 찾음' for r in rows):,}")
    print(f"판정표 {a.out / f'coord_check_{tag}.csv'}\n수정 후보 {a.out / f'coord_fix_{tag}.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
