#
# Class for two-dimensional current collectors
#
import pybamm
from .base_surface_form_current_collector import BaseSurfaceForm


class LeadingOrder(BaseSurfaceForm):
    """A submodel for Ohm's law plus conservation of current in the current collectors,
    which uses the voltage-current relationship from the surface form of the
    leading-order model.

    Parameters
    ----------
    param : parameter class
        The parameters to use for this submodel


    **Extends:** :class:`pybamm.current_collector.surface_form.BaseSurfaceForm`
    """

    def __init__(self, param):
        super().__init__(param)

    def get_coupled_variables(self, variables):

        delta_phi_n_av = variables[
            "X-averaged negative electrode surface potential difference"
        ]
        delta_phi_p_av = variables[
            "X-averaged positive electrode surface potential difference"
        ]
        phi_s_cn = delta_phi_n_av - pybamm.BoundaryValue(delta_phi_n_av, "right")
        phi_s_cp = delta_phi_p_av - delta_phi_n_av
        variables = self._get_standard_potential_variables(phi_s_cn, phi_s_cp)

        # Define conductivity
        param = self.param
        vertical_conductivity = (
            param.l_n * param.sigma_n_dash * param.l_p * param.sigma_p_dash
        ) / (param.l_n * param.sigma_n_dash + param.l_p * param.sigma_p_dash)

        # Simple model: read off vertical current (no extra equation)
        delta_phi_difference = delta_phi_n_av - delta_phi_p_av
        i_boundary_cc = vertical_conductivity * pybamm.laplacian(delta_phi_difference)

        # TODO: grad not implemented for 2D yet
        i_cc = pybamm.Scalar(0)

        variables.update(self._get_standard_current_variables(i_cc, i_boundary_cc))

        return variables

    def set_boundary_conditions(self, variables):

        delta_phi_n_av = variables[
            "X-averaged negative electrode surface potential difference"
        ]
        delta_phi_p_av = variables[
            "X-averaged positive electrode surface potential difference"
        ]
        delta_phi_difference = delta_phi_n_av - delta_phi_p_av

        # Set boundary conditions at top ("right") and bottom ("left")
        param = self.param
        i_cell = param.current_with_time
        vertical_conductivity = (
            param.l_n * param.sigma_n_dash * param.l_p * param.sigma_p_dash
        ) / (param.l_n * param.sigma_n_dash + param.l_p * param.sigma_p_dash)

        self.boundary_conditions = {
            delta_phi_difference: {
                "left": (pybamm.Scalar(0), "Neumann"),
                "right": (i_cell / vertical_conductivity, "Neumann"),
            }
        }
