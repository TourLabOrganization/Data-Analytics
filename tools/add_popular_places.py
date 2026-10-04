# -*- coding: utf-8 -*-
"""앱 홈 '지금 인기 관광지'(한국관광공사 집중률 API)가 부르는 관광지를 analysis/tour-places.csv에 새 장소로 추가한다.

    DATA_GO_KR_KEY=<공공데이터포털 인증키> python tools/add_popular_places.py            # 전국: 후보만 만든다(파일은 바꾸지 않는다)
    DATA_GO_KR_KEY=<키> python tools/add_popular_places.py --apply                    # 새 장소를 tour-places.csv 끝에 붙인다
    DATA_GO_KR_KEY=<키> python tools/add_popular_places.py --scope home               # 앱 홈 칩 10개 도시만(앱과 같은 시군구 선택)
    python tools/add_popular_places.py --from-json <폴더> --apply                      # 받아 둔 응답 JSON으로(네트워크 없이)

규칙은 앱(frontend src/lib/tour-popular.ts · tour-api.ts)과 같다.
  1. 시군구마다 집중률 행을 받는다(TatsCnctrRateService/tatsCnctrRatedList, areaCd·signguCd만, 쪽당 1,000행 · 최대 5쪽).
     강원 51·전북 52로 그 시군구 행이 없으면 옛 코드 42·45로 한 번 더 부른다. 어느 시군구를 부르느냐는 --scope로 정한다.
       all(기본): 장소 표의 124개 지역 전부. 장소(숙박 제외)가 있는 시군구(analysis/place_signgu.json의 법정동 코드, --min-places 이상)를
                 모두 부르고, 한 시군구가 두 지역에 걸치면 장소가 많은 지역에 붙인다.
       home: 앱 홈 칩 10개 도시만, 앱이 고른 시군구(CITY_DISTRICTS: 장소 5곳 이상 · 많은 순 · 최대 4곳).
  2. 지역마다 기준 날짜(서울 오늘, 없으면 그 뒤 가장 이른 날)의 집중률 높은 순으로 상위 10곳(--top, 0이면 전부)이 후보다.
  3. 같은 지역의 기존 장소와 이름 점수 2 이상이면 이미 있는 장소다(추가하지 않는다).
  4. 못 맞춘 후보는 국문 관광정보 KorService2/searchKeyword2로 찾아(같은 시군구 · 이름 점수 2 이상 · 관광지 타입 우선) 좌표를 얻고,
     250m 안의 기존 장소(또는 1km 안에서 이름이 절반 이상 겹치는 곳)가 있으면 그 장소로 본다.
  5. 남은 후보가 새 장소다. id는 pop<관광정보 contentid>(앱 frontend scripts/add-popular-places.mjs와 같은 id), 범주는 관광정보 분류로(ktoCategory),
     추천 체류는 그 범주의 기존 중앙값, 출처에 관광정보 contentid를 적어 두어 다시 돌려도 같은 곳을 두 번 넣지 않는다.
     --apply 때 새 장소의 시군구 코드(관광정보 법정동 코드)도 analysis/place_signgu.json에 넣어 다음 실행의 조회 대상이 된다.

산출(--out 폴더, 기본 analysis/popular_added):
  popular_candidates_<날짜>.csv   도시별 후보 전부와 판정(기존 장소 id 또는 신규 id, 못 찾음)
  popular_new_rows_<날짜>.csv     tour-places.csv에 붙일(붙인) 행
새 장소를 붙인 뒤에는 분석(analysis/run_analysis.py 또는 노트북)을 다시 돌려야 군집·코스 연결에 반영된다.
인증키는 환경변수 DATA_GO_KR_KEY로만 받고 어디에도 적지 않는다.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
PLACES_CSV = ROOT / "analysis" / "tour-places.csv"
SIGNGU_JSON = ROOT / "analysis" / "place_signgu.json"  # 장소 id → 법정동 시군구 코드(앱 signgu.json과 같다)
OUT_DIR = ROOT / "analysis" / "popular_added"
MATCH_CSV = ROOT / "analysis" / "popular_match.csv"  # 수기 대조표(앱 lib/popular-match.ts와 같은 짝): 규칙으로 못 잇는 이름 → 장소 id
BASE = "https://apis.data.go.kr/B551011"
ID_PREFIX = "pop"

# 앱 tour-popular.ts citySigngu(): 도시마다 플래너 장소(숙박 제외) 5곳 이상인 시군구를 장소 수 순으로 최대 4곳(2026-10-04 장소 데이터 기준)
CITY_DISTRICTS: dict[str, list[str]] = {
    "서울": ["11110", "11440", "11560", "11170"],  # 종로 · 마포 · 영등포 · 용산(같은 장소 통합으로 송파가 12곳이 되어 빠짐)
    "부산": ["26350", "26710", "26200", "26230"],  # 해운대 · 기장 · 영도 · 부산진
    "제주": ["50110", "50130"],
    "경주": ["47130"],
    "강릉": ["51150"],
    "전주": ["52111", "52113"],
    "인천": ["28125", "28710", "28185", "28200"],  # 중구 · 강화 · 연수 · 남동
    "속초": ["51210"],
    "대구": ["27710", "27260", "27720", "27290"],  # 달성 · 수성 · 군위 · 달서(2026-10-04 추가)
    "춘천": ["51110"],
}
HOME_CITIES = list(CITY_DISTRICTS)
ROWS, MAX_PAGES, TOP = 1000, 5, 10
SAME_SPOT_M, NEAR_SPOT_M, NEAR_SPOT_OVERLAP = 250, 1000, 0.5
SKIP_TYPES, SPOT_TYPES = {"25", "32"}, {"12", "14", "28", "38"}
SEA_RE = re.compile(r"해수욕장|해변|해안|바다|포구|등대|섬|항$")
COLUMNS = ["id", "권역", "지역", "이름(한국어)", "English", "中文", "日本語", "카테고리", "카테고리명", "위도", "경도",
           "추천 체류(분)", "유네스코", "지정구역", "출처", "설명", "링크"]


# ---------- 이름 비교(앱 tour-crowd.ts · tour-popular.ts와 같다) ----------
def crowd_name(v) -> str:
    return re.sub(r"[\s·]", "", re.sub(r"\[.*?\]|\(.*?\)", "", str(v or "")))


def crowd_score(name, me: str) -> int:
    n = crowd_name(name)
    if not n or not me:
        return 0
    if n == me:
        return 3
    return 2 if (me in n or n in me) else 0


def spot_name(v) -> str:
    n = re.sub(r"(해수욕장|해안)$", "해변", crowd_name(v))
    return re.sub(r"(전통시장|재래시장)$", "시장", n)


def without_city(name: str, city: str) -> str | None:
    c = re.sub(r"\(.*?\)", "", city).strip()
    if not c or not name.startswith(c):
        return None
    rest = name[len(c):].strip()
    return rest if len(rest) >= 2 else None


def name_variants(name: str, city: str) -> list[str]:
    raw = [name, (without_city(name, city) or "") if city else ""]
    out: list[str] = []
    for n in map(spot_name, raw):
        if len(n) >= 2 and n not in out:
            out.append(n)
    return out


def name_score(spot: str, place: str, city: str) -> int:
    best = crowd_score(spot, crowd_name(place))
    if best == 3:
        return 3
    for a in name_variants(spot, city):
        for b in name_variants(place, city):
            if a == b:
                return 3
            short = a if len(a) <= len(b) else b
            if len(short) >= 3 and (a in b or b in a):
                best = 2
    return best


def name_overlap(a: str, b: str) -> float:
    def pairs(s: str) -> list[str]:
        n = spot_name(s)
        return [n[i:i + 2] for i in range(len(n) - 1)]
    x, y = pairs(a), pairs(b)
    if not x or not y:
        return 0.0
    rest, hit = list(y), 0
    for p in x:
        if p in rest:
            hit += 1
            rest.remove(p)
    return 2 * hit / (len(x) + len(y))


def meters(lat1, lng1, lat2, lng2) -> float:
    r = math.pi / 180
    a = math.sin((lat2 - lat1) * r / 2) ** 2 + math.cos(lat1 * r) * math.cos(lat2 * r) * math.sin((lng2 - lng1) * r / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(a))


# ---------- 한국관광공사 API ----------
def signgu_variants(code: str) -> list[str]:
    pair = {"51": "42", "42": "51", "52": "45", "45": "52"}
    other = pair.get(code[:2])
    return [code, other + code[2:]] if other else [code]


def parse_items(body) -> tuple[list[dict], int]:
    resp = body.get("response") if isinstance(body, dict) else None
    if not isinstance(resp, dict):
        raise ValueError("tour api shape")
    code = str((resp.get("header") or {}).get("resultCode", ""))
    if code not in ("0000", "00"):
        raise ValueError(f"tour api result code {code}")
    inner = resp.get("body") or {}
    items = inner.get("items")
    item = items.get("item") if isinstance(items, dict) else None
    lst = item if isinstance(item, list) else ([item] if item else [])
    try:
        total = int(inner.get("totalCount") or 0)
    except (TypeError, ValueError):
        total = 0
    return [x for x in lst if isinstance(x, dict)], total


class Api:
    """공공데이터포털 호출. fetch(path, params) → (items, totalCount)."""

    def __init__(self, key: str):
        self.key = key

    def fetch(self, path: str, params: dict) -> tuple[list[dict], int]:
        q = {"serviceKey": self.key, "MobileOS": "ETC", "MobileApp": "TourNavigator", "_type": "json", **params}
        url = f"{BASE}/{path}?" + urllib.parse.urlencode(q)
        with urllib.request.urlopen(url, timeout=30) as r:
            return parse_items(json.load(r))


class JsonDirApi:
    """받아 둔 응답으로 돌린다(테스트 · 네트워크 없는 곳). 파일 이름: crowd_<signguCd>_p<쪽>.json, odii_<langCode>_p<쪽>.json,
    related_<signguCd>_<baseYm>_p<쪽>.json, search_<검색어>.json"""

    def __init__(self, folder: Path):
        self.folder = Path(folder)

    def fetch(self, path: str, params: dict) -> tuple[list[dict], int]:
        if path.startswith("TatsCnctrRateService"):
            name = f"crowd_{params['signguCd']}_p{params['pageNo']}.json"
        elif path.startswith("Odii/themeBasedList"):
            name = f"odii_{params['langCode']}_p{params['pageNo']}.json"
        elif path.startswith("TarRlteTarService1/areaBasedList1"):
            name = f"related_{params['signguCd']}_{params['baseYm']}_p{params['pageNo']}.json"
        else:
            name = f"search_{params['keyword']}.json"
        f = self.folder / name
        if not f.is_file():
            return [], 0
        return parse_items(json.loads(f.read_text(encoding="utf-8")))


def district_items(api, code: str) -> list[dict]:
    for q in signgu_variants(code):
        got: list[dict] = []
        for page in range(1, MAX_PAGES + 1):
            items, total = api.fetch("TatsCnctrRateService/tatsCnctrRatedList",
                                     {"numOfRows": str(ROWS), "pageNo": str(page), "areaCd": q[:2], "signguCd": q})
            got += items
            if len(items) < ROWS or len(got) >= total:
                break
        mine = [dict(x, signguCd=code) for x in got if str(x.get("signguCd", "")).strip() in signgu_variants(code)]
        if mine:
            return mine
    return []


def ymd(v) -> str | None:
    d = re.sub(r"\D", "", str(v or ""))
    return f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 else None


def rank_spots(items: list[dict], today: str) -> tuple[str, list[dict]] | None:
    rows = []
    for x in items:
        date, name = ymd(x.get("baseYmd")), str(x.get("tAtsNm", "")).strip()
        try:
            rate = float(x.get("cnctrRate"))
        except (TypeError, ValueError):
            continue
        if not date or not name or not math.isfinite(rate) or date < today:
            continue
        rows.append({"date": date, "rate": rate, "name": name,
                     "district": str(x.get("signguNm", "")).strip(), "signgu": str(x.get("signguCd", "")).strip()})
    if not rows:
        return None
    date = today if any(r["date"] == today for r in rows) else min(r["date"] for r in rows)
    by: dict[str, dict] = {}
    for r in rows:
        if r["date"] == date:
            by[f"{r['signgu']}|{r['name']}"] = r
    return date, sorted(by.values(), key=lambda r: (-r["rate"], r["name"]))


def kto_category(item: dict) -> str:
    t, cat1, lcls = str(item.get("contenttypeid", "")), str(item.get("cat1", "")), str(item.get("lclsSystm1", ""))
    if t == "32" or cat1 == "B02" or lcls == "AC":
        return "stay"
    if t == "39" or cat1 == "A05" or lcls == "FD":
        return "food"
    if t in ("15", "28", "38") or cat1 in ("A03", "A04") or lcls in ("LS", "SH", "EV", "EX"):
        return "activity"
    if t == "14" or cat1 == "A02" or lcls in ("HS", "VE"):
        return "herit"
    return "sea" if SEA_RE.search(str(item.get("title", ""))) else "heal"


def pick_spot_item(items: list[dict], spot: dict) -> dict | None:
    scored = []
    for i, x in enumerate(items):
        if str(x.get("contenttypeid", "")) in SKIP_TYPES:
            continue
        code = f"{x.get('lDongRegnCd', '')}{x.get('lDongSignguCd', '')}"
        if re.fullmatch(r"\d{5}", spot["signgu"]) and re.fullmatch(r"\d{5}", code) and code != spot["signgu"]:
            continue
        score = name_score(spot["name"], str(x.get("title", "")), "")
        if score < 2:
            continue
        scored.append((-score, 0 if str(x.get("contenttypeid", "")) in SPOT_TYPES else 1, i, x))
    return min(scored)[3] if scored else None


def kto_coords(item: dict) -> tuple[float, float] | None:
    try:
        lat, lng = float(item.get("mapy")), float(item.get("mapx"))
    except (TypeError, ValueError):
        return None
    return (lat, lng) if 32 <= lat <= 39 and 124 <= lng <= 132 else None


# ---------- 기존 장소 표 ----------
def read_places(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    missing = [c for c in COLUMNS if c not in rows[0]]
    if missing:
        raise ValueError(f"tour-places.csv 칼럼 누락: {missing}")
    return rows


def city_places(places: list[dict], city: str) -> list[dict]:
    return [p for p in places if p["지역"] == city and p["카테고리"] != "stay"]


def read_match(path: Path = MATCH_CSV) -> dict[str, str]:
    """수기 대조표: '도시|정규화 이름' → 장소 id. 파일이 없으면 빈 표"""
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {f"{r['city'].strip()}|{crowd_name(r['name'])}": r["id"].strip() for r in csv.DictReader(f) if r.get("id", "").strip()}


def match_by_name(spot: dict, pool: list[dict], pins: dict[str, str] | None = None) -> dict | None:
    """수기 대조표(pins)에 있으면 그 장소, 아니면 이름 점수 2 이상 중 가장 높은 곳(앱 matchPlace와 같다)"""
    pinned = (pins or {}).get(f"{spot.get('city', '')}|{crowd_name(spot['name'])}")
    if pinned:
        for p in pool:
            if p["id"] == pinned:
                return p
    best, best_score = None, 1
    for p in pool:
        s = name_score(spot["name"], p["이름(한국어)"], spot["city"])
        if s > best_score:
            best, best_score = p, s
    return best


def match_by_location(name: str, lat: float, lng: float, pool: list[dict]) -> dict | None:
    best, best_d = None, math.inf
    for p in pool:
        try:
            d = meters(lat, lng, float(p["위도"]), float(p["경도"]))
        except ValueError:
            continue
        if d > NEAR_SPOT_M or d >= best_d:
            continue
        if d > SAME_SPOT_M and name_overlap(name, p["이름(한국어)"]) < NEAR_SPOT_OVERLAP:
            continue
        best, best_d = p, d
    return best


def known_contentids(places: list[dict]) -> dict[str, str]:
    out = {}
    for p in places:
        m = re.search(r"contentid (\d+)", p["출처"])
        if m:
            out[m.group(1)] = p["id"]
    return out


def stay_medians(places: list[dict]) -> dict[str, int]:
    by: dict[str, list[int]] = {}
    for p in places:
        try:
            by.setdefault(p["카테고리"], []).append(int(float(p["추천 체류(분)"])))
        except ValueError:
            pass
    return {k: int(median(v)) for k, v in by.items() if v}


# ---------- 조회 대상 ----------
def read_signgu(path: Path) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def write_signgu(path: Path, codes: dict[str, str]) -> None:
    path.write_text("{\n" + ",\n".join(f'"{k}": "{v}"' for k, v in codes.items()) + "\n}", encoding="utf-8")


def region_macro(places: list[dict], region: str) -> str:
    """지역의 권역: 그 지역 행에 가장 많은 값. 없으면 '전국'"""
    counts: dict[str, int] = {}
    for p in places:
        if p["지역"] == region and p["권역"]:
            counts[p["권역"]] = counts.get(p["권역"], 0) + 1
    return max(counts, key=counts.get) if counts else "전국"


def targets_home(places: list[dict], cities: list[str]) -> list[dict]:
    """앱 홈 칩 도시: {region, codes, pool}. 매칭 풀은 그 도시의 장소(숙박 제외)"""
    out = []
    for city in cities:
        codes = CITY_DISTRICTS.get(city)
        if not codes:
            continue
        out.append({"region": city, "codes": list(codes), "pool": [p for p in places if p["지역"] == city and p["카테고리"] != "stay"]})
    return out


def targets_all(places: list[dict], signgu: dict[str, str], min_places: int = 1, regions: list[str] | None = None) -> list[dict]:
    """전국: 장소(숙박 제외)가 있는 시군구 전부. 한 시군구가 두 지역에 걸치면 장소가 많은 지역(같으면 이름 순)에 붙인다.
    매칭 풀은 그 지역의 장소 + 그 시군구 코드의 장소(지역이 달라도)"""
    count: dict[tuple[str, str], int] = {}
    for p in places:
        code = signgu.get(p["id"], "")
        if p["카테고리"] == "stay" or not re.fullmatch(r"\d{5}", code):
            continue
        count[(p["지역"], code)] = count.get((p["지역"], code), 0) + 1
    claims: dict[str, list[tuple[int, str]]] = {}
    for (region, code), n in count.items():
        if n >= min_places:
            claims.setdefault(code, []).append((-n, region))
    by_region: dict[str, list[str]] = {}
    for code, who in claims.items():
        by_region.setdefault(min(who)[1], []).append(code)
    out = []
    for region in sorted(by_region):
        if regions and region not in regions:
            continue
        codes = sorted(by_region[region], key=lambda c: (-count[(region, c)], c))
        pool = [p for p in places if p["카테고리"] != "stay" and (p["지역"] == region or signgu.get(p["id"], "") in codes)]
        out.append({"region": region, "codes": codes, "pool": pool})
    return out


# ---------- 본 작업 ----------
def collect(api, places: list[dict], targets: list[dict], today: str, top: int, log=print,
            signgu: dict[str, str] | None = None, pins: dict[str, str] | None = None) -> tuple[list[dict], list[dict]]:
    """(후보 판정표, 새 행). places에는 새 행을 바로 더해 같은 실행 안에서도 중복이 없다. signgu를 주면 새 장소의 코드를 넣는다.
    pins(수기 대조표 read_match)를 주지 않으면 analysis/popular_match.csv를 읽는다."""
    if pins is None:
        pins = read_match()
    candidates, new_rows = [], []
    seen = known_contentids(places)
    ids = {p["id"] for p in places}
    stays = stay_medians(places)
    for t in targets:
        city, codes, pool = t["region"], t["codes"], t["pool"]
        items, failed = [], 0
        for c in codes:
            try:
                items += district_items(api, c)
            except Exception as e:  # 한 시군구가 실패해도 나머지로(앱과 같다)
                failed += 1
                log(f"{city} {c}: 실패 {e}")
        if failed == len(codes):
            log(f"{city}: 모든 시군구 실패")
            continue
        ranked = rank_spots(items, today)
        if not ranked:
            log(f"{city}: 기준 날짜 행 없음")
            continue
        date, spots = ranked
        if top > 0:
            spots = spots[:top]
        added = 0
        for rank, s in enumerate(spots, 1):
            spot = dict(s, city=city)
            row = {"지역": city, "순위": rank, "관광지": s["name"], "시군구": s["district"], "시군구 코드": s["signgu"],
                   "집중률": s["rate"], "기준 날짜": date, "판정": "", "장소 id": "", "장소 이름": "", "contentid": ""}
            hit = match_by_name(spot, pool, pins)
            if hit:
                row.update(판정="기존(이름)", **{"장소 id": hit["id"], "장소 이름": hit["이름(한국어)"]})
                candidates.append(row)
                continue
            try:
                found, _ = api.fetch("KorService2/searchKeyword2", {"numOfRows": "30", "pageNo": "1", "arrange": "A", "keyword": s["name"]})
            except Exception as e:
                found = []
                log(f"{city} {s['name']}: 검색 실패 {e}")
            item = pick_spot_item(found, spot)
            coords = kto_coords(item) if item else None
            if not item or not coords:
                row["판정"] = "못 찾음(관광정보에 없음)"
                candidates.append(row)
                continue
            cid = str(item.get("contentid", "")).strip()
            row["contentid"] = cid
            if cid in seen or f"{ID_PREFIX}{cid}" in ids:
                row.update(판정="기존(contentid)", **{"장소 id": seen.get(cid, f"{ID_PREFIX}{cid}")})
                candidates.append(row)
                continue
            lat, lng = coords
            near = match_by_location(s["name"], lat, lng, pool)
            if near:
                row.update(판정="기존(위치)", **{"장소 id": near["id"], "장소 이름": near["이름(한국어)"]})
                candidates.append(row)
                continue
            cat = kto_category(item)
            addr = " ".join(x for x in (str(item.get("addr1", "")).strip(), str(item.get("addr2", "")).strip()) if x)
            new = {c: "" for c in COLUMNS}
            new.update({
                "id": f"{ID_PREFIX}{cid}", "권역": region_macro(places, city), "지역": city,
                "이름(한국어)": str(item.get("title", "")).strip() or s["name"],
                "English": str(item.get("title", "")).strip() or s["name"],  # 영문 관광정보로 바꾸기 전까지 한국어 그대로(연관 관광지 행과 같다)
                "카테고리": cat, "위도": f"{lat:.5f}", "경도": f"{lng:.5f}",
                "추천 체류(분)": str(stays.get(cat, 60)),
                "출처": " · ".join(x for x in (addr, f"한국관광공사 인기 관광지(집중률 {s['rate']:g}%, {date})", f"관광정보 contentid {cid} 좌표") if x),
                "설명": f"{s['district'] or city} 인기 관광지 {rank}위({date} 집중률 기준). 분류 {cat}는 관광정보 콘텐츠 타입 {item.get('contenttypeid', '')}에서.",
            })
            new_rows.append(new)
            places.append(new)
            pool.append(new)
            seen[cid] = new["id"]
            ids.add(new["id"])
            if signgu is not None:
                code = f"{item.get('lDongRegnCd', '')}{item.get('lDongSignguCd', '')}"
                signgu[new["id"]] = code if re.fullmatch(r"\d{5}", code) else s["signgu"]
            added += 1
            row.update(판정="신규", **{"장소 id": new["id"], "장소 이름": new["이름(한국어)"]})
            candidates.append(row)
        log(f"{city}: 시군구 {len(codes)}곳 · 후보 {len(spots)}곳 / 신규 {added}곳 (기준 {date})")
    return candidates, new_rows


def append_rows(path: Path, rows: list[dict]) -> None:
    """tour-places.csv 끝에 붙인다(UTF-8 BOM · CRLF · 17열 그대로). 파일 끝에 줄바꿈이 없으면 먼저 넣는다."""
    if not rows:
        return
    raw = path.read_bytes()
    with open(path, "ab") as f:
        if not raw.endswith(b"\n"):
            f.write(b"\r\n")
        buf = []
        for r in rows:
            cells = []
            for c in COLUMNS:
                v = str(r.get(c, ""))
                cells.append('"' + v.replace('"', '""') + '"' if re.search(r'[",\r\n]', v) else v)
            buf.append(",".join(cells))
        f.write(("\r\n".join(buf) + "\r\n").encode("utf-8"))


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--places", type=Path, default=PLACES_CSV)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--signgu", type=Path, default=SIGNGU_JSON, help="장소 id → 시군구 코드 JSON")
    ap.add_argument("--scope", choices=["all", "home"], default="all", help="all: 장소 표의 모든 지역(기본) · home: 앱 홈 칩 10개 도시")
    ap.add_argument("--regions", nargs="*", help="이 지역(도시)만")
    ap.add_argument("--min-places", type=int, default=1, help="all: 부를 시군구의 최소 장소 수(숙박 제외)")
    ap.add_argument("--top", type=int, default=TOP, help="지역마다 볼 상위 관광지 수(앱 화면과 같은 10, 0이면 전부)")
    ap.add_argument("--date", help="기준 날짜 YYYY-MM-DD(기본 서울 오늘)")
    ap.add_argument("--from-json", type=Path, help="받아 둔 응답 JSON 폴더(네트워크 대신)")
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
    today = a.date or dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d")
    places = read_places(a.places)
    before = len(places)
    signgu = read_signgu(a.signgu)
    if a.scope == "home":
        targets = targets_home(places, a.regions or HOME_CITIES)
    else:
        if not signgu:
            print(f"시군구 코드 파일이 없습니다: {a.signgu} (--scope home 은 코드 파일 없이 돈다)", file=sys.stderr)
            return 2
        targets = targets_all(places, signgu, a.min_places, a.regions)
    print(f"조회: 지역 {len(targets)}곳 · 시군구 {sum(len(t['codes']) for t in targets)}곳")
    candidates, new_rows = collect(api, places, targets, today, a.top, signgu=signgu)

    tag = today.replace("-", "")
    cand_path, new_path = a.out / f"popular_candidates_{tag}.csv", a.out / f"popular_new_rows_{tag}.csv"
    write_csv(cand_path, candidates, ["지역", "순위", "관광지", "시군구", "시군구 코드", "집중률", "기준 날짜", "판정", "장소 id", "장소 이름", "contentid"])
    write_csv(new_path, new_rows, COLUMNS)
    print(f"후보 {len(candidates)}곳: 기존 {sum(r['판정'].startswith('기존') for r in candidates)} · 신규 {len(new_rows)} · 못 찾음 {sum(r['판정'].startswith('못') for r in candidates)}")
    print(f"판정표 {cand_path}\n새 행 {new_path}")
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
