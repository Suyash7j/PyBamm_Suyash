import pybamm
import numpy as np
import os
import pickle
import scipy.interpolate as interp
import matplotlib.pyplot as plt

# change working directory to the root of pybamm
os.chdir(pybamm.root_dir())

"-----------------------------------------------------------------------------"
"Load comsol data"

try:
    comsol_variables = pickle.load(
        open("input/comsol_results/comsol_thermal_1C.pickle", "rb")
    )
except FileNotFoundError:
    raise FileNotFoundError("COMSOL data not found. Try running load_comsol_data.py")

"-----------------------------------------------------------------------------"
"Create and solve pybamm model"

# load model and geometry
pybamm.set_logging_level("INFO")
options = {"thermal": "x-full"}
pybamm_model = pybamm.lithium_ion.DFN(options)
geometry = pybamm_model.default_geometry

# load parameters and process model and geometry
param = pybamm_model.default_parameter_values
param.update(
    {
        "C-rate": 1,
        #    "Negative electrode conductivity [S.m-1]": 1e6,
        #    "Positive electrode conductivity [S.m-1]": 1e6,
    }
)
param.process_model(pybamm_model)
param.process_geometry(geometry)

# create mesh
var = pybamm.standard_spatial_vars
# var_pts = {var.x_n: 101, var.x_s: 101, var.x_p: 101, var.r_n: 101, var.r_p: 101}
var_pts = {var.x_n: 15, var.x_s: 15, var.x_p: 15, var.r_n: 15, var.r_p: 15}
mesh = pybamm.Mesh(geometry, pybamm_model.default_submesh_types, var_pts)

# discretise model
spatial_methods = pybamm_model.default_spatial_methods
disc = pybamm.Discretisation(mesh, pybamm_model.default_spatial_methods)
disc.process_model(pybamm_model)

# discharge timescale
tau = param.evaluate(pybamm.standard_parameters_lithium_ion.tau_discharge)

# solve model at comsol times
time = comsol_variables["time"] / tau
# solver = pybamm.IDAKLUSolver(atol=1e-6, rtol=1e-6, root_tol=1e-6)
solver = pybamm.CasadiSolver(atol=1e-6, rtol=1e-6, root_tol=1e-6, mode="fast")
solution = solver.solve(pybamm_model, time)

"-----------------------------------------------------------------------------"
"Make Comsol 'model' for comparison"

whole_cell = ["negative electrode", "separator", "positive electrode"]
comsol_t = comsol_variables["time"]
L_x = param.evaluate(pybamm.standard_parameters_lithium_ion.L_x)


def get_interp_fun(variable_name, domain):
    """
    Create a :class:`pybamm.Function` object using the variable, to allow plotting with
    :class:`'pybamm.QuickPlot'` (interpolate in space to match edges, and then create
    function to interpolate in time)
    """
    variable = comsol_variables[variable_name]
    if domain == ["negative electrode"]:
        comsol_x = comsol_variables["x_n"]
    elif domain == ["separator"]:
        comsol_x = comsol_variables["x_s"]
    elif domain == ["positive electrode"]:
        comsol_x = comsol_variables["x_p"]
    elif domain == whole_cell:
        comsol_x = comsol_variables["x"]
    # Make sure to use dimensional space
    pybamm_x = mesh.combine_submeshes(*domain)[0].nodes * L_x
    variable = interp.interp1d(comsol_x, variable, axis=0)(pybamm_x)

    def myinterp(t):
        return interp.interp1d(comsol_t, variable)(t)[:, np.newaxis]

    # Make sure to use dimensional time
    fun = pybamm.Function(myinterp, pybamm.t * tau, name=variable_name + "_comsol")
    fun.domain = domain
    return fun


