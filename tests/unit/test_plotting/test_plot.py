import pybamm
import unittest
import numpy as np
from tests import TestCase
import matplotlib.pyplot as plt
from matplotlib import use

use("Agg")


class TestPlot(TestCase):
    def test_plot(self):
        x = pybamm.Array(np.array([0, 3, 10]))
        y = pybamm.Array(np.array([6, 16, 78]))
        pybamm.plot(x, y, show_plot=False)

        _, ax = plt.subplots()
        ax_out = pybamm.plot(x, y, ax=ax, show_plot=False)
        self.assertEqual(ax_out, ax)

    def test_plot_fail(self):
        x = pybamm.Array(np.array([0]))
        with self.assertRaisesRegex(TypeError, "x must be 'pybamm.Array'"):
            pybamm.plot("bad", x)
        with self.assertRaisesRegex(TypeError, "y must be 'pybamm.Array'"):
            pybamm.plot(x, "bad")

    def test_plot2D(self):
        x = pybamm.Array(np.array([0, 3, 10]))
        y = pybamm.Array(np.array([6, 16, 78]))
        X, Y = pybamm.meshgrid(x, y)

        # plot with array directly
        pybamm.plot2D(x, y, Y, show_plot=False)

        # plot with meshgrid
        pybamm.plot2D(X, Y, Y, show_plot=False)

        _, ax = plt.subplots()
        ax_out = pybamm.plot2D(X, Y, Y, ax=ax, show_plot=False)
        self.assertEqual(ax_out, ax)

    def test_plot2D_fail(self):
        x = pybamm.Array(np.array([0]))
        with self.assertRaisesRegex(TypeError, "x must be 'pybamm.Array'"):
            pybamm.plot2D("bad", x, x)
        with self.assertRaisesRegex(TypeError, "y must be 'pybamm.Array'"):
            pybamm.plot2D(x, "bad", x)
        with self.assertRaisesRegex(TypeError, "z must be 'pybamm.Array'"):
            pybamm.plot2D(x, x, "bad")


if __name__ == "__main__":
    print("Add -v for more debug output")
    import sys

    if "-v" in sys.argv:
        debug = True
    pybamm.settings.debug_mode = True
    unittest.main()
