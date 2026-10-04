# -*- coding: utf-8 -*-
"""사람이 좌표를 적은 장소 표(CSV)를 analysis/tour-places.csv에 새 장소로 추가한다(인증키 · 네트워크 없이).

    python -m tools.add_manual_places                       # 후보 판정만 찍는다(파일은 바꾸지 않는다)
    python -m tools.add_manual_places --apply               # 새 장소를 tour-places.csv 끝에 붙이고 place_signgu.json에 시군구 코드를 넣는다
    python -m tools.add_manual_places --csv <표.csv> --apply

입력 표(기본 analysis/citytour_manual_places.csv, 앱 frontend scripts/data/citytour-manual-places.csv와 같은 파일)의 열:
    region(지역) · stopName(시티투어 노선 표기) · tours(노선 수) · ko · en · cat · lat · lng · signgu(법정동 시군구 코드) · muni(시군구 이름) · desc · descEn\n    · nearOk(1이면 기존 장소 250m 안이어도 다른 곳으로 보고 넣는다. 사람이 확인한 이웃 장소)\n    · coord(좌표 근거. 비면 「좌표 수기 입력(지도 검증 필요, 날짜)」, 지오코딩한 표는 「카카오 로컬 좌표 …」)\n    · source(출처 앞 문구. 비면 「시티투어 경유지(n개 노선, 노선 표기 「…」)」. 연관 관광지 표 analysis/related_manual_places.csv는 「한국관광공사 연관 관광지(… 언급)」)

규칙은 앱 frontend scripts/add-manual-places.mjs와 같다(두 저장소의 장소 표가 같게 늘어난다).
  1. id는 ctm<sha1("지역|이름") 앞 8자리>: 같은 지역 · 같은 이름이면 다시 돌려도 같은 id라 두 번 들어가지 않는다.
  2. 기존 장소와 250m 안이거나, 1km 안에서 이름 글자쌍이 절반 넘게 겹치면(add_popular_places.match_by_location) 이미 있는 장소다.
  3. 권역은 그 지역 행에 가장 많은 값(없으면 전국), 추천 체류는 범주의 기존 중앙값(없으면 60), English는 표의 en,
     출처는 「시티투어 경유지(n개 노선, 노선 표기 「…」) · 좌표 수기 입력(지도 검증 필요, 날짜)」. 좌표는 관광정보가 아니라 사람이 적은 값이니
     뒤에 tools/verify_coords.py로 관광정보 좌표와 대조하는 것이 좋다.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from pathlib import Path

from tools.clean_place_sources import clean_source
from tools.add_popular_places import (
    COLUMNS,
    PLACES_CSV,
    SIGNGU_JSON,
    append_rows,
    match_by_location,
    read_places,
    read_signgu,
    region_macro,
    stay_medians,
    write_signgu,
)

ROOT = Path(__file__).resolve().parents[1]
MANUAL_CSV = ROOT / "analysis" / "citytour_manual_places.csv"
DATE = "2026-10-03"
ID_PREFIX = "ctm"


def manual_id(region: str, ko: str) -> str:
    """앱 scripts/add-manual-places.mjs manualId와 같다"""
    return ID_PREFIX + hashlib.sha1(f"{region}|{ko}".encode("utf-8")).hexdigest()[:8]


def read_manual(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def manual_rows(rows: list[dict], places: list[dict], date: str = DATE) -> tuple[list[dict], list[dict]]:
    """표 행 → (새 장소 행, 판정표). 기존 장소와 겹치는 행은 판정표에만 남는다(순수 함수)"""
    stays = stay_medians(places)
    ids = {p["id"] for p in places}
    pool = list(places)
    new_rows: list[dict] = []
    verdicts: list[dict] = []
    for r in rows:
        region = (r.get("region") or "").strip()
        ko = (r.get("ko") or "").strip()
        verdict = {"지역": region, "노선 표기": (r.get("stopName") or "").strip(), "이름": ko, "판정": "", "장소 id": "", "장소 이름": ""}
        try:
            lat, lng = float(r["lat"]), float(r["lng"])
        except (KeyError, TypeError, ValueError):
            verdict["판정"] = "빈 이름 · 지역 · 좌표"
            verdicts.append(verdict)
            continue
        if not region or not ko:
            verdict["판정"] = "빈 이름 · 지역 · 좌표"
            verdicts.append(verdict)
            continue
        pid = manual_id(region, ko)
        if pid in ids:
            verdict.update(판정="기존(id)", **{"장소 id": pid})
            verdicts.append(verdict)
            continue
        near = None if (r.get("nearOk") or "").strip() == "1" else match_by_location(ko, lat, lng, pool)
        if near:
            verdict.update(판정="기존(위치)", **{"장소 id": near["id"], "장소 이름": near["이름(한국어)"]})
            verdicts.append(verdict)
            continue
        cat = (r.get("cat") or "heal").strip()
        tours = int(r.get("tours") or 1)
        stop = verdict["노선 표기"] or ko
        new = {c: "" for c in COLUMNS}
        new.update({
            "id": pid, "권역": region_macro(places, region), "지역": region,
            "이름(한국어)": ko, "English": (r.get("en") or "").strip() or ko,
            "카테고리": cat, "위도": f"{lat:.5f}", "경도": f"{lng:.5f}",
            "추천 체류(분)": str(stays.get(cat, 60)),
            # 출처 칸에는 작업 기록(날짜 · 사용자 요청 · 검증 메모)을 남기지 않는다(tools/clean_place_sources.py)
            "출처": clean_source(f"{(r.get('source') or '').strip() or f'시티투어 경유지({tours}개 노선, 노선 표기 「{stop}」)'} · {(r.get('coord') or '').strip() or f'좌표 수기 입력(지도 검증 필요, {date})'}"),
            "설명": (r.get("desc") or "").strip() or f"{region} 시티투어 경유지({tours}개 노선)",
        })
        new_rows.append(new)
        pool.append(new)
        ids.add(pid)
        verdict.update(판정="신규", **{"장소 id": pid, "장소 이름": ko})
        verdicts.append(verdict)
    return new_rows, verdicts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", type=Path, default=MANUAL_CSV, help="사람이 좌표를 적은 장소 표")
    ap.add_argument("--places", type=Path, default=PLACES_CSV)
    ap.add_argument("--signgu", type=Path, default=SIGNGU_JSON, help="장소 id → 시군구 코드 JSON")
    ap.add_argument("--apply", action="store_true", help="새 장소를 tour-places.csv 끝에 붙인다")
    args = ap.parse_args(argv)

    places = read_places(args.places)
    rows = read_manual(args.csv)
    new_rows, verdicts = manual_rows(rows, places)
    counts: dict[str, int] = {}
    for v in verdicts:
        counts[v["판정"]] = counts.get(v["판정"], 0) + 1
        if v["판정"] != "신규":
            print(f"  - {v['지역']} {v['이름']}: {v['판정']} {v['장소 id']} {v['장소 이름']}".rstrip())
    for n in new_rows:
        print(f"  + {n['id']} {n['이름(한국어)']} ({n['지역']} · {n['카테고리']})")
    print(f"표 {len(rows)}행 · {counts} · 장소 {len(places)} → {len(places) + len(new_rows)}곳")
    if not args.apply or not new_rows:
        print("--apply 없음: 파일은 그대로" if not args.apply else "새 장소가 없어 파일은 그대로")
        return 0
    append_rows(args.places, new_rows)
    codes = read_signgu(args.signgu)
    by_key = {(r.get("region") or "").strip() + "|" + (r.get("ko") or "").strip(): (r.get("signgu") or "").strip() for r in rows}
    for n in new_rows:
        code = by_key.get(n["지역"] + "|" + n["이름(한국어)"], "")
        codes[n["id"]] = code if re.fullmatch(r"\d{5}", code) else ""
    write_signgu(args.signgu, codes)
    print(f"붙였다: {args.places} · {args.signgu}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