comsol_c_n_surf = get_interp_fun("c_n_surf", ["negative electrode"])
comsol_c_e = get_interp_fun("c_e", whole_cell)
comsol_c_p_surf = get_interp_fun("c_p_surf", ["positive electrode"])
comsol_phi_n = get_interp_fun("phi_n", ["negative electrode"])
comsol_phi_e = get_interp_fun("phi_e", whole_cell)
comsol_phi_p = get_interp_fun("phi_p", ["positive electrode"])
comsol_i_s_n = get_interp_fun("i_s_n", ["negative electrode"])
comsol_i_s_p = get_interp_fun("i_s_p", ["positive electrode"])
comsol_i_e_n = get_interp_fun("i_e_n", ["negative electrode"])
comsol_i_e_p = get_interp_fun("i_e_p", ["positive electrode"])
comsol_voltage = interp.interp1d(comsol_t, comsol_variables["voltage"])
comsol_temperature = get_interp_fun("temperature", whole_cell)
comsol_temperature_av = interp.interp1d(
    comsol_t, comsol_variables["average temperature"]
)
comsol_q_irrev_n = get_interp_fun("Q_irrev_n", ["negative electrode"])
comsol_q_irrev_p = get_interp_fun("Q_irrev_p", ["positive electrode"])
comsol_q_rev_n = get_interp_fun("Q_rev_n", ["negative electrode"])
comsol_q_rev_p = get_interp_fun("Q_rev_p", ["positive electrode"])
comsol_q_total_n = get_interp_fun("Q_total_n", ["negative electrode"])
comsol_q_total_s = get_interp_fun("Q_total_s", ["separator"])
comsol_q_total_p = get_interp_fun("Q_total_p", ["positive electrode"])

# Create comsol model with dictionary of Matrix variables
comsol_model = pybamm.BaseModel()
comsol_model.variables = {
    "Negative particle surface concentration [mol.m-3]": comsol_c_n_surf,
    "Electrolyte concentration [mol.m-3]": comsol_c_e,
    "Positive particle surface concentration [mol.m-3]": comsol_c_p_surf,
    "Current [A]": pybamm_model.variables["Current [A]"],
    "Negative electrode potential [V]": comsol_phi_n,
    "Electrolyte potential [V]": comsol_phi_e,
    "Positive electrode potential [V]": comsol_phi_p,
    "Negative electrode current density [A.m-2]": comsol_i_s_n,
    "Positive electrode current density [A.m-2]": comsol_i_s_p,
    "Negative electrode electrolyte current density [A.m-2]": comsol_i_e_n,
    "Positive electrode electrolyte current density [A.m-2]": comsol_i_e_p,
    "Terminal voltage [V]": pybamm.Function(comsol_voltage, pybamm.t * tau),
    "Cell temperature [K]": comsol_temperature,
    "Volume-averaged cell temperature [K]": pybamm.Function(
        comsol_temperature_av, pybamm.t * tau
    ),
    "Negative electrode irreversible electrochemical heating [W.m-3]": comsol_q_irrev_n,
    "Positive electrode irreversible electrochemical heating [W.m-3]": comsol_q_irrev_p,
    "Negative electrode reversible heating [W.m-3]": comsol_q_rev_n,
    "Positive electrode reversible heating [W.m-3]": comsol_q_rev_p,
    "Negative electrode total heating [W.m-3]": comsol_q_total_n,
    "Separator total heating [W.m-3]": comsol_q_total_s,
    "Positive electrode total heating [W.m-3]": comsol_q_total_p,
}

"-----------------------------------------------------------------------------"
"Plot comparison"

# Define plotting functions
# TODO: could be tidied up into shared file


