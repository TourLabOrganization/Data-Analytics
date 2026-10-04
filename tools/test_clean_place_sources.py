import unittest

from tools.clean_place_sources import clean_source


class CleanSource(unittest.TestCase):
    def test_same_as_app(self):
        self.assertEqual(
            clean_source("사용자 요청(의령 관광지, 2026-10-04 의령군 문화관광 · 의령9경 검색) · 좌표 수기 입력(주소 기준, 지도 검증 필요, 2026-10-04) · 대략 위치"),
            "의령군 문화관광 자료 · 주소 기준 좌표 · 대략 위치",
        )
        self.assertEqual(
            clean_source("국가유산 보물 소재지(보물 13건, 2026-10-04 국가유산 기본정보) · 좌표 수기 입력(소재지 주소 기준, 지도 검증 필요, 2026-10-04)"),
            "국가유산 보물 소재지(보물 13건) · 주소 기준 좌표",
        )
        self.assertEqual(
            clean_source("시티투어 경유지(2개 노선, 노선 표기 「새정원」) · 좌표 수기 입력(지도 검증 필요, 2026-10-03)"),
            "시티투어 경유지(2개 노선) · 주소 기준 좌표",
        )
        self.assertEqual(clean_source("사용자 요청(2026-10-04) · 좌표 수기 입력(지도 검증 필요, 2026-10-03)"), "주소 기준 좌표")


if __name__ == "__main__":
    unittest.main()
