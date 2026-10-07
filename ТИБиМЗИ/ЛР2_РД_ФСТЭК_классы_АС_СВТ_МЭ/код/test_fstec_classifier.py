"""Сверка с таблицей 11 отчёта ЛР2."""
import unittest
from pathlib import Path
from fstec_classifier import classify, load_cases, Case

EXPECTED = {  # кейс -> (АС, СВТ, МЭ)
    "1.": ("1Г", 5, 4), "2.": ("2А", 3, 2), "3.": ("3Б", 6, 5), "4.": ("1Д", 6, 5),
    "5а": ("2Б", 6, 5), "5б": ("1Г", 5, 4), "6.": ("3А", 3, 2), "7.": ("1Г", 5, 4),
}


class TestClassifier(unittest.TestCase):
    def test_cases_match_report(self):
        for c in load_cases(Path(__file__).with_name("cases.json")):
            r = classify(c)
            key = c.name[:2]
            self.assertEqual((r.as_class, r.svt_min, r.me_min), EXPECTED[key], c.name)

    def test_state_secret_lower_bound(self):
        # п. 2.18: при гостайне класс не ниже 3А / 2А / 1В
        for users, allowed in (("single", {"3А"}), ("equal", {"2А"}), ("differ", {"1А", "1Б", "1В"})):
            for grif in ("ОВ", "СС", "С"):
                self.assertIn(classify(Case("x", grif, users)).as_class, allowed)

    def test_svt_for_first_group_secret(self):
        self.assertEqual(classify(Case("x", "С", "differ")).svt_min, 4)   # 1В -> СВТ 4
        self.assertEqual(classify(Case("x", "СС", "differ")).svt_min, 3)  # 1Б -> СВТ 3
        self.assertEqual(classify(Case("x", "ОВ", "differ")).svt_min, 2)  # 1А -> СВТ 2


if __name__ == "__main__":
    unittest.main()
