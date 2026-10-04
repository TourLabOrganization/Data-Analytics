import unittest

from tools.apply_place_fixes import apply


class ApplyFixes(unittest.TestCase):
    def test_city_coords_unesco(self):
        rows = [
            {"id": "a", "지역": "대전", "위도": "36.1", "경도": "127.7", "유네스코": "Y"},
            {"id": "b", "지역": "울산", "위도": "35.6", "경도": "129.1", "유네스코": ""},
        ]
        n = apply(rows, [{"id": "a", "city": "영동", "lat": "", "lng": ""}, {"id": "b", "city": "", "lat": "35.60505", "lng": "129.17978"}], {"b"})
        self.assertEqual(n, 4)
        self.assertEqual(rows[0]["지역"], "영동")
        self.assertEqual(rows[0]["유네스코"], "")
        self.assertEqual((rows[1]["위도"], rows[1]["유네스코"]), ("35.60505", "Y"))

    def test_names(self):
        rows = [{"id": "a", "지역": "청송", "위도": "1", "경도": "2", "유네스코": "", "이름(한국어)": "옛", "English": "Old", "中文": "旧", "日本語": "旧"}]
        n = apply(rows, [{"id": "a", "city": "", "lat": "", "lng": "", "ko": "새", "en": "New", "zh": "", "ja": None, "es": "Nuevo"}], set())
        self.assertEqual(n, 1)
        self.assertEqual([rows[0][c] for c in ("이름(한국어)", "English", "中文", "日本語")], ["새", "New", "旧", "旧"])

    def test_unknown_id(self):
        with self.assertRaises(SystemExit):
            apply([{"id": "a", "지역": "x", "위도": "1", "경도": "2", "유네스코": ""}], [{"id": "zz", "city": "y"}], set())


if __name__ == "__main__":
    unittest.main()
