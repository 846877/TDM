import unittest

from calc import addition, division, moyenne, multiplication, soustraction


class TestOperations(unittest.TestCase):
    def test_addition(self):
        self.assertEqual(addition(2, 3), 5)

    def test_soustraction(self):
        self.assertEqual(soustraction(2, 3), -1)

    def test_multiplication(self):
        self.assertEqual(multiplication(4, 2.5), 10)

    def test_division(self):
        self.assertEqual(division(9, 3), 3)

    def test_division_par_zero(self):
        with self.assertRaises(ValueError):
            division(1, 0)

    def test_moyenne(self):
        self.assertEqual(moyenne([1, 2, 3]), 2)
        self.assertEqual(moyenne([10]), 10)

    def test_moyenne_vide(self):
        with self.assertRaises(ValueError):
            moyenne([])


if __name__ == "__main__":
    unittest.main()
