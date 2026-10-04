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

    def test_pinned_name_beats_rule(self):
        # 수기 대조표: 규칙으로 못 잇는 이름(팔각정북악스카이)을 적힌 장소로. 다른 도시 키는 무시
        places = m.read_places(self.places)
        pins = {"서울|팔각정북악스카이": "kdx35"}
        hit = m.match_by_name({"name": "팔각정 북악스카이", "city": "서울"}, places, pins)
        self.assertEqual(hit["id"], "kdx35")
        self.assertIsNone(m.match_by_name({"name": "팔각정 북악스카이", "city": "부산"}, places, pins))
        pins_file = m.read_match()
        for key, pid in pins_file.items():
            city = key.split("|")[0]
            place = next((p for p in places if p["id"] == pid), None)
            self.assertIsNotNone(place, key)
            self.assertEqual(place["지역"], city, key)
            self.assertNotEqual(place["카테고리"], "stay", key)

    def test_boundary_place_loose_pick(self):
        # 같은 시군구 관광정보가 없으면 같은 시도 · 이름 같은 것만(품는 이름은 안 됨). 다른 시도는 뺀다
        items = [{"contentid": "1", "title": "1100고지 습지", "contenttypeid": "12", "lDongRegnCd": "50", "lDongSignguCd": "130"},
                 {"contentid": "2", "title": "1100고지 휴게소", "contenttypeid": "39", "lDongRegnCd": "50", "lDongSignguCd": "130"},
                 {"contentid": "3", "title": "1100고지 습지", "contenttypeid": "12", "lDongRegnCd": "47", "lDongSignguCd": "130"}]
        self.assertIsNone(m.pick_spot_item(items, {"name": "1100고지습지", "signgu": "50110"}))
        self.assertEqual(m.pick_spot_item_loose(items, {"name": "1100고지습지", "signgu": "50110"})["contentid"], "1")
        self.assertIsNone(m.pick_spot_item_loose(items, {"name": "1100고지", "signgu": "50110"}))
        self.assertIsNone(m.pick_spot_item_loose(items, {"name": "1100고지습지", "signgu": ""}))
        # 다른 시도(47)만 남으면 없음, 시도 코드가 빈 항목은 받는다
        self.assertIsNone(m.pick_spot_item_loose(items[2:], {"name": "1100고지습지", "signgu": "50110"}))
        blank = [dict(items[0], contentid="4", lDongRegnCd="")]
        self.assertEqual(m.pick_spot_item_loose(blank, {"name": "1100고지습지", "signgu": "50110"})["contentid"], "4")

    def test_boundary_collect_requires_name_near(self):
        # 같은 시군구 관광정보가 없을 때: 시도 안 같은 이름 관광정보 좌표 1km 안에서 이름도 맞는(글자쌍 절반 겹침) 장소만.
        # 「동궁월지」는 이름 점수로는 「동궁과 월지」와 안 맞아(0점) 이름 대조를 지나고, 위치 + 글자 겹침(0.57)으로 gj3에 잇는다.
        # 「다른구 시장」은 동궁과 월지 바로 옆이지만 이름이 안 맞아 잇지 않고, 새 장소로도 만들지 않는다
        places = m.read_places(self.places)
        pond = next(p for p in places if p["id"] == "gj3")  # 동궁과 월지
        lat, lng = float(pond["위도"]), float(pond["경도"])
        self.put("crowd_47130_p1.json", [crowd("동궁월지", "47130", 40), crowd("다른구 시장", "47130", 30)])
        self.put("search_동궁월지.json", [search("동궁월지", "1001", lat + 0.001, lng, sgg="111")])
        self.put("search_다른구 시장.json", [search("다른구 시장", "2002", lat + 0.0005, lng, sgg="111")])
        api = m.JsonDirApi(self.fx)
        cand, new = m.collect(api, places, m.targets_home(places, ["경주"]), "2026-10-01", 10, log=lambda *_: None)
        self.assertEqual([(c["판정"], c["장소 id"]) for c in cand],
                         [("기존(위치)", "gj3"), ("못 찾음(관광정보에 없음)", "")])
        self.assertEqual(new, [])

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
        cand, new = m.collect(api, places, m.targets_home(places, ["경주"]), "2026-10-01", 10, log=lambda *_: None)
        self.assertEqual([c["판정"] for c in cand], ["기존(이름)", "기존(위치)", "신규", "못 찾음(관광정보에 없음)"])
        self.assertEqual(cand[1]["장소 id"], tower["id"])
        self.assertEqual(len(new), 1)
        row = new[0]
        self.assertEqual((row["id"], row["권역"], row["지역"], row["카테고리"], row["추천 체류(분)"]), ("pop2002", "경주", "경주", "heal", "60"))
        self.assertIn("contentid 2002", row["출처"])
        self.assertEqual(len(row), len(m.COLUMNS))

        # 붙이고 다시 읽으면 (collect가 새 행을 붙인 장소 수 + 머리글)행 · 17열 · CRLF, 다시 돌리면 contentid로 걸러 신규 0
        before = len(places)
        m.append_rows(self.places, new)
        raw = self.places.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf") and raw.endswith(b"\r\n") and b"\r\npop2002,\xea\xb2\xbd\xec\xa3\xbc" in raw)
        with open(self.places, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual((len(rows), {len(r) for r in rows}), (before + 1, {17}))
        again = m.read_places(self.places)
        cand2, new2 = m.collect(api, again, m.targets_home(again, ["경주"]), "2026-10-01", 10, log=lambda *_: None)
        self.assertEqual(new2, [])
        self.assertEqual(cand2[2]["판정"], "기존(이름)")  # 이제 이름으로 바로 맞는다
        self.assertEqual([p["id"] for p in again if p["id"].startswith("pop")], ["pop2002"])

    def test_old_code_fallback_and_top(self):
        # 강릉(51150): 새 코드로 그 시군구 행이 없으면 옛 코드 42150으로 받고, 상위 top만 본다
        self.put("crowd_51150_p1.json", [crowd("우도", "50130", 90, nm="서귀포시")])  # 다른 시군구 행만 → 무시
        self.put("crowd_42150_p1.json", [crowd(f"가상관광지{i}", "42150", 10 + i, nm="강릉시") for i in range(12)])
        for i in range(12):
            self.put(f"search_가상관광지{i}.json", [search(f"가상관광지{i}", str(3000 + i), 37.75 + i * 0.01, 128.90, regn="51", sgg="150")])
        places = m.read_places(self.places)
        cand, new = m.collect(m.JsonDirApi(self.fx), places, m.targets_home(places, ["강릉"]), "2026-10-01", 10, log=lambda *_: None)
        self.assertEqual(len(cand), 10)
        self.assertEqual([c["관광지"] for c in cand][:2], ["가상관광지11", "가상관광지10"])
        self.assertEqual(all(r["권역"] == "전국" and r["지역"] == "강릉" for r in new), True)
        self.assertEqual(len(new), 10)

    def test_targets_all_covers_every_region(self):
        places = m.read_places(self.places)
        signgu = m.read_signgu(ROOT / "analysis" / "place_signgu.json")
        targets = m.targets_all(places, signgu)
        regions = {p["지역"] for p in places if p["카테고리"] != "stay"}
        self.assertEqual({t["region"] for t in targets}, regions)  # 숙박만 있는 지역은 없으므로 124곳 전부
        codes = [c for t in targets for c in t["codes"]]
        self.assertEqual(len(codes), len(set(codes)))  # 한 시군구는 한 지역에만
        gj = next(t for t in targets if t["region"] == "경주")
        self.assertEqual(gj["codes"], ["47130"])
        busan = next(t for t in targets if t["region"] == "부산")
        self.assertIn("26710", busan["codes"])  # 기장군은 부산(17곳)에, 양산이 아니라
        self.assertNotIn("26710", next(t for t in targets if t["region"] == "양산")["codes"])
        self.assertEqual(m.targets_all(places, signgu, regions=["속초"])[0]["codes"], ["51210"])
        home = m.targets_home(places, ["서울"])[0]
        self.assertEqual(home["codes"], ["11110", "11440", "11560", "11140"])  # 종로 · 마포 · 영등포 · 중구(국보 소재지 추가 뒤)
        self.assertEqual(m.targets_home(places, ["대구"])[0]["codes"], ["27710", "27260", "27720", "27290"])
        self.assertEqual(m.targets_home(places, ["춘천"])[0]["codes"], ["51110"])

    def test_all_scope_adds_signgu_code_and_region_macro(self):
        # 전국 범위: 양평(ro 행, 권역 전국)에 새 장소가 생기면 권역은 그 지역 값, 코드는 관광정보 법정동 코드로 place_signgu에 들어간다
        signgu = m.read_signgu(ROOT / "analysis" / "place_signgu.json")
        places = m.read_places(self.places)
        targets = m.targets_all(places, signgu, regions=["양평"])
        code = targets[0]["codes"][0]
        self.put(f"crowd_{code}_p1.json", [crowd("가상양평관광지", code, 33, nm="양평군")])
        self.put("search_가상양평관광지.json", [search("가상양평관광지", "7007", 37.60, 127.60, ctype="14", regn=code[:2], sgg=code[2:], addr="경기 양평군 어딘가 2")])
        cand, new = m.collect(m.JsonDirApi(self.fx), places, targets, "2026-10-01", 10, log=lambda *_: None, signgu=signgu)
        self.assertEqual([c["판정"] for c in cand], ["신규"])
        self.assertEqual((new[0]["지역"], new[0]["권역"], new[0]["카테고리"]), ("양평", "전국", "herit"))
        self.assertEqual(signgu[new[0]["id"]], code)
        out = self.tmp / "sg.json"
        m.write_signgu(out, signgu)
        self.assertEqual(m.read_signgu(out), signgu)

    def test_cli_without_apply_leaves_file(self):
        self.put("crowd_51210_p1.json", [crowd("속초해수욕장", "51210", 70, nm="속초시")])
        before = self.places.read_bytes()
        out = self.tmp / "out"
        rc = m.main(["--places", str(self.places), "--from-json", str(self.fx), "--scope", "home", "--regions", "속초", "--date", "2026-10-01", "--out", str(out)])
        self.assertEqual(rc, 0)
        self.assertEqual(self.places.read_bytes(), before)
        self.assertTrue((out / "popular_candidates_20261001.csv").is_file() and (out / "popular_new_rows_20261001.csv").is_file())


if __name__ == "__main__":
    unittest.main()
