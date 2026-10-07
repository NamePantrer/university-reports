"""Проверка калькулятора на эталонных векторах (значения сверены с калькулятором FIRST)."""
import unittest
from cvss3 import scores


class TestCVSS(unittest.TestCase):
    def check(self, vec, base, temporal=None, env=None):
        s = scores(vec)
        self.assertEqual(s["base"], base, vec)
        if temporal is not None:
            self.assertEqual(s["temporal"], temporal, vec)
        if env is not None:
            self.assertEqual(s["environmental"], env, vec)

    def test_reference_vectors(self):
        self.check("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", 9.8)   # типичная RCE
        self.check("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H", 10.0)
        self.check("CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N", 6.1)   # отражённый XSS
        self.check("CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H", 7.8)   # локальное LPE
        self.check("CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:N/A:N", 5.9)
        self.check("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N", 0.0)

    def test_lab_tasks(self):
        v = "AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:N/A:L"
        self.check(f"CVSS:3.0/{v}", 8.5)
        self.check(f"CVSS:3.0/{v}/E:F/RL:W/RC:C", 8.5, temporal=8.0)
        env = f"CVSS:3.0/{v}/E:F/RL:W/RC:C/CR:H/IR:H/AR:H/MAV:L/MAC:L/MPR:H/MUI:N/MS:X/MC:H/MI:H/MA:H"
        self.check(env, 8.5, temporal=8.0, env=7.8)

    def test_roundup31(self):
        from cvss3 import roundup31
        self.assertEqual(roundup31(4.02), 4.1)
        self.assertEqual(roundup31(4.00), 4.0)


if __name__ == "__main__":
    unittest.main()
