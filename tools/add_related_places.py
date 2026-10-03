# -*- coding: utf-8 -*-
"""한국관광공사 관광지별 연관 관광지(TarRlteTarService1)를 전수 재조사해 장소 표에 없는 「함께 많이 가는 관광지」를 analysis/tour-places.csv에 더한다.

    DATA_GO_KR_KEY=<공공데이터포털 인증키> python -m tools.add_related_places                 # 후보만 만든다(파일은 바꾸지 않는다)
    DATA_GO_KR_KEY=<키> python -m tools.add_related_places --apply                         # 새 장소를 tour-places.csv 끝에 붙인다
    DATA_GO_KR_KEY=<키> python -m tools.add_related_places --regions 경주 부산               # 이 지역의 시군구만
    python -m tools.add_related_places --from-json <폴더> --apply                           # 받아 둔 응답 JSON으로(네트워크 없이)

규칙(앱 frontend src/lib/tour-collect.ts collectRelated와 같다):
  1. 장소(숙박 제외)가 있는 시군구 전부(analysis/place_signgu.json, add_popular_places.targets_all)마다 시군구 전체 연관 관광지 목록
     (TarRlteTarService1/areaBasedList1, 기준월 2개월 전 → 비면 3 · 4개월 전, 쪽당 2,000행 · 최대 5쪽)을 받는다.
  2. 연관 관광지(rlteTatsNm)를 시군구 코드(rlteSignguCd) · 정규화 이름으로 모아 연계 수(행 수) · 가장 좋은 순위 · 기준 관광지(tAtsNm) 몇 곳을 센다.
     주차장 · 화장실 · 전국 체인 브랜드(앱 lib/franchise-brands.ts와 같은 목록)는 뺀다. 숙박(대분류 「숙박」)은 stay 분류로 둔다.
  3. 지역은 그 시군구 코드가 든 조회 대상 지역. 같은 지역 장소와 이름 점수 2 이상이면 기존 장소.
  4. 아니면 국문 관광정보 KorService2/searchKeyword2에서 같은 시군구 코드의 항목을 찾아 좌표 · 분류 · 주소를 얻고, 250m 안(1km 안 이름 겹침) 기존 장소면 기존.
     관광정보에 없으면 좌표를 몰라 「못 찾음」(후보 표에만 남긴다). 지역을 모르는 코드는 관광정보 좌표에서 30km 안 가장 가까운 장소의 지역.
  5. 새 장소 id는 pop<contentid>(인기 · 오디 · 시티투어 도구와 같은 id), 추천 체류는 범주의 기존 중앙값, 출처에 「연관 관광지(연계 n회 · 기준 관광지)」와 contentid.
  6. --apply 때 새 장소의 시군구 코드를 analysis/place_signgu.json에 넣는다.

산출(--out 폴더, 기본 analysis/related_added): related_candidates_<날짜>.csv(연관 관광지마다 판정) · related_new_rows_<날짜>.csv(붙일 행).
붙인 뒤에는 분석을 다시 돌려야 군집 · 코스 연결에 반영된다. 인증키는 환경변수 DATA_GO_KR_KEY로만 받는다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.add_popular_places import (  # noqa: E402
    Api, COLUMNS, JsonDirApi, PLACES_CSV, SIGNGU_JSON, append_rows, known_contentids, kto_category, kto_coords, match_by_location,
    match_by_name, meters, name_score, read_places, read_signgu, region_macro, stay_medians, targets_all, write_csv, write_signgu,
)

OUT_DIR = Path(__file__).resolve().parents[1] / "analysis" / "related_added"
POP_PREFIX = "pop"
ROWS, MAX_PAGES = 2000, 5
NEAREST_M = 30_000

# 앱 lib/franchise-brands.ts와 같은 목록
FRANCHISE_BRANDS = [
    "맥도날드", "버거킹", "롯데리아", "KFC", "맘스터치", "서브웨이", "도미노피자", "피자헛", "파파존스",
    "스타벅스", "투썸플레이스", "이디야", "할리스", "엔제리너스", "커피빈", "폴바셋", "빽다방", "메가MGC커피", "메가커피", "컴포즈커피",
    "파스쿠찌", "탐앤탐스", "공차", "배스킨라빈스", "던킨", "파리바게뜨", "뚜레쥬르", "설빙",
    "CGV", "롯데시네마", "메가박스",
    "GS25", "CU", "세븐일레븐", "이마트24", "이마트", "홈플러스", "롯데마트", "코스트코", "다이소", "올리브영",
]
_BRANDS = [b.replace(" ", "").lower() for b in FRANCHISE_BRANDS]


def is_franchise(name: str) -> bool:
    """앱 isFranchiseName: 「/」 앞부분(공백 제거, 소문자)이 브랜드로 시작. 영문 브랜드 바로 뒤가 영문자면 다른 이름(CU ≠ CUBE)"""
    head = name.split("/")[0].replace(" ", "").lower()
    for b in _BRANDS:
        if head.startswith(b):
            nxt = head[len(b):len(b) + 1]
            if re.search(r"[a-z]$", b) and re.match(r"[a-z]", nxt):
                continue
            return True
    return False


def hidden_name(name: str) -> bool:
    return is_franchise(name) or bool(re.search(r"주차장|화장실", name))


def related_name(v) -> str:
    """앱 relatedName: '/부제' · 괄호 · 공백 · 가운뎃점 · 문장부호를 빼고 소문자"""
    s = re.sub(r"/.*$", "", str(v or ""))
    s = re.sub(r"\(.*?\)", "", s)
    return re.sub(r"[\s·\-_.,'\"]", "", s).lower()


def related_months(today: dt.date) -> list[str]:
    """기준월 후보(YYYYMM): 2 · 3 · 4개월 전"""
    out = []
    for back in (2, 3, 4):
        y, m = today.year, today.month - back
        while m <= 0:
            y, m = y - 1, m + 12
        out.append(f"{y}{m:02d}")
    return out


def fetch_bulk(api, code: str, months: list[str]) -> tuple[str, list[dict]]:
    """시군구 전체 목록 한 달치. 처음 비지 않는 기준월"""
    for ym in months:
        rows: list[dict] = []
        for page in range(1, MAX_PAGES + 1):
            got, total = api.fetch("TarRlteTarService1/areaBasedList1",
                                   {"numOfRows": str(ROWS), "pageNo": str(page), "baseYm": ym, "areaCd": code[:2], "signguCd": code})
            rows += got
            if len(got) < ROWS or len(rows) >= total:
                break
        if rows:
            return ym, rows
    return "", []


def related_stops(rows: list[dict], region_of) -> list[dict]:
    """연관 관광지 행 → 후보(같은 시군구 · 같은 정규화 이름은 한 번, 연계 수 · 최고 순위 · 기준 관광지 최대 3곳). 연계 많은 순"""
    out: dict[str, dict] = {}
    for x in rows:
        name = str(x.get("rlteTatsNm", "")).strip()
        if not name or hidden_name(name):
            continue
        code = str(x.get("rlteSignguCd", "")).strip()
        code = code if re.fullmatch(r"\d{5}", code) else ""
        try:
            rank = int(float(x.get("rlteRank") or 99))
        except (TypeError, ValueError):
            rank = 99
        base = str(x.get("tAtsNm", "")).strip()
        key = f"{code}|{related_name(name)}"
        cur = out.get(key)
        if cur:
            cur["연계"] += 1
            cur["최고 순위"] = min(cur["최고 순위"], rank)
            if base and base not in cur["bases"] and len(cur["bases"]) < 3:
                cur["bases"].append(base)
            continue
        out[key] = {"지역": region_of(code) if code else "", "관광지": name, "시군구": code,
                    "분류": str(x.get("rlteCtgrySclsNm") or x.get("rlteCtgryMclsNm") or x.get("rlteCtgryLclsNm") or ""),
                    "숙박": str(x.get("rlteCtgryLclsNm", "")).strip() == "숙박", "연계": 1, "최고 순위": rank, "bases": [base] if base else []}
    return sorted(out.values(), key=lambda s: (-s["연계"], s["최고 순위"], s["관광지"]))


def kto_in_code(api, name: str, code: str, log) -> dict | None:
    """국문 관광정보에서 같은 이름(점수 2 이상) · 같은 시군구 코드(코드 없는 행은 둔다)인 항목(여행코스 · 숙박 타입 제외 아님 — 숙소도 찾는다)"""
    keyword = name.split("/")[0].strip()
    try:
        found, _ = api.fetch("KorService2/searchKeyword2", {"numOfRows": "30", "pageNo": "1", "arrange": "A", "keyword": keyword})
    except Exception as e:
        log(f"{name}: 관광정보 검색 실패 {e}")
        return None
    best, best_score = None, 1
    for it in found:
        if str(it.get("contenttypeid", "")) == "25":
            continue
        c = f"{it.get('lDongRegnCd', '')}{it.get('lDongSignguCd', '')}"
        if code and re.fullmatch(r"\d{5}", c) and c != code:
            continue
        if not kto_coords(it):
            continue
        s = name_score(keyword, str(it.get("title", "")), "")
        if s > best_score:
            best, best_score = it, s
    return best


def nearest_region(lat: float, lng: float, places: list[dict]) -> str:
    best, best_d = "", math.inf
    for p in places:
        if p["카테고리"] == "stay":
            continue
        try:
            d = meters(lat, lng, float(p["위도"]), float(p["경도"]))
        except ValueError:
            continue
        if d < best_d:
            best, best_d = p["지역"], d
    return best if best_d <= NEAREST_M else ""


def collect(api, places: list[dict], signgu: dict[str, str], today: dt.date, log=print, regions: list[str] | None = None,
            apply_signgu: dict[str, str] | None = None):
    targets = targets_all(places, signgu, 1, regions)
    region_of_code = {c: t["region"] for t in targets_all(places, signgu, 1) for c in t["codes"]}
    for t in targets:
        for c in t["codes"]:
            region_of_code[c] = t["region"]
    months = related_months(today)
    rows: list[dict] = []
    used: dict[str, str] = {}
    for t in targets:
        for code in t["codes"]:
            try:
                ym, got = fetch_bulk(api, code, months)
            except Exception as e:
                log(f"{t['region']} {code}: 연관 관광지 호출 실패 {e}")
                continue
            used[code] = ym
            rows += got
            log(f"{t['region']} {code}: {ym or '자료 없음'} {len(got)}행")
    stops = related_stops(rows, lambda c: region_of_code.get(c, ""))
    if regions:
        stops = [s for s in stops if not s["지역"] or s["지역"] in regions]
    log(f"연관 관광지 {len(stops):,}곳(행 {len(rows):,})")
    seen_cid = known_contentids(places)
    ids = {p["id"] for p in places}
    stays = stay_medians(places)
    candidates, new_rows = [], []
    for s in stops:
        row = {"지역": s["지역"], "관광지": s["관광지"], "시군구": s["시군구"], "분류": s["분류"], "연계": s["연계"], "최고 순위": s["최고 순위"],
               "기준 관광지": ", ".join(s["bases"]), "판정": "", "장소 id": "", "장소 이름": "", "contentid": ""}
        if s["지역"]:
            pool = [p for p in places if p["지역"] == s["지역"] and p["카테고리"] != "stay"]
            hit = match_by_name({"name": s["관광지"], "signgu": "", "city": s["지역"]}, pool)
            if hit:
                row.update(판정="기존(이름)", **{"장소 id": hit["id"], "장소 이름": hit["이름(한국어)"]})
                candidates.append(row)
                continue
        item = kto_in_code(api, s["관광지"], s["시군구"], log)
        cid = str(item.get("contentid", "")).strip() if item else ""
        coords = kto_coords(item) if item else None
        if not item or not cid or not coords:
            row["판정"] = "못 찾음(관광정보에 없음)"
            candidates.append(row)
            continue
        lat, lng = coords
        region = s["지역"] or nearest_region(lat, lng, places)
        row["지역"] = region
        if not region:
            row["판정"] = "지역 없음(건너뜀)"
            candidates.append(row)
            continue
        if cid in seen_cid or f"{POP_PREFIX}{cid}" in ids:
            row.update(판정="기존(contentid)", **{"장소 id": seen_cid.get(cid, f"{POP_PREFIX}{cid}"), "contentid": cid})
            candidates.append(row)
            continue
        pool = [p for p in places if p["지역"] == region and p["카테고리"] != "stay"]
        near = match_by_location(s["관광지"], lat, lng, pool)
        if near:
            row.update(판정="기존(위치)", **{"장소 id": near["id"], "장소 이름": near["이름(한국어)"], "contentid": cid})
            candidates.append(row)
            continue
        cat = "stay" if s["숙박"] else kto_category(item)
        pid = f"{POP_PREFIX}{cid}"
        code = f"{item.get('lDongRegnCd', '')}{item.get('lDongSignguCd', '')}"
        addr = str(item.get("addr1", "")).strip()
        new = {c: "" for c in COLUMNS}
        new.update({
            "id": pid, "권역": region_macro(places, region), "지역": region, "이름(한국어)": s["관광지"], "English": s["관광지"],
            "카테고리": cat, "위도": f"{lat:.5f}", "경도": f"{lng:.5f}", "추천 체류(분)": str(stays.get(cat, 60)),
            "출처": " · ".join(x for x in (addr, f"한국관광공사 연관 관광지(연계 {s['연계']}회{(' · ' + ', '.join(s['bases'])) if s['bases'] else ''})", f"관광정보 contentid {cid} 좌표") if x),
            "설명": f"{s['분류'] or '관광지'} · {', '.join(s['bases'][:2]) or region} 등과 함께 많이 찾는 곳 (연관 {s['연계']}회)",
        })
        new_rows.append(new)
        places.append(new)
        ids.add(pid)
        seen_cid[cid] = pid
        if apply_signgu is not None:
            apply_signgu[pid] = code if re.fullmatch(r"\d{5}", code) else s["시군구"]
        row.update(판정="신규", **{"장소 id": pid, "장소 이름": s["관광지"], "contentid": cid})
        candidates.append(row)
    return used, candidates, new_rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--places", type=Path, default=PLACES_CSV)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--signgu", type=Path, default=SIGNGU_JSON, help="장소 id → 시군구 코드 JSON")
    ap.add_argument("--regions", nargs="*", help="이 지역(도시)만")
    ap.add_argument("--from-json", type=Path, help="받아 둔 응답 JSON 폴더(related_<signguCd>_<baseYm>_p<쪽>.json · search_<검색어>.json)")
    ap.add_argument("--apply", action="store_true", help="새 장소를 tour-places.csv 끝에 붙인다")
    ap.add_argument("--today", help="기준 날짜 YYYY-MM-DD(기본 오늘)")
    args = ap.parse_args(argv)

    if args.from_json:
        api = JsonDirApi(args.from_json)
    else:
        key = os.environ.get("DATA_GO_KR_KEY", "").strip()
        if not key:
            print("DATA_GO_KR_KEY 환경변수가 필요합니다(또는 --from-json)", file=sys.stderr)
            return 2
        api = Api(key)
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    places = read_places(args.places)
    signgu = read_signgu(args.signgu)
    used, candidates, new_rows = collect(api, places, signgu, today, regions=args.regions, apply_signgu=signgu)
    stamp = today.strftime("%Y%m%d")
    cols = ["지역", "관광지", "시군구", "분류", "연계", "최고 순위", "기준 관광지", "판정", "장소 id", "장소 이름", "contentid"]
    write_csv(args.out / f"related_candidates_{stamp}.csv", candidates, cols)
    write_csv(args.out / f"related_new_rows_{stamp}.csv", new_rows, COLUMNS)
    counts: dict[str, int] = {}
    for c in candidates:
        counts[c["판정"]] = counts.get(c["판정"], 0) + 1
    print(f"시군구 {len(used)}곳 · 후보 {len(candidates):,}곳 {counts} · 새 장소 {len(new_rows):,}곳 → {args.out}")
    if args.apply and new_rows:
        append_rows(args.places, new_rows)
        write_signgu(args.signgu, signgu)
        print(f"붙였다: {args.places} · {args.signgu}")
    elif args.apply:
        print("새 장소가 없어 파일은 그대로")
    return 0


if __name__ == "__main__":
    sys.exit(main())
