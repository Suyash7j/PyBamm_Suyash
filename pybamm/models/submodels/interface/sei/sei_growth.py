#
# Class for SEI growth
#
import pybamm
from .base_sei import BaseModel


class SEIGrowth(BaseModel):
    """
    Class for SEI growth.

    Most of the models are from Section 5.6.4 of :footcite:t:`Marquis2020` and
    references therein.

    The ec reaction limited model is from :footcite:t:`Yang2017`.

    Parameters
    ----------
    param : parameter class
        The parameters to use for this submodel
    reaction_loc : str
        Where the reaction happens: "x-average" (SPM, SPMe, etc),
        "full electrode" (full DFN), or "interface" (half-cell model)
    options : dict
        A dictionary of options to be passed to the model.
    phase : str, optional
        Phase of the particle (default is "primary")
    cracks : bool, optional
        Whether this is a submodel for standard SEI or SEI on cracks
    """

    def __init__(
        self, param, domain, reaction_loc, options, phase="primary", cracks=False
    ):
        super().__init__(param, domain, options=options, phase=phase, cracks=cracks)
        self.reaction_loc = reaction_loc
        SEI_option = getattr(self.options, domain)["SEI"]
        if SEI_option == "ec reaction limited":
            pybamm.citations.register("Yang2017")
        else:
            pybamm.citations.register("Marquis2020")

    def get_fundamental_variables(self):
        domain, Domain = self.domain_Domain
        Ls = []
        for pos in ["inner", "outer"]:
            scale = self.phase_param.L_sei_0
            if self.reaction_loc == "x-average":
                L_av = pybamm.Variable(
                    f"X-averaged {domain} {pos} {self.reaction_name}thickness [m]",
                    domain="current collector",
                    scale=scale,
                )
                L_av.print_name = f"L_{pos}_av"
                L = pybamm.PrimaryBroadcast(L_av, f"{domain} electrode")
            elif self.reaction_loc == "full electrode":
                L = pybamm.Variable(
                    f"{Domain} {pos} {self.reaction_name}thickness [m]",
                    domain=f"{domain} electrode",
                    auxiliary_domains={"secondary": "current collector"},
                    scale=scale,
                )
            elif self.reaction_loc == "interface":
                L = pybamm.Variable(
                    f"{Domain} {pos} {self.reaction_name}thickness [m]",
                    domain="current collector",
                    scale=scale,
                )
            L.print_name = f"L_{pos}"
            Ls.append(L)

        L_inner, L_outer = Ls

        SEI_option = getattr(self.options, domain)["SEI"]
        if SEI_option.startswith("ec reaction limited"):
            L_inner = 0 * L_inner  # Set L_inner to zero, copying domains

        variables = self._get_standard_thickness_variables(L_inner, L_outer)

        return variables

    def get_coupled_variables(self, variables):
        param = self.param
        phase_param = self.phase_param
        domain, Domain = self.domain_Domain
        SEI_option = getattr(self.options, domain)["SEI"]
        T = variables[f"{Domain} electrode temperature [K]"]
        # delta_phi = phi_s - phi_e
        if self.reaction_loc == "interface":
            delta_phi = variables[
                "Lithium metal interface surface potential difference [V]"
            ]
            T = pybamm.boundary_value(T, "right")
        else:
            delta_phi = variables[
                f"{Domain} electrode surface potential difference [V]"
            ]

        # Look for current that contributes to the -IR drop
        # If we can't find the interfacial current density from the main reaction, j,
        # it's ok to fall back on the total interfacial current density, j_tot
        # This should only happen when the interface submodel is "InverseButlerVolmer"
        # in which case j = j_tot (uniform) anyway
        if f"{Domain} electrode interfacial current density [A.m-2]" in variables:
            j = variables[f"{Domain} electrode interfacial current density [A.m-2]"]
        elif self.reaction_loc == "interface":
            j = variables["Lithium metal total interfacial current density [A.m-2]"]
        else:
            j = variables[
                f"X-averaged {domain} electrode total "
                "interfacial current density [A.m-2]"
            ]

        L_sei = variables[f"{Domain} total {self.reaction_name}thickness [m]"]
        L_sei_outer = variables[f"{Domain} outer {self.reaction_name}thickness [m]"]
        if self.double_layer_sei:
            L_sei_inner = variables[f"{Domain} inner {self.reaction_name}thickness [m]"]

        R_sei = phase_param.R_sei
        eta_SEI = delta_phi - phase_param.U_sei - j * L_sei * R_sei
        # Thermal prefactor for reaction, interstitial and EC models
        F_RT = param.F / (param.R * T)

        # Define alpha_SEI depending on whether it is symmetric or asymmetric. This
        # applies to "reaction limited" and "EC reaction limited"
        if SEI_option.endswith("(asymmetric)"):
            alpha_SEI = phase_param.alpha_SEI
        else:
            alpha_SEI = 0.5

        if SEI_option.startswith("reaction limited"):
            # Scott Marquis thesis (eq. 5.92)
            j_sei = -phase_param.j0_sei * pybamm.exp(-alpha_SEI * F_RT * eta_SEI)

        elif SEI_option == "electron-migration limited":
            # Scott Marquis thesis (eq. 5.94)
            j_sei = 0
            if self.double_layer_sei:
                eta_inner = delta_phi - phase_param.U_inner
                j_sei = (
                    (eta_inner < 0) * phase_param.kappa_inner * eta_inner / L_sei_inner
                )
        elif SEI_option == "interstitial-diffusion limited":
            # Scott Marquis thesis (eq. 5.96)
            j_sei = -(
                phase_param.D_li * phase_param.c_li_0 * param.F / L_sei_outer
            ) * pybamm.exp(-F_RT * delta_phi)

        elif SEI_option == "solvent-diffusion limited":
            # Scott Marquis thesis (eq. 5.91)
            j_sei = -phase_param.D_sol * phase_param.c_sol * param.F / L_sei_outer

        elif SEI_option.startswith("ec reaction limited"):
            # we have a linear system for j and c
            #  c = c_0 + j * L / F / D          [1] (eq 11 in the Yang2017 paper)
            #  j = - F * c * k_exp()            [2] (eq 10 in the Yang2017 paper, factor
            #                                        of a is outside the defn of j here)
            # [1] into [2] gives (F cancels in the second terms)
            #  j = - F * c_0 * k_exp() - j * L * k_exp() / D
            # rearrange
            #  j = -F * c_0* k_exp() / (1 + L * k_exp() / D)
            #  c_ec = c_0 - L * k_exp() / D / (1 + L * k_exp() / D)
            #       = c_0 / (1 + L * k_exp() / D)
            k_exp = phase_param.k_sei * pybamm.exp(-alpha_SEI * F_RT * eta_SEI)
            L_over_D = L_sei / phase_param.D_ec
            c_0 = phase_param.c_ec_0
            j_sei = -param.F * c_0 * k_exp / (1 + L_over_D * k_exp)
            c_ec = c_0 / (1 + L_over_D * k_exp)

            # Get variables related to the concentration
            c_ec_av = pybamm.x_average(c_ec)

            if self.reaction == "SEI on cracks":
                name = f"{Domain} EC concentration on cracks [mol.m-3]"
            else:
                name = f"{Domain} EC surface concentration [mol.m-3]"
            variables.update({name: c_ec, f"X-averaged {name}": c_ec_av})

        # All SEI growth mechanisms assumed to have Arrhenius dependence
        Arrhenius = pybamm.exp(phase_param.E_sei / param.R * (1 / param.T_ref - 1 / T))
        j_inner = None
        inner_sei_proportion = 0

        if self.double_layer_sei:
            if not SEI_option.startswith("ec reaction limited"):
                inner_sei_proportion = phase_param.inner_sei_proportion
            j_inner = inner_sei_proportion * Arrhenius * j_sei

        j_outer = (1 - inner_sei_proportion) * Arrhenius * j_sei

        variables.update(self._get_standard_concentration_variables(variables))
        variables.update(self._get_standard_reaction_variables(j_inner, j_outer))

        # Add other standard coupled variables
        variables.update(super().get_coupled_variables(variables))

        return variables

    def set_rhs(self, variables):
        phase_param = self.phase_param
        param = self.param
        domain, Domain = self.domain_Domain

        if self.reaction_loc == "x-average":
            L_outer = variables[
                f"X-averaged {domain} outer {self.reaction_name}thickness [m]"
            ]
            j_outer = variables[
                f"X-averaged {domain} electrode outer {self.reaction_name}"
                "interfacial current density [A.m-2]"
            ]
            if self.double_layer_sei:
                L_inner = variables[
                    f"X-averaged {domain} inner {self.reaction_name}thickness [m]"
                ]
                j_inner = variables[
                    f"X-averaged {domain} electrode inner {self.reaction_name}"
                    "interfacial current density [A.m-2]"
                ]
        else:
            L_outer = variables[f"{Domain} outer {self.reaction_name}thickness [m]"]
            j_outer = variables[
                f"{Domain} electrode outer {self.reaction_name}interfacial current density [A.m-2]"
            ]

            if self.double_layer_sei:
                L_inner = variables[f"{Domain} inner {self.reaction_name}thickness [m]"]
                j_inner = variables[
                    f"{Domain} electrode inner {self.reaction_name}"
                    "interfacial current density [A.m-2]"
                ]

        # The spreading term acts to spread out SEI along the cracks as they grow.
        # For SEI on initial surface (as opposed to cracks), it is zero.
        spreading_outer = 0
        spreading_inner = 0

        if self.reaction == "SEI on cracks":
            if self.reaction_loc == "x-average":
                l_cr = variables[f"X-averaged {domain} particle crack length [m]"]
                dl_cr = variables[f"X-averaged {domain} particle cracking rate [m.s-1]"]
            else:
                l_cr = variables[f"{Domain} particle crack length [m]"]
                dl_cr = variables[f"{Domain} particle cracking rate [m.s-1]"]
            spreading_outer = (
                dl_cr / l_cr * (self.phase_param.L_outer_crack_0 - L_outer)
            )
            if self.double_layer_sei:
                spreading_inner = (
                    dl_cr / l_cr * (self.phase_param.L_inner_crack_0 - L_inner)
                )

        # a * j_sei / F is the rate of consumption of li moles by SEI reaction
        # 1/z_sei converts from li moles to SEI moles (z_sei=li mol per sei mol)
        # a * j_sei / (F * z_sei) is the rate of consumption of SEI moles by SEI
        # reaction
        # V_bar / a converts from SEI moles to SEI thickness
        # V_bar * j_sei / (F * z_sei) is the rate of SEI thickness change
        dLdt_SEI_outer = (
            phase_param.V_bar_outer * j_outer / (param.F * phase_param.z_sei)
        )
        if self.double_layer_sei:
            dLdt_SEI_inner = (
                phase_param.V_bar_inner * j_inner / (param.F * phase_param.z_sei)
            )

        # we have to add the spreading rate to account for cracking
        SEI_option = getattr(self.options, domain)["SEI"]
        self.rhs = {L_outer: -dLdt_SEI_outer + spreading_outer}
        if self.double_layer_sei and not SEI_option.startswith("ec reaction limited"):
            self.rhs[L_inner] = -dLdt_SEI_inner + spreading_inner

    def set_initial_conditions(self, variables):
        domain, Domain = self.domain_Domain
        if self.reaction_loc == "x-average":
            outer_key = f"X-averaged {domain} outer {self.reaction_name}thickness [m]"
            inner_key = f"X-averaged {domain} inner {self.reaction_name}thickness [m]"
        else:
            outer_key = f"{Domain} outer {self.reaction_name}thickness [m]"
            inner_key = f"{Domain} inner {self.reaction_name}thickness [m]"

        L_outer_0 = (
            self.phase_param.L_outer_crack_0
            if self.reaction == "SEI on cracks"
            else self.phase_param.L_outer_0
        )
        L_inner_0 = (
            self.phase_param.L_inner_crack_0
            if self.reaction == "SEI on cracks"
            else self.phase_param.L_inner_0
        )

        SEI_option = getattr(self.options, domain)["SEI"]
        if self.double_layer_sei:
            if SEI_option.startswith("ec reaction limited"):
                self.initial_conditions = {variables[outer_key]: L_inner_0 + L_outer_0}
            else:
                self.initial_conditions = {
                    variables[inner_key]: L_inner_0,
                    variables[outer_key]: L_outer_0,
                }
        else:
            self.initial_conditions = {variables[outer_key]: L_outer_0}
