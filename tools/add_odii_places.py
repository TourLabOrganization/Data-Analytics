# -*- coding: utf-8 -*-
"""한국관광공사 관광지 오디오 가이드(오디, Odii/themeBasedList)에 해설이 있는 관광지 가운데 장소 표에 없는 곳을 analysis/tour-places.csv에 더한다.

    DATA_GO_KR_KEY=<공공데이터포털 인증키> python tools/add_odii_places.py            # 후보만 만든다(파일은 바꾸지 않는다)
    DATA_GO_KR_KEY=<키> python tools/add_odii_places.py --apply                    # 새 장소를 tour-places.csv 끝에 붙인다
    python tools/add_odii_places.py --from-json <폴더> --apply                      # 받아 둔 응답 JSON으로(네트워크 없이)

규칙(앱 frontend src/lib/tour-collect.ts collectOdii와 같다):
  1. 오디 한국어 관광지 목록(Odii/themeBasedList langCode=ko, 쪽당 1,000행 · 최대 5쪽)을 받는다. 관광지(tid)마다 제목 · 좌표(mapY · mapX) · 주소(addr1 시도 · addr2 시군구).
  2. 지역은 주소로 정한다(광역시 · 특별시 · 세종은 그 이름, 그 밖은 시군구 이름에서 시 · 군을 뗀 것. 강원 고성 → 고성(강원), 경기 광주 → 경기광주,
     제주 · 서귀포 → 제주). 장소 표에 없는 지역이면 가장 가까운 장소(숙박 제외, 30km 안)의 지역, 그것도 없으면 건너뛴다.
  3. 같은 지역 장소와 이름 점수 2 이상이면 기존 장소. 아니면 좌표 250m 안(또는 1km 안에서 이름이 절반 이상 겹치는) 기존 장소. 둘 다 없으면 새 장소.
  4. 새 장소의 범주 · id: 국문 관광정보 KorService2/searchKeyword2로 같은 이름(점수 2 이상) · 1km 안 항목을 찾으면 그 분류(ktoCategory)와
     id pop<contentid>(인기 관광지 도구와 같은 id). 못 찾으면 이름의 낱말로 범주를 정하고(해변 · 섬 → sea, 사 · 궁 · 성 · 유적 → herit, 공원 · 숲 · 오름 → heal …)
     id는 odii<tid>. 추천 체류는 그 범주의 기존 중앙값. 출처에 「오디 tid <n>」을 적어 다시 돌려도 두 번 넣지 않는다.
  5. --apply 때 새 장소의 시군구 코드(관광정보 법정동 코드, 없으면 빈 값)를 analysis/place_signgu.json에 넣는다.

산출(--out 폴더, 기본 analysis/odii_added): odii_candidates_<날짜>.csv(관광지마다 판정) · odii_new_rows_<날짜>.csv(붙일 행).
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
    match_by_name, meters, name_score, read_places, read_signgu, region_macro, stay_medians, write_csv, write_signgu,
)

OUT_DIR = Path(__file__).resolve().parents[1] / "analysis" / "odii_added"
ODII_PREFIX = "odii"
POP_PREFIX = "pop"
ROWS, MAX_PAGES = 1000, 5
NEAREST_KM = 30
METRO = {"서울": "서울", "부산": "부산", "대구": "대구", "인천": "인천", "광주광역시": "광주", "대전": "대전", "울산": "울산", "세종": "세종"}
CAT_RULES = [
    ("sea", re.compile(r"해수욕장|해변|해안|바다|포구|등대|섬$|도$|항$|갯벌|방파제")),
    ("food", re.compile(r"시장|먹거리|맛|음식|카페거리|포차")),
    ("activity", re.compile(r"체험|박람회|월드|파크|테마|놀이|레일|케이블카|짚|스키|수목원|동물원|아쿠아|전망대|스카이")),
    ("herit", re.compile(r"사$|사지|궁|성$|산성|읍성|릉$|릉|묘|고분|서원|향교|유적|박물관|기념관|문학관|미술관|고택|생가|탑|비$|정$|루$|대$|당$|관$|성당|교회|사당|서당|터$")),
    ("heal", re.compile(r"공원|숲|산$|봉$|폭포|호수|저수지|계곡|오름|습지|정원|둘레길|길$|강$|천$|들|평야|농원|목장")),
]


def odii_region(addr1: str, addr2: str) -> str:
    a1 = addr1.replace(" ", "")
    for k, v in METRO.items():
        if a1.startswith(k):
            return v
    if a1.startswith("제주"):
        return "제주"
    a2 = addr2.split()[0] if addr2.strip() else ""
    base = re.sub(r"(시|군)$", "", a2)
    if not base:
        return ""
    if base == "고성" and a1.startswith("강원"):
        return "고성(강원)"
    if base == "광주" and a1.startswith("경기"):
        return "경기광주"
    return base


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
    return best if best_d <= NEAREST_KM * 1000 else ""


def rule_category(name: str) -> str:
    for cat, rx in CAT_RULES:
        if rx.search(name):
            return cat
    return "herit"


def fetch_themes(api) -> list[dict]:
    items: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        got, total = api.fetch("Odii/themeBasedList", {"numOfRows": str(ROWS), "pageNo": str(page), "langCode": "ko"})
        items += got
        if len(got) < ROWS or len(items) >= total:
            break
    seen, out = set(), []
    for x in items:
        tid = str(x.get("tid", "")).strip()
        title = str(x.get("title", "")).strip()
        try:
            lat, lng = float(x.get("mapY")), float(x.get("mapX"))
        except (TypeError, ValueError):
            continue
        if not tid or not title or tid in seen or not (32 <= lat <= 39 and 124 <= lng <= 132):
            continue
        seen.add(tid)
        out.append({"tid": tid, "name": title, "lat": lat, "lng": lng, "addr1": str(x.get("addr1", "")).strip(),
                    "addr2": str(x.get("addr2", "")).strip(), "theme": str(x.get("themeCategory", "")).strip()})
    return out


def known_tids(places: list[dict]) -> dict[str, str]:
    out = {}
    for p in places:
        m = re.search(r"오디 tid (\d+)", p["출처"])
        if m:
            out[m.group(1)] = p["id"]
    return out


def kto_lookup(api, name: str, lat: float, lng: float, log) -> dict | None:
    """같은 이름(점수 2 이상) · 1km 안의 국문 관광정보 항목(여행코스 · 숙박 제외, 가까운 것)"""
    try:
        found, _ = api.fetch("KorService2/searchKeyword2", {"numOfRows": "30", "pageNo": "1", "arrange": "A", "keyword": name})
    except Exception as e:
        log(f"{name}: 관광정보 검색 실패 {e}")
        return None
    best, best_d = None, math.inf
    for it in found:
        if str(it.get("contenttypeid", "")) in ("25", "32"):
            continue
        c = kto_coords(it)
        if not c or name_score(name, str(it.get("title", "")), "") < 2:
            continue
        d = meters(lat, lng, *c)
        if d <= 1000 and d < best_d:
            best, best_d = it, d
    return best


def collect(api, places: list[dict], log=print, signgu: dict[str, str] | None = None, regions: list[str] | None = None):
    themes = fetch_themes(api)
    log(f"오디 관광지 {len(themes):,}곳")
    regions_known = {p["지역"] for p in places}
    seen_cid, seen_tid = known_contentids(places), known_tids(places)
    ids = {p["id"] for p in places}
    stays = stay_medians(places)
    candidates, new_rows = [], []
    for t in themes:
        region = odii_region(t["addr1"], t["addr2"])
        how = "주소"
        if region not in regions_known:
            region, how = nearest_region(t["lat"], t["lng"], places), "가까운 장소"
        row = {"tid": t["tid"], "관광지": t["name"], "주소": f"{t['addr1']} {t['addr2']}".strip(), "위도": t["lat"], "경도": t["lng"],
               "지역": region, "지역 근거": how, "판정": "", "장소 id": "", "장소 이름": "", "contentid": ""}
        if regions and region not in regions:
            continue
        if not region:
            row["판정"] = "지역 없음(건너뜀)"
            candidates.append(row)
            continue
        if t["tid"] in seen_tid:
            row.update(판정="기존(tid)", **{"장소 id": seen_tid[t["tid"]]})
            candidates.append(row)
            continue
        pool = [p for p in places if p["지역"] == region and p["카테고리"] != "stay"]
        hit = match_by_name({"name": t["name"], "signgu": "", "city": region}, pool)
        if hit:
            row.update(판정="기존(이름)", **{"장소 id": hit["id"], "장소 이름": hit["이름(한국어)"]})
            candidates.append(row)
            continue
        near = match_by_location(t["name"], t["lat"], t["lng"], pool)
        if near:
            row.update(판정="기존(위치)", **{"장소 id": near["id"], "장소 이름": near["이름(한국어)"]})
            candidates.append(row)
            continue
        item = kto_lookup(api, t["name"], t["lat"], t["lng"], log)
        cid = str(item.get("contentid", "")).strip() if item else ""
        if cid and (cid in seen_cid or f"{POP_PREFIX}{cid}" in ids):
            row.update(판정="기존(contentid)", **{"장소 id": seen_cid.get(cid, f"{POP_PREFIX}{cid}"), "contentid": cid})
            candidates.append(row)
            continue
        if item and cid:
            pid, cat = f"{POP_PREFIX}{cid}", kto_category(item)
            lat, lng = kto_coords(item)
            code = f"{item.get('lDongRegnCd', '')}{item.get('lDongSignguCd', '')}"
            addr = str(item.get("addr1", "")).strip()
        else:
            pid, cat, lat, lng, code, addr = f"{ODII_PREFIX}{t['tid']}", rule_category(t["name"]), t["lat"], t["lng"], "", row["주소"]
        new = {c: "" for c in COLUMNS}
        new.update({
            "id": pid, "권역": region_macro(places, region), "지역": region, "이름(한국어)": t["name"], "English": t["name"],
            "카테고리": cat, "위도": f"{lat:.5f}", "경도": f"{lng:.5f}", "추천 체류(분)": str(stays.get(cat, 60)),
            "출처": " · ".join(x for x in (addr, f"한국관광공사 관광지 오디오 가이드(오디 tid {t['tid']})", f"관광정보 contentid {cid} 좌표" if cid else "오디 좌표") if x),
            "설명": f"오디오 가이드(오디) 해설이 있는 관광지{(' · ' + t['theme']) if t['theme'] else ''}. 분류 {cat}는 {'관광정보 콘텐츠 타입 ' + str(item.get('contenttypeid', '')) if item else '이름 낱말 규칙'}에서.",
        })
        new_rows.append(new)
        places.append(new)
        ids.add(pid)
        seen_tid[t["tid"]] = pid
        if cid:
            seen_cid[cid] = pid
        if signgu is not None:
            signgu[pid] = code if re.fullmatch(r"\d{5}", code) else ""
        row.update(판정="신규", **{"장소 id": pid, "장소 이름": t["name"], "contentid": cid})
        candidates.append(row)
    return candidates, new_rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--places", type=Path, default=PLACES_CSV)
    ap.add_argument("--signgu", type=Path, default=SIGNGU_JSON)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--regions", nargs="*", help="이 지역만")
    ap.add_argument("--from-json", type=Path, help="받아 둔 응답 JSON 폴더(odii_ko_p<쪽>.json · search_<검색어>.json)")
    ap.add_argument("--apply", action="store_true", help="새 장소를 tour-places.csv에 붙인다")
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
    before = len(places)
    signgu = read_signgu(a.signgu)
    candidates, new_rows = collect(api, places, signgu=signgu, regions=a.regions)
    tag = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y%m%d")
    write_csv(a.out / f"odii_candidates_{tag}.csv", candidates, ["tid", "관광지", "주소", "위도", "경도", "지역", "지역 근거", "판정", "장소 id", "장소 이름", "contentid"])
    write_csv(a.out / f"odii_new_rows_{tag}.csv", new_rows, COLUMNS)
    n = len(candidates)
    print(f"관광지 {n:,}곳: 기존 {sum(c['판정'].startswith('기존') for c in candidates):,} · 신규 {len(new_rows):,} · 지역 없음 {sum(c['판정'].startswith('지역') for c in candidates):,}")
    if a.apply and new_rows:
        append_rows(a.places, new_rows)
        write_signgu(a.signgu, signgu)
        print(f"{a.places}: {before:,} → {before + len(new_rows):,}행, 시군구 코드 {a.signgu} 갱신. 분석을 다시 돌려야 군집에 반영된다.")
    elif a.apply:
        print("새 장소가 없어 tour-places.csv는 그대로다.")
    else:
        print("--apply 를 주면 새 행을 tour-places.csv에 붙인다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
