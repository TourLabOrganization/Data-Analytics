# -*- coding: utf-8 -*-
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from tools.add_popular_places import COLUMNS
from tools.merge_same_places import main, read_aliases


def row(pid, ko, **over):
    r = {c: "" for c in COLUMNS}
    r.update({"id": pid, "권역": "경주", "지역": "경주", "이름(한국어)": ko, "English": ko, "카테고리": "herit", "위도": "35.8", "경도": "129.2", "추천 체류(분)": "60"})
    r.update(over)
    return r


def write_places(path, rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(COLUMNS)
    for r in rows:
        w.writerow([r[c] for c in COLUMNS])
    path.write_bytes(b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8"))


class MergeSamePlacesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.places = d / "tour-places.csv"
        self.signgu = d / "place_signgu.json"
        self.same = d / "same_places.csv"
        self.aliases = d / "place_aliases.csv"
        write_places(self.places, [
            row("a1", "감은사지"),
            row("b1", "감은사지동서삼층석탑", 日本語="感恩寺址", 유네스코="Y", 설명="석탑 둘"),
            row("c1", "황남빵 본점", 中文="皇南面包", 설명="빵"),
            row("c2", "황남빵", 中文="다른 값", 링크="http://x"),
            row("z1", "분황사", 설명="그대로, 쉼표 있음"),
        ])
        self.signgu.write_text(json.dumps({"a1": "47130", "b1": "47130", "c1": "47130", "c2": "47130", "z1": "47130"}), encoding="utf-8")
        self.same.write_text("﻿keep,drop,reason\na1,b1,\"감은사지 = 석탑(13m)\"\nc1,c2,같은 빵집\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_tool(self, apply=True):
        args = ["--csv", str(self.same), "--places", str(self.places), "--signgu", str(self.signgu), "--aliases", str(self.aliases)]
        return main(args + (["--apply"] if apply else []))

    def rows(self):
        with open(self.places, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    def test_dry_run_leaves_files(self):
        before = self.places.read_bytes()
        self.assertEqual(self.run_tool(apply=False), 0)
        self.assertEqual(self.places.read_bytes(), before)
        self.assertFalse(self.aliases.exists())

    def test_apply_drops_fills_and_aliases(self):
        self.assertEqual(self.run_tool(), 0)
        rows = self.rows()
        self.assertEqual([r["id"] for r in rows], ["a1", "c1", "z1"])
        a1 = rows[0]
        self.assertEqual((a1["日本語"], a1["유네스코"], a1["설명"]), ("感恩寺址", "Y", "석탑 둘"))
        c1 = rows[1]
        self.assertEqual((c1["中文"], c1["설명"], c1["링크"]), ("皇南面包", "빵", "http://x"))  # keep 값 우선, 빈 칸만 채움
        raw = self.places.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertIn(b"\r\n", raw)
        self.assertNotIn(b"\n\n", raw)
        self.assertEqual(json.loads(self.signgu.read_text(encoding="utf-8")), {"a1": "47130", "c1": "47130", "z1": "47130"})
        self.assertEqual(read_aliases(self.aliases), {"b1": ("a1", "감은사지 = 석탑(13m)"), "c2": ("c1", "같은 빵집")})

    def test_second_run_is_same(self):
        self.run_tool()
        after = self.places.read_bytes()
        self.assertEqual(self.run_tool(), 0)
        self.assertEqual(self.places.read_bytes(), after)
        self.assertEqual(len(read_aliases(self.aliases)), 2)

    def test_missing_keep_fails(self):
        self.same.write_text("keep,drop,reason\nnope,b1,x\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.run_tool()


if __name__ == "__main__":
    unittest.main()
