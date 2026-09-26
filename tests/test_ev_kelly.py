import unittest
from scoring.ev import _kelly

class TestKelly(unittest.TestCase):
    def test_kelly_normal(self):
        # p=0.5, odds=2.0 -> f = (1*0.5 - 0.5)/1 = 0
        self.assertAlmostEqual(_kelly(0.5, 2.0), 0.0)

    def test_kelly_positive_edge(self):
        # p=0.6, odds=2.0 -> f = (1*0.6 - 0.4)/1 = 0.2
        self.assertTrue(_kelly(0.6, 2.0) > 0)

    def test_kelly_clamps_p_above_1(self):
        # p=1.5, odds=2.0 -> treated as p=1.0. f = (1*1.0 - 0.0)/1 = 1.0
        self.assertTrue(_kelly(1.5, 2.0) <= 1.0)
        self.assertTrue(_kelly(1.5, 2.0) > 0)

    def test_kelly_clamps_result_above_1(self):
        # p=0.99, odds=100.0 -> f = (99*0.99 - 0.01)/99 = (98.01 - 0.01)/99 = 98/99 ~ 0.9899
        self.assertTrue(_kelly(0.99, 100.0) <= 1.0)
        self.assertTrue(_kelly(0.99, 100.0) > 0)

if __name__ == '__main__':
    unittest.main()
