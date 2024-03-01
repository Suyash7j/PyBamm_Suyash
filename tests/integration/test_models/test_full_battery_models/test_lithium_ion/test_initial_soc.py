#
# Test edge cases for initial SOC
#
from __future__ import annotations

import unittest

import pybamm
from tests import TestCase


class TestInitialSOC(TestCase):
    def test_interpolant_parameter_sets(self):
        model = pybamm.lithium_ion.SPM()
        params = [
            "Ai2020",
            "Chen2020",
            "Ecker2015",
            "Marquis2019",
            "Mohtat2020",
            "OKane2022",
            "ORegan2022",
        ]
        for param in params:
            with self.subTest(param=param):
                parameter_values = pybamm.ParameterValues(param)
                sim = pybamm.Simulation(model=model, parameter_values=parameter_values)
                sim.solve([0, 600], initial_soc=0.2)
                sim.solve([0, 600], initial_soc="3.7 V")


if __name__ == "__main__":
    print("Add -v for more debug output")
    import sys

    if "-v" in sys.argv:
        debug = True
    unittest.main()
