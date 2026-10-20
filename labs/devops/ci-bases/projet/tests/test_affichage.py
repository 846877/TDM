import unittest

from calc.affichage import formater


class TestAffichage(unittest.TestCase):
    def test_formater(self):
        self.assertEqual(formater(3.14159), "Résultat : 3.14")


if __name__ == "__main__":
    unittest.main()
