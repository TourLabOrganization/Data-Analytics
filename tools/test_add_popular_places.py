# -*- coding: utf-8 -*-
"""tools/add_popular_places.py 점검(네트워크 없이). python -m unittest tools.test_add_popular_places"""
import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools import add_popular_places as m

ROOT = Path(__file__).resolve().parents[1]


def body(items, total=None):
    return {"response": {"header": {"resultCode": "0000"}, "body": {"items": {"item": items}, "totalCount": total if total is not None else len(items)}}}


def crowd(name, code, rate, ymd="20261001", nm="경주시"):
    return {"tAtsNm": name, "signguCd": code, "signguNm": nm, "baseYmd": ymd, "cnctrRate": str(rate)}


def search(title, cid, lat, lng, ctype="12", regn="47", sgg="130", addr="경북 경주시 어딘가 1"):
    return {"title": title, "contentid": cid, "contenttypeid": ctype, "mapy": str(lat), "mapx": str(lng),
            "lDongRegnCd": regn, "lDongSignguCd": sgg, "addr1": addr}


class NameRules(unittest.TestCase):
    def test_name_score_like_app(self):
        self.assertEqual(m.name_score("경포해수욕장", "경포해변", "강릉"), 3)
        self.assertEqual(m.name_score("전주한옥마을", "한옥마을", "전주"), 3)
        self.assertEqual(m.name_score("불국사", "불국사 (경주)", ""), 3)
        self.assertEqual(m.name_score("첨성대", "첨성대 야경 투어", ""), 2)
        self.assertEqual(m.name_score("해안", "경포해변", ""), 0)  # 맞춘 끝말(해변)만 겹치면 아님
        self.assertEqual(m.name_score("대릉원", "동궁과 월지", ""), 0)

    def test_category(self):
        self.assertEqual(m.kto_category({"contenttypeid": "14"}), "herit")
        self.assertEqual(m.kto_category({"contenttypeid": "39"}), "food")
        self.assertEqual(m.kto_category({"contenttypeid": "28"}), "activity")
        self.assertEqual(m.kto_category({"contenttypeid": "12", "title": "경포해변"}), "sea")
        self.assertEqual(m.kto_category({"contenttypeid": "12", "title": "오죽헌"}), "heal")

    def test_rank_uses_today_then_earliest(self):
        items = [crowd("a", "47130", 10, "20260930"), crowd("b", "47130", 20, "20261002"), crowd("c", "47130", 30, "20261003")]
        date, spots = m.rank_spots(items, "2026-10-01")
        self.assertEqual((date, [s["name"] for s in spots]), ("2026-10-02", ["b"]))
        items.append(crowd("d", "47130", 5, "20261001"))
        date, spots = m.rank_spots(items, "2026-10-01")
        self.assertEqual((date, [s["name"] for s in spots]), ("2026-10-01", ["d"]))


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

    def test_match_existing_new_and_missing(self):
        # 경주시 집중률: 불국사(기존 이름), 월정교 야경(월정교와 250m 안 → 위치), 가상의 새 관광지(신규), 아무 데도 없는 곳(못 찾음)
        self.put("crowd_47130_p1.json", [crowd("불국사", "47130", 50), crowd("신라의 밤 야경", "47130", 40),
                                          crowd("새로생긴전망대", "47130", 30), crowd("없는곳", "47130", 20)])
        places = m.read_places(self.places)
        tower = next(p for p in places if p["id"] == "gjx6")  # 월정교
        self.put("search_신라의 밤 야경.json", [search("신라의 밤 야경", "1001", float(tower["위도"]) + 0.001, float(tower["경도"]))])
        self.put("search_새로생긴전망대.json", [search("새로생긴전망대", "2002", 35.80, 129.30, ctype="12"),
                                            search("새로생긴전망대 (다른 시군구)", "2003", 35.80, 129.30, regn="26", sgg="350")])
        self.put("search_없는곳.json", [])
        api = m.JsonDirApi(self.fx)
        cand, new = m.collect(api, places, ["경주"], "2026-10-01", 10, log=lambda *_: None)
        self.assertEqual([c["판정"] for c in cand], ["기존(이름)", "기존(위치)", "신규", "못 찾음(관광정보에 없음)"])
        self.assertEqual(cand[1]["장소 id"], tower["id"])
        self.assertEqual(len(new), 1)
        row = new[0]
        self.assertEqual((row["id"], row["권역"], row["지역"], row["카테고리"], row["추천 체류(분)"]), ("pop1", "경주", "경주", "heal", "60"))
        self.assertIn("contentid 2002", row["출처"])
        self.assertEqual(len(row), len(m.COLUMNS))

        # 붙이고 다시 읽으면 3,110행 · 17열 · CRLF, 다시 돌리면 contentid로 걸러 신규 0
        m.append_rows(self.places, new)
        raw = self.places.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf") and raw.endswith(b"\r\n") and b"\r\npop1,\xea\xb2\xbd\xec\xa3\xbc" in raw)
        with open(self.places, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual((len(rows), {len(r) for r in rows}), (3111, {17}))
        again = m.read_places(self.places)
        cand2, new2 = m.collect(api, again, ["경주"], "2026-10-01", 10, log=lambda *_: None)
        self.assertEqual(new2, [])
        self.assertEqual(cand2[2]["판정"], "기존(이름)")  # 이제 이름으로 바로 맞는다
        self.assertEqual(m.next_id(again), 2)

    def test_old_code_fallback_and_top(self):
        # 강릉(51150): 새 코드로 그 시군구 행이 없으면 옛 코드 42150으로 받고, 상위 top만 본다
        self.put("crowd_51150_p1.json", [crowd("우도", "50130", 90, nm="서귀포시")])  # 다른 시군구 행만 → 무시
        self.put("crowd_42150_p1.json", [crowd(f"가상관광지{i}", "42150", 10 + i, nm="강릉시") for i in range(12)])
        for i in range(12):
            self.put(f"search_가상관광지{i}.json", [search(f"가상관광지{i}", str(3000 + i), 37.75 + i * 0.01, 128.90, regn="51", sgg="150")])
        places = m.read_places(self.places)
        cand, new = m.collect(m.JsonDirApi(self.fx), places, ["강릉"], "2026-10-01", 10, log=lambda *_: None)
        self.assertEqual(len(cand), 10)
        self.assertEqual([c["관광지"] for c in cand][:2], ["가상관광지11", "가상관광지10"])
        self.assertEqual(all(r["권역"] == "전국" and r["지역"] == "강릉" for r in new), True)
        self.assertEqual(len(new), 10)

    def test_cli_without_apply_leaves_file(self):
        self.put("crowd_51210_p1.json", [crowd("속초해수욕장", "51210", 70, nm="속초시")])
        before = self.places.read_bytes()
        out = self.tmp / "out"
        rc = m.main(["--places", str(self.places), "--from-json", str(self.fx), "--cities", "속초", "--date", "2026-10-01", "--out", str(out)])
        self.assertEqual(rc, 0)
        self.assertEqual(self.places.read_bytes(), before)
        self.assertTrue((out / "popular_candidates_20261001.csv").is_file() and (out / "popular_new_rows_20261001.csv").is_file())


if __name__ == "__main__":
    unittest.main()
