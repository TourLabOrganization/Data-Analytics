# -*- coding: utf-8 -*-
"""같은 장소가 두 번 들어간 쌍을 하나로 합친다(analysis/same_places.csv: keep · drop · reason).

    python -m tools.merge_same_places            # 합칠 쌍과 옮길 값을 찍는다(파일은 바꾸지 않는다)
    python -m tools.merge_same_places --apply    # tour-places.csv에서 drop 행을 빼고 place_signgu.json에서 drop을 지우고 analysis/place_aliases.csv에 drop → keep을 적는다

입력 표는 앱 frontend scripts/data/same-places.csv와 같은 파일이다(앱은 scripts/merge-same-places.mjs가 같은 쌍을 합친다).
2026-10-03 전수 점검: 같은 도시 · 같은 이름(정규화) 5쌍(수기 장소가 기존 장소와 겹침), 전용 화면 묶음 ↔ 전국 목록 14쌍,
전국 목록 안의 같은 장소 46쌍(이름이 서로를 품고 좌표 700m 안, 눈으로 확인).
2026-10-04 이름 혼용 전수 점검: 이름이 비슷한 쌍 · 150m 안 근접 쌍을 모두 훑어 같은 주소 · 같은 시설로 확인한 16쌍을 더했다
(김녕성세기해변 = 김녕해수욕장, 장항송림산림욕장 → 장항송림자연휴양림 개칭 …).

규칙:
  1. drop 행은 지운다. keep 행의 빈 칸(中文 · 日本語 · 유네스코 · 지정구역 · 설명 · 링크)은 drop 행 값으로 채운다. 그 밖(좌표 · 범주 · 출처)은 keep 그대로.
  2. 파일은 UTF-8 BOM · CRLF · 17열 그대로 두고 지우는 줄과 채운 keep 줄만 바꾼다(한 행 = 한 줄).
  3. drop → keep 표(analysis/place_aliases.csv)는 분석 결과 · 교차표(datalab_place_crosswalk.csv 등)에 남은 옛 id를 남긴 장소로 읽을 때 쓴다.
     이미 합친 쌍(drop이 없고 별명 표에 있음)은 건너뛰어 여러 번 돌려도 같다.
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

from tools.add_popular_places import COLUMNS, PLACES_CSV, SIGNGU_JSON, read_signgu, write_signgu

ROOT = Path(__file__).resolve().parents[1]
SAME_CSV = ROOT / "analysis" / "same_places.csv"
ALIASES_CSV = ROOT / "analysis" / "place_aliases.csv"
FILL_COLUMNS = ("中文", "日本語", "유네스코", "지정구역", "설명", "링크")


def read_pairs(path: Path) -> list[tuple[str, str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if rows and not {"keep", "drop"} <= set(rows[0]):
        raise ValueError(f"{path}: keep · drop 열이 없다")
    return [(r["keep"].strip(), r["drop"].strip(), (r.get("reason") or "").strip()) for r in rows if (r.get("keep") or "").strip()]


def read_aliases(path: Path) -> dict[str, tuple[str, str]]:
    """drop → (keep, reason)"""
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["drop"]: (r["keep"], r.get("reason", "")) for r in csv.DictReader(f)}


def write_aliases(path: Path, aliases: dict[str, tuple[str, str]]) -> None:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["drop", "keep", "reason"])
    for drop in sorted(aliases):
        keep, reason = aliases[drop]
        w.writerow([drop, keep, reason])
    path.write_text("﻿" + buf.getvalue(), encoding="utf-8")


def fill_row(keep: dict, drop: dict) -> list[str]:
    """keep의 빈 칸을 drop 값으로 채운다. 채운 열 이름을 돌려준다"""
    filled = []
    for col in FILL_COLUMNS:
        if not (keep.get(col) or "").strip() and (drop.get(col) or "").strip():
            keep[col] = drop[col]
            filled.append(col)
    return filled


def merge(places: list[dict], pairs, aliases: dict[str, tuple[str, str]]):
    """(남는 행, 바뀐 keep id 집합, 로그). places 행은 제자리에서 채운다"""
    by_id = {p["id"]: p for p in places}
    dropped: set[str] = set()
    changed: set[str] = set()
    log: list[str] = []
    for keep_id, drop_id, reason in pairs:
        keep = by_id.get(keep_id)
        if keep is None:
            raise ValueError(f"keep {keep_id}가 장소 표에 없다 ({reason})")
        drop = by_id.get(drop_id)
        if drop is None:
            if drop_id in aliases:
                continue
            raise ValueError(f"drop {drop_id}가 장소 표에 없다 ({reason})")
        filled = fill_row(keep, drop)
        if filled:
            changed.add(keep_id)
        dropped.add(drop_id)
        del by_id[drop_id]
        aliases[drop_id] = (keep_id, reason)
        log.append(f"{keep_id} {keep['이름(한국어)']} ← {drop_id} {drop['이름(한국어)']}" + (f" (채운 열: {' · '.join(filled)})" if filled else ""))
    # 사슬(a → b, b → c)은 끝까지
    for d, (k, r) in list(aliases.items()):
        seen = {d}
        while k in aliases and k not in seen:
            seen.add(k)
            k = aliases[k][0]
        aliases[d] = (k, r)
    return [p for p in places if p["id"] not in dropped], changed, log


def rewrite_places(path: Path, keep_rows: dict[str, dict], dropped: set[str]) -> None:
    """지우는 줄은 빼고, 채운 keep 줄은 다시 쓴다. 나머지 줄은 바이트 그대로(BOM · CRLF 유지)"""
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    lines = text.split("\r\n")
    out = []
    for i, line in enumerate(lines):
        pid = line.split(",", 1)[0]
        if i > 0 and pid in dropped:
            continue
        if i > 0 and pid in keep_rows:
            buf = io.StringIO()
            csv.writer(buf, lineterminator="").writerow([keep_rows[pid].get(c, "") for c in COLUMNS])
            line = buf.getvalue()
        out.append(line)
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + "\r\n".join(out).encode("utf-8"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", type=Path, default=SAME_CSV, help="같은 장소 쌍 표(keep · drop · reason)")
    ap.add_argument("--places", type=Path, default=PLACES_CSV)
    ap.add_argument("--signgu", type=Path, default=SIGNGU_JSON)
    ap.add_argument("--aliases", type=Path, default=ALIASES_CSV, help="drop → keep 표")
    ap.add_argument("--apply", action="store_true", help="파일을 바꾼다")
    args = ap.parse_args(argv)

    with open(args.places, encoding="utf-8-sig", newline="") as f:
        places = list(csv.DictReader(f))
    if places and [c for c in COLUMNS if c not in places[0]]:
        raise ValueError("tour-places.csv 칼럼 누락")
    pairs = read_pairs(args.csv)
    aliases = read_aliases(args.aliases)
    before = len(places)
    kept, changed, log = merge(places, pairs, aliases)
    for line in log:
        print("  " + line)
    dropped = {p["id"] for p in places} - {p["id"] for p in kept}
    print(f"쌍 {len(pairs)} · 합침 {len(log)} · 장소 {before} → {len(kept)}행 · 채운 keep {len(changed)} · 별명 {len(aliases)}")
    if not args.apply:
        print("--apply 없음: 파일은 그대로")
        return 0
    if dropped:
        rewrite_places(args.places, {p["id"]: p for p in kept if p["id"] in changed}, dropped)
        codes = read_signgu(args.signgu)
        for d in dropped:
            codes.pop(d, None)
        write_signgu(args.signgu, codes)
    write_aliases(args.aliases, aliases)
    print(f"썼다: {args.places} · {args.signgu} · {args.aliases}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