def time_only_plot(var, plot_times=None, plot_error=None):
    """
    Plot pybamm variable against comsol variable where both are a function of
    time only.

    Parameters
    ----------

    var : str
        The name of the variable to plot.
    plot_times : array_like, optional
        The times at which to plot. If None (default) the plot times will be
        the times in the comsol model.
    plot_error : str, optional
        Whether to plot the error. Can be "rel" (plots the relative error), "abs"
        (plots the abolute error), "both" (plots both the relative and abolsute
        errors) or None (default, plots no errors).
    """

    # Set plot times if not provided
    if plot_times is None:
        plot_times = comsol_variables["time"]

    # Process variables
    pybamm_var = pybamm.ProcessedVariable(
        pybamm_model.variables[var], solution.t, solution.y, mesh=mesh
    )(plot_times / tau)
    comsol_var = pybamm.ProcessedVariable(
        comsol_model.variables[var], solution.t, solution.y, mesh=mesh
    )(plot_times / tau)

    # Make plot

    # add extra row for errors
    if plot_error in ["abs", "rel"]:
        n_rows = 2
    elif plot_error == "both":
        n_rows = 3
    else:
        n_rows = 1
    fig, ax = plt.subplots(n_rows, 1, figsize=(15, 8))

    ax[0].plot(plot_times, pybamm_var, "-", label="PyBaMM")
    ax[0].plot(plot_times, comsol_var, "o", fillstyle="none", label="COMSOL")
    if plot_error == "abs":
        error = np.abs(pybamm_var - comsol_var)
        ax[1].plot(plot_times, error, "-")
    elif plot_error == "rel":
        error = np.abs((pybamm_var - comsol_var) / comsol_var)
        ax[1].plot(plot_times, error, "-")
    elif plot_error == "both":
        abs_error = np.abs(pybamm_var - comsol_var)
        rel_error = np.abs((pybamm_var - comsol_var) / comsol_var)
        ax[1].plot(plot_times, abs_error, "-")
        ax[2].plot(plot_times, rel_error, "-")

    # set labels
    ax[0].set_xlabel("t")
    ax[0].set_ylabel(var)
    if plot_error in ["abs", "rel"]:
        ax[1].set_xlabel("t")
        ax[1].set_ylabel("error (" + plot_error + ")")
    elif plot_error == "both":
        ax[1].set_xlabel("t")
        ax[1].set_ylabel("error (abs)")
        ax[2].set_xlabel("t")
        ax[2].set_ylabel("error (rel)")
    ax[0].legend(bbox_to_anchor=(1.04, 1), loc="upper left")
    plt.tight_layout()


# Get mesh nodes for spatial plots
x_n = mesh.combine_submeshes(*["negative electrode"])[0].nodes
x_s = mesh.combine_submeshes(*["separator"])[0].nodes
x_p = mesh.combine_submeshes(*["positive electrode"])[0].nodes
x = mesh.combine_submeshes(*whole_cell)[0].nodes


