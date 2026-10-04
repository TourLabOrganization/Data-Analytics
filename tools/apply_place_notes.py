"""이미 있는 장소의 설명 끝에 명단 문장을 붙인다(앱 frontend scripts/apply-place-notes.mjs와 같은 규칙).

    python -m tools.apply_place_notes            # 바뀔 행 수만 찍는다
    python -m tools.apply_place_notes --apply    # analysis/tour-places.csv 「설명」 칸을 고친다

  analysis/place_notes.csv  열: id · ko(붙일 한국어 문장) · en · list(식객 · 한식당100선 …)
  - 설명에 같은 문장이 있으면 건너뛰고, 설명이 비면 문장만 적는다
  - 합쳐서 사라진 id는 analysis/place_aliases.csv(drop → keep)로 남긴 장소에 붙인다
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACES = ROOT / "analysis" / "tour-places.csv"
NOTES = ROOT / "analysis" / "place_notes.csv"
ALIASES = ROOT / "analysis" / "place_aliases.csv"


def read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def append_sentence(desc: str | None, sentence: str | None) -> str:
    s = (sentence or "").strip()
    d = desc or ""
    if not s:
        return d
    if not d.strip():
        return s
    if s in d:
        return d
    return f"{d.rstrip()} {s}"


def apply(rows: list[dict], notes: list[dict], aliases: dict[str, str]) -> int:
    by_id = {r["id"]: r for r in rows}
    missing = [n["id"] for n in notes if aliases.get(n["id"], n["id"]) not in by_id]
    if missing:
        raise SystemExit(f"장소 표에 없는 id: {', '.join(missing)}")
    changed = 0
    for n in notes:
        r = by_id[aliases.get(n["id"], n["id"])]
        new = append_sentence(r["설명"], n.get("ko"))
        if new != r["설명"]:
            r["설명"] = new
            changed += 1
    return changed


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    rows = read(PLACES)
    cols = list(rows[0].keys())
    aliases = {r["drop"]: r["keep"] for r in read(ALIASES)}
    n = apply(rows, read(NOTES), aliases)
    print(f"설명 바뀐 장소 {n}곳")
    if a.apply:
        with PLACES.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"썼다: {PLACES}")


if __name__ == "__main__":
    main()
