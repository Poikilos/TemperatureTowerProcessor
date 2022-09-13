import unittest
import decimal
from decimal import Decimal

from gcodefollower import (
    changed_cmd,
)


class Testing(unittest.TestCase):
    def test_changed_cmd(self):
        old = "G0 F9000 X27.781 Y32.781 Z{z:.3f}\n".format(z=.2)
        expected = "G0 F9000 X27.781 Y32.781 Z{z:.3f}".format(z=.4)
        # ^ removed \n
        new = changed_cmd(old, 'Z', Decimal(.4))
        self.assertEqual(new, expected)
        new = changed_cmd(old, 'Z', .4)
        self.assertEqual(new, expected)


if __name__ == '__main__':
    unittest.main()