def whole_cell_by_domain_comparison_plot(var, plot_times=None, plot_error=None):
    """
    Plot pybamm variable (defined over whole cell) against comsol variable
    (defined by component). E.g. if var = "Electrolyte current density [A.m-2]"
    then the pybamm variable will be "Electrolyte current density [A.m-2]", and
    comsol variables will be "Negative electrode electrolyte current density [A.m-2]",
    "Separator electrolyte current density [A.m-2]", and "Positive electrode electrolyte
    current density [A.m-2]".

    Parameters
    ----------

    var : str
        The name of the variable to plot.
    plot_times : array_like, optional
        The times at which to plot. If None (default) the plot times will be
        the times in the comsol model.
    plot_error : str, optional
        Whether to plot the error. Can be "rel" (plots the relative error), "abs"
        (plots the abolute error), "both" (plots both the relative and abolsute
        errors) or None (default, plots no errors).
    """

    # Set plot times if not provided
    if plot_times is None:
        plot_times = comsol_variables["time"]

    # Process variables

    # Process pybamm variable
    pybamm_var_fun = pybamm.ProcessedVariable(
        pybamm_model.variables[var], solution.t, solution.y, mesh=mesh
    )

    # Process comsol variable in negative electrode
    comsol_var_n_fun = pybamm.ProcessedVariable(
        comsol_model.variables["Negative electrode " + var[0].lower() + var[1:]],
        solution.t,
        solution.y,
        mesh=mesh,
    )
    # Process comsol variable in separator (if defined here)
    try:
        comsol_var_s_fun = pybamm.ProcessedVariable(
            comsol_model.variables["Separator " + var[0].lower() + var[1:]],
            solution.t,
            solution.y,
            mesh=mesh,
        )
    except KeyError:
        comsol_var_s_fun = None
        print("Variable " + var + " not defined in separator")
    # Process comsol variable in positive electrode
    comsol_var_p_fun = pybamm.ProcessedVariable(
        comsol_model.variables["Positive electrode " + var[0].lower() + var[1:]],
        solution.t,
        solution.y,
        mesh=mesh,
    )

    # Make plot

    # add extra row for errors
    if plot_error in ["abs", "rel"]:
        n_rows = 2
    elif plot_error == "both":
        n_rows = 3
    else:
        n_rows = 1
    # add extra column for separator
    if comsol_var_s_fun:
        n_cols = 3
    else:
        n_cols = 2
    fig, ax = plt.subplots(n_rows, n_cols, figsize=(15, 8))
    cmap = plt.get_cmap("inferno")

    # Loop over plot_times
    for ind, t in enumerate(plot_times):
        color = cmap(float(ind) / len(plot_times))

        # negative electrode
        comsol_var_n = comsol_var_n_fun(x=x_n, t=t / tau)
        pybamm_var_n = pybamm_var_fun(x=x_n, t=t / tau)
        ax[0, 0].plot(x_n * L_x, comsol_var_n, "o", color=color, fillstyle="none")
        ax[0, 0].plot(x_n * L_x, pybamm_var_n, "-", color=color)
        if plot_error == "abs":
            error_n = np.abs(pybamm_var_n - comsol_var_n)
            ax[1, 0].plot(x_n * L_x, error_n, "-", color=color)
        elif plot_error == "rel":
            error_n = np.abs((pybamm_var_n - comsol_var_n) / comsol_var_n)
            ax[1, 0].plot(x_n * L_x, error_n, "-", color=color)
        elif plot_error == "both":
            abs_error_n = np.abs(pybamm_var_n - comsol_var_n)
            rel_error_n = np.abs((pybamm_var_n - comsol_var_n) / comsol_var_n)
            ax[1, 0].plot(x_n * L_x, abs_error_n, "-", color=color)
            ax[2, 0].plot(x_n * L_x, rel_error_n, "-", color=color)

        # separator
        if comsol_var_s_fun:
            comsol_var_s = comsol_var_s_fun(x=x_s, t=t / tau)
            pybamm_var_s = pybamm_var_fun(x=x_s, t=t / tau)
            ax[0, 1].plot(x_s * L_x, comsol_var_s, "o", color=color, fillstyle="none")
            ax[0, 1].plot(x_s * L_x, pybamm_var_s, "-", color=color)
            if plot_error == "abs":
                error_s = np.abs(pybamm_var_s - comsol_var_s)
                ax[1, 1].plot(x_s * L_x, error_s, "-", color=color)
            elif plot_error == "rel":
                error_s = np.abs((pybamm_var_s - comsol_var_s) / comsol_var_s)
                ax[1, 1].plot(x_s * L_x, error_s, "-", color=color)
            elif plot_error == "both":
                abs_error_s = np.abs(pybamm_var_s - comsol_var_s)
                rel_error_s = np.abs((pybamm_var_s - comsol_var_s) / comsol_var_s)
                ax[1, 1].plot(x_s * L_x, abs_error_s, "-", color=color)
                ax[2, 1].plot(x_s * L_x, rel_error_s, "-", color=color)

        # positive electrode
        comsol_var_p = comsol_var_p_fun(x=x_p, t=t / tau)
        pybamm_var_p = pybamm_var_fun(x=x_p, t=t / tau)
        ax[0, n_cols - 1].plot(
            x_p * L_x,
            comsol_var_p,
            "o",
            color=color,
            fillstyle="none",
            label="COMSOL" if ind == 0 else "",
        )
        ax[0, n_cols - 1].plot(
            x_p * L_x,
            pybamm_var_p,
            "-",
            color=color,
            label="PyBaMM (t={:.0f} s)".format(t),
        )
        if plot_error == "abs":
            error_p = np.abs(pybamm_var_p - comsol_var_p)
            ax[1, n_cols - 1].plot(x_p * L_x, error_p, "-", color=color)
        elif plot_error == "rel":
            error_p = np.abs((pybamm_var_p - comsol_var_p) / comsol_var_p)
            ax[1, n_cols - 1].plot(x_p * L_x, error_p, "-", color=color)
        elif plot_error == "both":
            abs_error_p = np.abs(pybamm_var_p - comsol_var_p)
            rel_error_p = np.abs((pybamm_var_p - comsol_var_p) / comsol_var_p)
            ax[1, n_cols - 1].plot(x_p * L_x, abs_error_p, "-", color=color)
            ax[2, n_cols - 1].plot(x_p * L_x, rel_error_p, "-", color=color)

    # set labels
    ax[0, 0].set_xlabel("x_n")
    ax[0, 0].set_ylabel(var)
    if comsol_var_s_fun:
        ax[0, 1].set_xlabel("x_s")
        ax[0, 1].set_ylabel(var)
    ax[0, n_cols - 1].set_xlabel("x_p")
    ax[0, n_cols - 1].set_ylabel(var)
    if plot_error in ["abs", "rel"]:
        ax[1, 0].set_xlabel("x_n")
        ax[1, 0].set_ylabel("error (" + plot_error + ")")
        if comsol_var_s_fun:
            ax[1, 1].set_xlabel("x_s")
            ax[1, 1].set_ylabel("error (" + plot_error + ")")
        ax[1, n_cols - 1].set_xlabel("x_p")
        ax[1, n_cols - 1].set_ylabel("error (" + plot_error + ")")
    elif plot_error == "both":
        ax[1, 0].set_xlabel("x_n")
        ax[1, 0].set_ylabel("error (abs)")
        ax[2, 0].set_xlabel("x_n")
        ax[2, 0].set_ylabel("error (rel)")
        if comsol_var_s_fun:
            ax[1, 1].set_xlabel("x_s")
            ax[1, 1].set_ylabel("error (abs)")
            ax[2, 1].set_xlabel("x_s")
            ax[2, 1].set_ylabel("error (rel)")
        ax[1, n_cols - 1].set_xlabel("x_p")
        ax[1, n_cols - 1].set_ylabel("error (abs)")
        ax[2, n_cols - 1].set_xlabel("x_p")
        ax[2, n_cols - 1].set_ylabel("error (rel)")
    ax[0, n_cols - 1].legend(bbox_to_anchor=(1.04, 1), loc="upper left")
    plt.tight_layout()


