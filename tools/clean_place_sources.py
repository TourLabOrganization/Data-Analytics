"""장소 표 「출처」 칸에서 작업 기록을 지운다(앱 frontend scripts/clean-place-sources.mjs cleanSource와 같은 규칙, 2026-10-04 사용자 요청).

    python -m tools.clean_place_sources            # 바뀔 행 수만 찍는다
    python -m tools.clean_place_sources --apply    # analysis/tour-places.csv 출처 칸을 고친다

지우는 것: 작업 날짜, 「사용자 요청」, 「지도 검증 필요」 · 「확인 필요」, 노선 표기 · 언급 횟수 같은 대조 메모, 「정정」.
남기는 것: 출처 종류(국가유산 보물 소재지(보물 n건) · 열린관광지(연도 선정) · 시티투어 경유지(n개 노선) …), 좌표 근거, 대략 위치.
원본 표(analysis/*_places.csv)의 출처 메모는 그대로 둔다.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACES = ROOT / "analysis" / "tour-places.csv"

RULES: list[tuple[str, str]] = [
    (r"좌표 수기 입력\([^)]*\)", "주소 기준 좌표"),
    (r"사용자 요청\(의령 관광지,[^)]*\)", "의령군 문화관광 자료"),
    (r"사용자 요청\([^)]*\)", ""),
    (r"국가유산 보물 소재지\(보물 (\d+)건,[^)]*\)", r"국가유산 보물 소재지(보물 \1건)"),
    (r"국보 목록 재점검\([^)]*\)", "국가유산 국보 소재지"),
    (r"국보 소재지\([^)]*점검\)", "국가유산 국보 소재지"),
    (r"국보 소장처\([^)]*\)", "국가유산 국보 소장처"),
    (r"열린관광지\((\d{4})년 선정,[^)]*\)", r"열린관광지(\1년 선정)"),
    (r"한국관광공사 연관 관광지\(기존 장소 설명에 \d+회 언급\)", "한국관광공사 연관 관광지"),
    (r"시티투어 경유지\((\d+)개 노선, 노선 표기 「[^」]*」\)", r"시티투어 경유지(\1개 노선)"),
    (r"\s*\((?:지도 )?(?:확인|검증) 필요\)", ""),
    (r"주소 기준으로 좌표 정정", "주소 기준 좌표"),
    (r"좌표로 정정", "좌표"),
    (r"\d{4}-\d{2}-\d{2}\s*", ""),
]


def clean_source(text: str) -> str:
    s = text or ""
    for pat, to in RULES:
        s = re.sub(pat, to, s)
    parts = [re.sub(r"\(\s*\)", "", x).strip() for x in s.split(" · ")]
    return " · ".join(dict.fromkeys(p for p in parts if p))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    with PLACES.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
        cols = list(rows[0].keys())
    n = 0
    for r in rows:
        new = clean_source(r["출처"])
        if new != r["출처"]:
            n += 1
            r["출처"] = new
    print(f"출처 {n}행 정리")
    if a.apply:
        with PLACES.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"썼다: {PLACES}")


if __name__ == "__main__":
    main()
