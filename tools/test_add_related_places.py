# -*- coding: utf-8 -*-
"""tools/add_related_places.py 점검(네트워크 없이). python -m unittest tools.test_add_related_places"""
import csv
import datetime as dt
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools import add_related_places as m
from tools.add_popular_places import JsonDirApi

ROOT = Path(__file__).resolve().parents[1]


def body(items, total=None):
    return {"response": {"header": {"resultCode": "0000"}, "body": {"items": {"item": items}, "totalCount": total if total is not None else len(items)}}}


def row(base, rlte, rank, signgu="47130", lcls="관광지"):
    return {"baseYm": "202608", "tAtsNm": base, "rlteTatsNm": rlte, "rlteRank": str(rank), "rlteSignguCd": signgu, "rlteRegnNm": "경상북도",
            "rlteSignguNm": "경주시", "rlteCtgryLclsNm": lcls, "rlteCtgryMclsNm": "", "rlteCtgrySclsNm": "호텔" if lcls == "숙박" else "역사관광지"}


def search(title, cid, lat, lng, ctype="12", regn="47", sgg="130", addr="경북 경주시 어딘가 1"):
    return {"title": title, "contentid": cid, "contenttypeid": ctype, "mapy": str(lat), "mapx": str(lng), "lDongRegnCd": regn, "lDongSignguCd": sgg, "addr1": addr}


class Rules(unittest.TestCase):
    def test_names_and_filters(self):
        self.assertEqual(m.related_months(dt.date(2026, 10, 3)), ["202608", "202607", "202606"])
        self.assertEqual(m.related_months(dt.date(2026, 1, 15)), ["202511", "202510", "202509"])
        self.assertTrue(m.is_franchise("CGV용산아이파크몰"))
        self.assertTrue(m.is_franchise("맥도날드/신월남부DT점"))
        self.assertFalse(m.is_franchise("CUBE미술관"))
        self.assertFalse(m.is_franchise("마복림떡볶이"))
        self.assertTrue(m.hidden_name("불국사주차장"))
        self.assertEqual(m.related_name("경주 불국사/본점 (석굴암)"), "경주불국사")

    def test_related_stops(self):
        stops = m.related_stops([
            row("불국사", "석굴암", 1), row("첨성대", "석굴암 ", 3), row("대릉원", "석굴암", 2),
            row("불국사", "새전망대", 2), row("불국사", "불국사주차장", 4), row("불국사", "스타벅스/경주보문점", 5),
            row("불국사", "힐튼 경주", 6, lcls="숙박"), row("불국사", "", 7), row("불국사", "코드없는곳", 8, signgu=""),
        ], lambda c: "경주" if c == "47130" else "")
        self.assertEqual([(s["관광지"], s["연계"], s["최고 순위"], s["지역"]) for s in stops],
                         [("석굴암", 3, 1, "경주"), ("새전망대", 1, 2, "경주"), ("힐튼 경주", 1, 6, "경주"), ("코드없는곳", 1, 8, "")])
        self.assertEqual(stops[0]["bases"], ["불국사", "첨성대", "대릉원"])
        self.assertTrue(stops[2]["숙박"])


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.places = self.tmp / "tour-places.csv"
        shutil.copy(ROOT / "analysis" / "tour-places.csv", self.places)
        self.fx = self.tmp / "fx"
        self.fx.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def put(self, name, items, total=None):
        (self.fx / name).write_text(json.dumps(body(items, total), ensure_ascii=False), encoding="utf-8")

    def test_collect_gyeongju(self):
        places = m.read_places(self.places)
        wol = next(p for p in places if p["id"] == "gjx6")  # 월정교
        self.put("related_47130_202608_p1.json", [
            row("불국사", "석굴암", 1), row("불국사", "새전망대", 2), row("첨성대", "새전망대", 1),
            row("대릉원", "신라의밤다리", 2), row("대릉원", "없는곳", 3), row("불국사", "새호텔", 4, lcls="숙박"),
        ])
        self.put("search_새전망대.json", [search("새전망대", "9101", 35.80, 129.30, ctype="14"), search("새전망대", "9102", 35.80, 129.30, regn="26", sgg="350")])
        self.put("search_신라의밤다리.json", [search("신라의밤다리", "9103", float(wol["위도"]) + 0.001, float(wol["경도"]))])
        self.put("search_없는곳.json", [])
        self.put("search_새호텔.json", [search("새호텔", "9104", 35.81, 129.31, ctype="32", addr="경북 경주시 호텔길 1")])
        api = JsonDirApi(self.fx)
        signgu = m.read_signgu(ROOT / "analysis" / "place_signgu.json")
        used, cand, new = m.collect(api, places, signgu, dt.date(2026, 10, 3), log=lambda *_: None, regions=["경주"], apply_signgu=signgu)
        self.assertEqual(used["47130"], "202608")
        self.assertEqual([(c["관광지"], c["판정"]) for c in cand],
                         [("새전망대", "신규"), ("석굴암", "기존(이름)"), ("신라의밤다리", "기존(위치)"), ("없는곳", "못 찾음(관광정보에 없음)"), ("새호텔", "신규")])
        self.assertEqual(cand[1]["장소 id"], "gjx5")
        self.assertEqual(cand[2]["장소 id"], "gjx6")
        self.assertEqual([(r["id"], r["카테고리"], r["지역"], r["권역"]) for r in new], [("pop9101", "herit", "경주", "경주"), ("pop9104", "stay", "경주", "경주")])
        self.assertIn("연관 관광지(연계 2회 · 불국사, 첨성대)", new[0]["출처"])
        self.assertIn("함께 많이 찾는 곳 (연관 2회)", new[0]["설명"])
        self.assertEqual((signgu["pop9101"], signgu["pop9104"]), ("47130", "47130"))
        self.assertEqual(len(new[0]), len(m.COLUMNS))

        # 붙이고 다시 돌리면 contentid로 걸러 신규 0
        before = len(m.read_places(self.places))
        m.append_rows(self.places, new)
        again = m.read_places(self.places)
        _, cand2, new2 = m.collect(api, again, signgu, dt.date(2026, 10, 3), log=lambda *_: None, regions=["경주"])
        self.assertEqual(new2, [])
        self.assertEqual(cand2[0]["판정"], "기존(이름)")
        with open(self.places, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual((len(rows), {len(r) for r in rows}), (before + len(new) + 1, {17}))

    def test_cli_without_apply(self):
        self.put("related_47130_202608_p1.json", [row("불국사", "석굴암", 1)])
        before = self.places.read_bytes()
        out = self.tmp / "out"
        rc = m.main(["--places", str(self.places), "--signgu", str(ROOT / "analysis" / "place_signgu.json"), "--from-json", str(self.fx),
                     "--out", str(out), "--regions", "경주", "--today", "2026-10-03"])
        self.assertEqual(rc, 0)
        self.assertEqual(self.places.read_bytes(), before)
        self.assertTrue(sorted(out.glob("related_candidates_*.csv")) and sorted(out.glob("related_new_rows_*.csv")))


if __name__ == "__main__":
    unittest.main()