def electrode_comparison_plot(var, plot_times=None, plot_error=None):
    """
    Plot pybamm variable against comsol variable (both defined separately in the
    negative and positive electrode) E.g. if var = "electrode current density [A.m-2]"
    then the variables "Negative electrode current density [A.m-2]" and "Positive
    electrode current density [A.m-2]" will be plotted.

    Parameters
    ----------

    var : str
        The name of the variable to plot with the domain (Negative or Positive)
        removed from the beginning of the name.
    plot_times : array_like, optional
        The times at which to plot. If None (default) the plot times will be
        the times in the comsol model.
    plot_error : str, optional
        Whether to plot the error. Can be "rel" (plots the relative error), "abs"
        (plots the abolute error), "both" (plots both the relative and abolsute
        errors) or None (default, plots no errors).
    """

    # Set plot times if not provided
    if plot_times is None:
        plot_times = comsol_variables["time"]

    # Process variables

    # Process pybamm variable in negative electrode
    pybamm_var_n_fun = pybamm.ProcessedVariable(
        pybamm_model.variables["Negative " + var], solution.t, solution.y, mesh=mesh
    )

    # Process pybamm variable in positive electrode
    pybamm_var_p_fun = pybamm.ProcessedVariable(
        pybamm_model.variables["Positive " + var], solution.t, solution.y, mesh=mesh
    )

    # Process comsol variable in negative electrode
    comsol_var_n_fun = pybamm.ProcessedVariable(
        comsol_model.variables["Negative " + var], solution.t, solution.y, mesh=mesh
    )

    # Process comsol variable in positive electrode
    comsol_var_p_fun = pybamm.ProcessedVariable(
        comsol_model.variables["Positive " + var], solution.t, solution.y, mesh=mesh
    )

    # Make plot

    # add extra row for errors
    if plot_error in ["abs", "rel"]:
        n_rows = 2
    elif plot_error == "both":
        n_rows = 3
    else:
        n_rows = 1
    fig, ax = plt.subplots(n_rows, 2, figsize=(15, 8))
    cmap = plt.get_cmap("inferno")

    # Loop over plot_times
    for ind, t in enumerate(plot_times):
        color = cmap(float(ind) / len(plot_times))

        # negative electrode
        comsol_var_n = comsol_var_n_fun(x=x_n, t=t / tau)
        pybamm_var_n = pybamm_var_n_fun(x=x_n, t=t / tau)
        ax[0, 0].plot(x_n * L_x, comsol_var_n, "o", color=color, fillstyle="none")
        ax[0, 0].plot(x_n * L_x, pybamm_var_n, "-", color=color)
        if plot_error == "abs":
            error_n = np.abs(pybamm_var_n - comsol_var_n)
            ax[1, 0].plot(x_n * L_x, error_n, "-", color=color)
        elif plot_error == "rel":
            error_n = np.abs((pybamm_var_n - comsol_var_n) / comsol_var_n)
            ax[1, 0].plot(x_n * L_x, error_n, "-", color=color)
        elif plot_error == "both":
            abs_error_n = np.abs(pybamm_var_n - comsol_var_n)
            rel_error_n = np.abs((pybamm_var_n - comsol_var_n) / comsol_var_n)
            ax[1, 0].plot(x_n * L_x, abs_error_n, "-", color=color)
            ax[2, 0].plot(x_n * L_x, rel_error_n, "-", color=color)

        # positive electrode
        comsol_var_p = comsol_var_p_fun(x=x_p, t=t / tau)
        pybamm_var_p = pybamm_var_p_fun(x=x_p, t=t / tau)
        ax[0, 1].plot(
            x_p * L_x,
            comsol_var_p,
            "o",
            color=color,
            fillstyle="none",
            label="COMSOL" if ind == 0 else "",
        )
        ax[0, 1].plot(
            x_p * L_x,
            pybamm_var_p,
            "-",
            color=color,
            label="PyBaMM (t={:.0f} s)".format(t),
        )
        if plot_error == "abs":
            error_p = np.abs(pybamm_var_p - comsol_var_p)
            ax[1, 1].plot(x_p * L_x, error_p, "-", color=color)
        elif plot_error == "rel":
            error_p = np.abs((pybamm_var_p - comsol_var_p) / comsol_var_p)
            ax[1, 1].plot(x_p * L_x, error_p, "-", color=color)
        elif plot_error == "both":
            abs_error_p = np.abs(pybamm_var_p - comsol_var_p)
            rel_error_p = np.abs((pybamm_var_p - comsol_var_p) / comsol_var_p)
            ax[1, 1].plot(x_p * L_x, abs_error_p, "-", color=color)
            ax[2, 1].plot(x_p * L_x, rel_error_p, "-", color=color)

    # set labels
    ax[0, 0].set_xlabel("x_n")
    ax[0, 0].set_ylabel(var)
    ax[0, 1].set_xlabel("x_p")
    ax[0, 1].set_ylabel(var)
    if plot_error in ["abs", "rel"]:
        ax[1, 0].set_xlabel("x_n")
        ax[1, 0].set_ylabel("error (" + plot_error + ")")
        ax[1, 1].set_xlabel("x_p")
        ax[1, 1].set_ylabel("error (" + plot_error + ")")
    elif plot_error == "both":
        ax[1, 0].set_xlabel("x_n")
        ax[1, 0].set_ylabel("error (abs)")
        ax[2, 0].set_xlabel("x_n")
        ax[2, 0].set_ylabel("error (rel)")
        ax[1, 1].set_xlabel("x_p")
        ax[1, 1].set_ylabel("error (abs)")
        ax[2, 0].set_xlabel("x_n")
        ax[2, 1].set_ylabel("error (rel)")
    ax[0, 1].legend(bbox_to_anchor=(1.04, 1), loc="upper left")
    plt.tight_layout()


