# -*- coding: utf-8 -*-
"""tools/add_odii_places.py 점검(네트워크 없이). python -m unittest tools.test_add_odii_places"""
import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools import add_odii_places as m
from tools.add_popular_places import JsonDirApi

ROOT = Path(__file__).resolve().parents[1]


def body(items, total=None):
    return {"response": {"header": {"resultCode": "0000"}, "body": {"items": {"item": items}, "totalCount": total if total is not None else len(items)}}}


def theme(tid, title, lat, lng, addr1, addr2, cat=""):
    return {"tid": tid, "tlid": "1", "themeCategory": cat, "addr1": addr1, "addr2": addr2, "title": title, "mapX": str(lng), "mapY": str(lat), "langCode": "ko"}


def search(title, cid, lat, lng, ctype="12", regn="47", sgg="130", addr="경북 경주시 어딘가 1"):
    return {"title": title, "contentid": cid, "contenttypeid": ctype, "mapy": str(lat), "mapx": str(lng), "lDongRegnCd": regn, "lDongSignguCd": sgg, "addr1": addr}


class Rules(unittest.TestCase):
    def test_region_from_address(self):
        self.assertEqual(m.odii_region("경상북도", "경주시"), "경주")
        self.assertEqual(m.odii_region("서울특별시", "종로구"), "서울")
        self.assertEqual(m.odii_region("광주광역시", "동구"), "광주")
        self.assertEqual(m.odii_region("경기도", "광주시"), "경기광주")
        self.assertEqual(m.odii_region("강원특별자치도", "고성군"), "고성(강원)")
        self.assertEqual(m.odii_region("경상남도", "고성군"), "고성")
        self.assertEqual(m.odii_region("제주특별자치도", "서귀포시"), "제주")
        self.assertEqual(m.odii_region("", ""), "")

    def test_rule_category(self):
        self.assertEqual(m.rule_category("경포해변"), "sea")
        self.assertEqual(m.rule_category("불국사"), "herit")
        self.assertEqual(m.rule_category("아부오름"), "heal")
        self.assertEqual(m.rule_category("경주월드"), "activity")
        self.assertEqual(m.rule_category("서문시장"), "food")
        self.assertEqual(m.rule_category("이름없음"), "herit")


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

    def test_match_and_add(self):
        places = m.read_places(self.places)
        wol = next(p for p in places if p["id"] == "gjx6")  # 월정교
        self.put("odii_ko_p1.json", [
            theme("2", "경주 불국사", 35.7923, 129.3317, "경상북도", "경주시", "신라 역사 여행"),  # 기존(이름)
            theme("3", "신라의 밤 다리", float(wol["위도"]) + 0.001, float(wol["경도"]), "경상북도", "경주시"),  # 기존(위치)
            theme("4", "새해설전망대", 35.80, 129.30, "경상북도", "경주시"),  # 신규 · 관광정보 있음 → pop
            theme("5", "새해설오름", 33.40, 126.60, "제주특별자치도", "서귀포시"),  # 신규 · 관광정보 없음 → odii, heal
            theme("6", "주소없는곳", 35.80, 129.31, "", ""),  # 지역은 가까운 장소(경주)
            theme("7", "바다 한가운데", 33.0, 124.5, "", ""),  # 30km 안 장소 없음 → 건너뜀(34.0 · 126.0은 전남 섬 해수욕장이 들어와 30km 안이 됐다, 2026-10-04)
        ])
        self.put("search_새해설전망대.json", [search("새해설전망대", "9001", 35.8005, 129.3005, ctype="14")])
        self.put("search_새해설오름.json", [])
        self.put("search_주소없는곳.json", [search("주소없는곳", "9002", 35.0, 129.0)])  # 1km 밖 → 못 씀
        api = JsonDirApi(self.fx)
        signgu = m.read_signgu(ROOT / "analysis" / "place_signgu.json")
        cand, new = m.collect(api, places, log=lambda *_: None, signgu=signgu)
        self.assertEqual([c["판정"] for c in cand], ["기존(이름)", "기존(위치)", "신규", "신규", "신규", "지역 없음(건너뜀)"])
        self.assertEqual(cand[0]["장소 id"], "gjx1")
        self.assertEqual(cand[1]["장소 id"], "gjx6")
        self.assertEqual(cand[4]["지역 근거"], "가까운 장소")
        self.assertEqual([r["id"] for r in new], ["pop9001", "odii5", "odii6"])
        self.assertEqual((new[0]["카테고리"], new[0]["지역"], new[0]["권역"], new[0]["위도"]), ("herit", "경주", "경주", "35.80050"))
        self.assertEqual((new[1]["카테고리"], new[1]["지역"], new[1]["권역"]), ("heal", "제주", "전국"))
        self.assertIn("오디 tid 5", new[1]["출처"])
        self.assertEqual((signgu["pop9001"], signgu["odii5"]), ("47130", ""))
        self.assertEqual(len(new[0]), len(m.COLUMNS))

        # 붙이고 다시 돌리면 tid로 걸러 신규 0
        before = len(m.read_places(self.places))
        m.append_rows(self.places, new)
        again = m.read_places(self.places)
        cand2, new2 = m.collect(api, again, log=lambda *_: None)
        self.assertEqual(new2, [])
        self.assertEqual([c["판정"] for c in cand2][2:5], ["기존(tid)"] * 3)
        with open(self.places, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual((len(rows), {len(r) for r in rows}), (before + len(new) + 1, {17}))

    def test_cli_without_apply(self):
        self.put("odii_ko_p1.json", [theme("2", "경주 불국사", 35.7923, 129.3317, "경상북도", "경주시")])
        before = self.places.read_bytes()
        out = self.tmp / "out"
        rc = m.main(["--places", str(self.places), "--signgu", str(ROOT / "analysis" / "place_signgu.json"), "--from-json", str(self.fx), "--out", str(out)])
        self.assertEqual(rc, 0)
        self.assertEqual(self.places.read_bytes(), before)
        self.assertTrue(sorted(out.glob("odii_candidates_*.csv")) and sorted(out.glob("odii_new_rows_*.csv")))


if __name__ == "__main__":
    unittest.main()
