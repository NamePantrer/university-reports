import unittest
from quest import load, play, auto_chooser, list_chooser, outcome

SC = load()
quiet = lambda *a, **k: None  # noqa: E731


class TestQuest(unittest.TestCase):
    def test_outcomes_table7(self):
        self.assertIn("минимальный ущерб", outcome(SC, 15))
        self.assertIn("минимальный ущерб", outcome(SC, 13))
        self.assertIn("умеренный", outcome(SC, 12))
        self.assertIn("умеренный", outcome(SC, 8))
        self.assertIn("максимальный ущерб", outcome(SC, 7))

    def test_full_team(self):
        self.assertEqual(play(SC, set(SC["roles"]), auto_chooser("max", None), quiet)[0], 15)
        self.assertEqual(play(SC, set(SC["roles"]), auto_chooser("mid", None), quiet)[0], 10)
        self.assertEqual(play(SC, set(SC["roles"]), auto_chooser("min", None), quiet)[0], 0)

    def test_missing_role_costs_a_turn(self):
        # без IR на 4-м этапе первая попытка уходит на привлечение роли, вторая засчитывается
        total, log = play(SC, {"SOC", "ADMIN", "CISO", "PR"}, auto_chooser("max", None), quiet)
        self.assertEqual(total, 15)
        # оба хода этапа ушли на привлечение ролей -> этап засчитывается в 0
        # этап 3: вариант 2 (нет ADMIN) -> ход 1 потрачен, вариант 1 (нет CISO) -> ход 2 потрачен
        total, log = play(SC, {"SOC"}, list_chooser([1, 3, 2, 1, 1, 1, 3]), quiet)
        self.assertEqual(log[0], (1, 3))
        self.assertEqual(log[1], (2, 0))
        self.assertEqual(log[2], (3, 0))
        self.assertEqual(log[3], (4, 3))  # этап 4: IR привлечён 1-м ходом, решение засчитано 2-м
        self.assertEqual(total, 6)

if __name__ == "__main__":
    unittest.main()