def whole_cell_comparison_plot(var, plot_times=None, plot_error=None):
    """
    Plot pybamm variable against comsol variable (both defined over whole cell)

    Parameters
    ----------

    var : str
        The name of the variable to plot.
    plot_times : array_like, optional
        The times at which to plot. If None (default) the plot times will be
        the times in the comsol model.
    plot_error : str, optional
        Whether to plot the error. Can be "rel" (plots the relative error), "abs"
        (plots the abolute error), "both" (plots both the relative and abolsute
        errors) or None (default, plots no errors).
    """

    # Set plot times if not provided
    if plot_times is None:
        plot_times = comsol_variables["time"]

    # Process variables

    # Process pybamm variable
    pybamm_var_fun = pybamm.ProcessedVariable(
        pybamm_model.variables[var], solution.t, solution.y, mesh=mesh
    )

    # Process comsol variable
    comsol_var_fun = pybamm.ProcessedVariable(
        comsol_model.variables[var], solution.t, solution.y, mesh=mesh
    )

    # Make plot

    # add extra row for errors
    if plot_error in ["abs", "rel"]:
        n_rows = 2
    elif plot_error == "both":
        n_rows = 3
    else:
        n_rows = 1
    fig, ax = plt.subplots(n_rows, 1, figsize=(15, 8))
    cmap = plt.get_cmap("inferno")

    # Loop over plot_times
    for ind, t in enumerate(plot_times):
        color = cmap(float(ind) / len(plot_times))

        # whole cell
        comsol_var = comsol_var_fun(x=x, t=t / tau)
        pybamm_var = pybamm_var_fun(x=x, t=t / tau)
        ax[0].plot(
            x * L_x,
            comsol_var,
            "o",
            color=color,
            fillstyle="none",
            label="COMSOL" if ind == 0 else "",
        )
        ax[0].plot(
            x * L_x, pybamm_var, "-", color=color, label="PyBaMM (t={:.0f} s)".format(t)
        )
        if plot_error == "abs":
            error = np.abs(pybamm_var - comsol_var)
            ax[1].plot(x * L_x, error, "-", color=color)
        elif plot_error == "rel":
            error = np.abs((pybamm_var - comsol_var) / comsol_var)
            ax[1].plot(x_n * L_x, error, "-", color=color)
        elif plot_error == "both":
            abs_error = np.abs(pybamm_var - comsol_var)
            rel_error = np.abs((pybamm_var - comsol_var) / comsol_var)
            ax[1].plot(x * L_x, abs_error, "-", color=color)
            ax[2].plot(x * L_x, rel_error, "-", color=color)

    # set labels
    ax[0].set_xlabel("x")
    ax[0].set_ylabel(var)
    if plot_error in ["abs", "rel"]:
        ax[1].set_xlabel("x")
        ax[1].set_ylabel("error (" + plot_error + ")")
    elif plot_error == "both":
        ax[1].set_xlabel("x")
        ax[1].set_ylabel("error (abs)")
        ax[2].set_xlabel("x")
        ax[2].set_ylabel("error (rel)")
    ax[0].legend(bbox_to_anchor=(1.04, 1), loc="upper left")
    plt.tight_layout()


