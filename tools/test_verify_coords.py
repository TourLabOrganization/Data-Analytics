# -*- coding: utf-8 -*-
"""tools/verify_coords.py 점검(네트워크 없이). python -m unittest tools.test_verify_coords"""
import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools import verify_coords as v
from tools.add_popular_places import JsonDirApi

ROOT = Path(__file__).resolve().parents[1]


def body(items):
    return {"response": {"header": {"resultCode": "0000"}, "body": {"items": {"item": items}, "totalCount": len(items)}}}


def search(title, cid, lat, lng, regn="47", sgg="130", ctype="12"):
    return {"title": title, "contentid": cid, "contenttypeid": ctype, "mapy": str(lat), "mapx": str(lng), "lDongRegnCd": regn, "lDongSignguCd": sgg}


class VerifyCoords(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.fx = self.tmp / "fx"
        self.fx.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def put(self, name, items):
        (self.fx / name).write_text(json.dumps(body(items), ensure_ascii=False), encoding="utf-8")

    def test_match_difference_and_missing(self):
        places = v.read_places(ROOT / "analysis" / "tour-places.csv")
        by = {p["id"]: p for p in places}
        bul, mus = by["gjx1"], by["gjx4"]  # 불국사 · 국립경주박물관
        self.put("search_불국사.json", [search("불국사", "126508", float(bul["위도"]) + 0.0005, float(bul["경도"]))])
        self.put("search_국립경주박물관.json", [search("국립경주박물관", "126461", float(mus["위도"]) + 0.02, float(mus["경도"]))])
        # 다른 시군구 항목만 있으면 못 찾음
        self.put("search_첨성대.json", [search("첨성대", "9", 35.83, 129.21, regn="26", sgg="350")])
        api = JsonDirApi(self.fx)
        r1 = v.check_place(api, bul, "47130", log=lambda *_: None)
        r2 = v.check_place(api, mus, "47130", log=lambda *_: None)
        r3 = v.check_place(api, by["gjx3"], "47130", log=lambda *_: None)
        self.assertEqual((r1["판정"], r1["contentid"]), ("일치", "126508"))
        self.assertLess(int(r1["거리(m)"]), 300)
        self.assertEqual(r2["판정"], "차이")
        self.assertGreater(int(r2["거리(m)"]), 2000)
        self.assertEqual(r3["판정"], "못 찾음")

    def test_city_prefix_query_and_cli(self):
        places = v.read_places(ROOT / "analysis" / "tour-places.csv")
        p = next(x for x in places if x["이름(한국어)"].startswith("경주 ") and x["카테고리"] != "stay")
        rest = p["이름(한국어)"][len("경주 "):]
        self.put(f"search_{rest}.json", [search(rest, "777", float(p["위도"]), float(p["경도"]))])
        out = self.tmp / "out"
        rc = v.main(["--from-json", str(self.fx), "--regions", "경주", "--skip-cat", "stay", "food", "--out", str(out)])
        self.assertEqual(rc, 0)
        files = sorted(out.glob("coord_check_*.csv"))
        self.assertEqual(len(files), 1)
        rows = list(csv.DictReader(open(files[0], encoding="utf-8-sig")))
        self.assertTrue(all(r["지역"] == "경주" and r["범주"] not in ("stay", "food") for r in rows))
        hit = next(r for r in rows if r["장소ID"] == p["id"])
        self.assertEqual((hit["판정"], hit["contentid"]), ("일치", "777"))
        self.assertTrue(sorted(out.glob("coord_fix_*.csv")))


if __name__ == "__main__":
    unittest.main()
