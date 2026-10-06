import unittest

from tools.apply_place_notes import append_sentence, apply


class ApplyNotes(unittest.TestCase):
    def test_append_once(self):
        self.assertEqual(append_sentence("국밥집. ", "식객에 나온 식당이다."), "국밥집. 식객에 나온 식당이다.")
        self.assertEqual(append_sentence("국밥집. 식객에 나온 식당이다.", "식객에 나온 식당이다."), "국밥집. 식객에 나온 식당이다.")
        self.assertEqual(append_sentence("", "문장."), "문장.")

    def test_alias_and_idempotent(self):
        rows = [{"id": "b", "설명": "국밥집."}]
        notes = [{"id": "a", "ko": "문장.", "en": "Sentence."}]
        self.assertEqual(apply(rows, notes, {"a": "b"}), 1)
        self.assertEqual(apply(rows, notes, {"a": "b"}), 0)
        self.assertEqual(rows[0]["설명"], "국밥집. 문장.")

    def test_unknown_id(self):
        with self.assertRaises(SystemExit):
            apply([{"id": "b", "설명": ""}], [{"id": "zz", "ko": "x"}], {})


if __name__ == "__main__":
    unittest.main()