# Make plots
plot_times = comsol_variables["time"][0::10]
plot_error = "both"
# plot_times = [600, 1200, 1800, 2400, 3000]
# voltage
time_only_plot("Terminal voltage [V]", plot_error=plot_error)
# volume averaged temperature
time_only_plot("Volume-averaged cell temperature [K]", plot_error=plot_error)
# heat sources
whole_cell_by_domain_comparison_plot(
    "Irreversible electrochemical heating [W.m-3]",
    plot_times=plot_times,
    plot_error=plot_error,
)
whole_cell_by_domain_comparison_plot(
    "Reversible heating [W.m-3]", plot_times=plot_times, plot_error=plot_error
)
whole_cell_by_domain_comparison_plot(
    "Total heating [W.m-3]", plot_times=plot_times, plot_error=plot_error
)
# temperature
# whole_cell_comparison_plot(
#     "Cell temperature [K]", plot_times=plot_times, plot_error=plot_error
# )
# potentials
electrode_comparison_plot(
    "electrode potential [V]", plot_times=plot_times, plot_error=plot_error
)
plt.savefig("thermal1D_phi_s.eps", format="eps", dpi=1000)
whole_cell_comparison_plot(
    "Electrolyte potential [V]", plot_times=plot_times, plot_error=plot_error
)
plt.savefig("thermal1D_phi_e.eps", format="eps", dpi=1000)
# current
electrode_comparison_plot(
    "electrode current density [A.m-2]", plot_times=plot_times, plot_error=plot_error
)
plt.savefig("thermal1D_i_s.eps", format="eps", dpi=1000)
whole_cell_by_domain_comparison_plot(
    "Electrolyte current density [A.m-2]", plot_times=plot_times, plot_error=plot_error
)
plt.savefig("thermal1D_i_e.eps", format="eps", dpi=1000)
# concentrations
electrode_comparison_plot(
    "particle surface concentration [mol.m-3]",
    plot_times=plot_times,
    plot_error=plot_error,
)
plt.savefig("thermal1D_c_surf.eps", format="eps", dpi=1000)
whole_cell_comparison_plot(
    "Electrolyte concentration [mol.m-3]", plot_times=plot_times, plot_error=plot_error
)
plt.savefig("thermal1D_c_e.eps", format="eps", dpi=1000)
plt.show()
