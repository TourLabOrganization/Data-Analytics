# -*- coding: utf-8 -*-
"""tools/add_manual_places.py 점검. python -m unittest tools.test_add_manual_places"""
import unittest

from tools import add_manual_places as m
from tools.add_popular_places import COLUMNS


def place(pid, region, ko, lat, lng, cat="herit", stay="60", macro="경주"):
    p = {c: "" for c in COLUMNS}
    p.update({"id": pid, "권역": macro, "지역": region, "이름(한국어)": ko, "카테고리": cat, "위도": str(lat), "경도": str(lng), "추천 체류(분)": stay})
    return p


POOL = [
    place("gj1", "경주", "효우당", 35.8923, 129.1786, cat="stay", stay="180"),
    place("gj2", "경주", "첨성대", 35.8347, 129.219, stay="40"),
    place("gj3", "경주", "대릉원", 35.8389, 129.2126, stay="80"),
]


def row(**over):
    r = {"region": "경주", "stopName": "새정원", "tours": "2", "ko": "새정원", "en": "Sae Garden", "cat": "heal",
         "lat": "35.9000", "lng": "129.3000", "signgu": "47130", "muni": "경주시", "desc": "새로 적은 정원", "descEn": "A newly listed garden"}
    r.update(over)
    return r


class ManualId(unittest.TestCase):
    def test_same_as_app(self):
        # 앱 scripts/add-manual-places.mjs manualId("경주", "새정원")와 같은 값
        self.assertEqual(m.manual_id("경주", "새정원"), "ctm" + __import__("hashlib").sha1("경주|새정원".encode()).hexdigest()[:8])
        self.assertRegex(m.manual_id("경주", "새정원"), r"^ctm[0-9a-f]{8}$")
        self.assertNotEqual(m.manual_id("경주", "새정원"), m.manual_id("부산", "새정원"))


class ManualRows(unittest.TestCase):
    def test_new_row_fields(self):
        new, verdicts = m.manual_rows([row()], POOL, date="2026-10-03")
        self.assertEqual([v["판정"] for v in verdicts], ["신규"])
        self.assertEqual(len(new), 1)
        n = new[0]
        self.assertEqual(n["id"], m.manual_id("경주", "새정원"))
        self.assertEqual((n["권역"], n["지역"], n["이름(한국어)"], n["English"], n["카테고리"]), ("경주", "경주", "새정원", "Sae Garden", "heal"))
        self.assertEqual((n["위도"], n["경도"], n["추천 체류(분)"]), ("35.90000", "129.30000", "60"))
        self.assertEqual(n["출처"], "시티투어 경유지(2개 노선, 노선 표기 「새정원」) · 좌표 수기 입력(지도 검증 필요, 2026-10-03)")
        self.assertEqual(n["설명"], "새로 적은 정원")
        self.assertEqual(list(n), COLUMNS)

    def test_median_stay_and_default_desc(self):
        new, _ = m.manual_rows([row(cat="herit", desc="")], POOL)
        self.assertEqual(new[0]["추천 체류(분)"], "60")  # herit 중앙값 (40, 80) → 60
        self.assertEqual(new[0]["설명"], "경주 시티투어 경유지(2개 노선)")

    def test_skips(self):
        rows = [
            row(ko="첨성대 옆", lat="35.8348", lng="129.2195"),  # 250m 안
            row(),
            row(ko="새정원", stopName="새정원(중복)"),  # 같은 id
            row(ko="좌표없음", lat=""),
            row(ko="먼곳", lat="35.9001", lng="129.3001"),  # 방금 넣은 새정원 옆
        ]
        new, verdicts = m.manual_rows(rows, POOL)
        self.assertEqual([n["이름(한국어)"] for n in new], ["새정원"])
        self.assertEqual([v["판정"] for v in verdicts], ["기존(위치)", "신규", "기존(id)", "빈 이름 · 지역 · 좌표", "기존(위치)"])
        self.assertEqual(verdicts[0]["장소 id"], "gj2")
        self.assertEqual(verdicts[4]["장소 이름"], "새정원")

    def test_source_column(self):
        new, _ = m.manual_rows([row(source="한국관광공사 연관 관광지(기존 장소 설명에 3회 언급)")], POOL, date="2026-10-03")
        self.assertEqual(new[0]["출처"], "한국관광공사 연관 관광지(기존 장소 설명에 3회 언급) · 좌표 수기 입력(지도 검증 필요, 2026-10-03)")

    def test_near_ok(self):
        near = row(ko="첨성대 옆", lat="35.8348", lng="129.2195")
        self.assertEqual(m.manual_rows([near], POOL)[0], [])
        new, verdicts = m.manual_rows([dict(near, nearOk="1")], POOL)
        self.assertEqual([n["이름(한국어)"] for n in new], ["첨성대 옆"])
        self.assertEqual(verdicts[0]["판정"], "신규")

    def test_near_with_name_overlap(self):
        new, verdicts = m.manual_rows([row(ko="경주 첨성대", lat="35.8397", lng="129.219")], POOL)  # 약 550m · 이름 겹침
        self.assertEqual(new, [])
        self.assertEqual(verdicts[0]["장소 id"], "gj2")


if __name__ == "__main__":
    unittest.main()
