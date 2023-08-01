import nox
import os
import sys


# Options to modify nox behaviour
nox.options.reuse_existing_virtualenvs = True
if sys.platform == "linux":
    nox.options.sessions = ["pre-commit", "pybamm-requires", "unit"]
else:
    nox.options.sessions = ["pre-commit", "unit"]


homedir = os.getenv("HOME")
PYBAMM_ENV = {
    "SUNDIALS_INST": f"{homedir}/.local",
    "LD_LIBRARY_PATH": f"{homedir}/.local/lib:",
}
# Do not stdout ANSI colours on GitHub Actions
if os.getenv("CI") == "true":
    os.environ["NO_COLOR"] = "1"


def set_environment_variables(env_dict, session):
    """
    Sets environment variables for a nox session object.

    Parameters
    -----------
        session : nox.Session
            The session to set the environment variables for.
        env_dict : dict
            A dictionary of environment variable names and values.

    """
    for key, value in env_dict.items():
        session.env[key] = value


@nox.session(name="pybamm-requires")
def run_pybamm_requires(session):
    """Download, compile, and install the build-time requirements for Linux and macOS: the SuiteSparse and SUNDIALS libraries."""  # noqa: E501
    set_environment_variables(PYBAMM_ENV, session=session)
    if sys.platform != "win32":
        session.install("wget", "cmake")
        session.run("python", "scripts/install_KLU_Sundials.py")
        if not os.path.exists("./pybind11"):
            session.run(
                "git",
                "clone",
                "https://github.com/pybind/pybind11.git",
                "pybind11/",
                external=True,
            )
    else:
        session.error("nox -s pybamm-requires is only available on Linux & MacOS.")


@nox.session(name="coverage")
def run_coverage(session):
    """Run the coverage tests and generate an XML report."""
    set_environment_variables(PYBAMM_ENV, session=session)
    session.install("coverage")
    session.install("-e", ".[all]")
    if sys.platform != "win32":
        session.install("-e", ".[odes]")
        session.install("-e", ".[jax]")
    session.run("coverage", "run", "--rcfile=.coveragerc", "run-tests.py", "--nosub")
    session.run("coverage", "combine")
    session.run("coverage", "xml")


@nox.session(name="integration")
def run_integration(session):
    """Run the integration tests."""
    set_environment_variables(PYBAMM_ENV, session=session)
    session.install("-e", ".[all]")
    if sys.platform == "linux":
        session.install("-e", ".[odes]")
    session.run("python", "run-tests.py", "--integration")


@nox.session(name="doctests")
def run_doctests(session):
    """Run the doctests and generate the output(s) in the docs/build/ directory."""
    session.install("-e", ".[all,docs]")
    session.run("python", "run-tests.py", "--doctest")


@nox.session(name="unit")
def run_unit(session):
    """Run the unit tests."""
    set_environment_variables(PYBAMM_ENV, session=session)
    session.install("-e", ".[all]")
    if sys.platform == "linux":
        session.install("-e", ".[odes]")
        session.install("-e", ".[jax]")
    session.run("python", "run-tests.py", "--unit")


@nox.session(name="examples")
def run_examples(session):
    """Run the examples tests for Jupyter notebooks and Python scripts."""
    session.install("-e", ".[all]")
    session.run("python", "run-tests.py", "--examples")


@nox.session(name="dev")
def set_dev(session):
    """Install PyBaMM in editable mode."""
    set_environment_variables(PYBAMM_ENV, session=session)
    envbindir = session.bin
    session.install("-e", ".[all]")
    session.install("cmake")
    if sys.platform == "linux" or sys.platform == "darwin":
        session.run(
            "echo",
            "export",
            f"LD_LIBRARY_PATH={PYBAMM_ENV['LD_LIBRARY_PATH']}",
            ">>",
            f"{envbindir}/activate",
            external=True,  # silence warning about echo being an external command
        )


@nox.session(name="tests")
def run_tests(session):
    """Run the unit tests and integration tests sequentially."""
    set_environment_variables(PYBAMM_ENV, session=session)
    session.install("-e", ".[all]")
    if sys.platform == "linux" or sys.platform == "darwin":
        session.install("-e", ".[odes]")
        session.install("-e", ".[jax]")
    session.run("python", "run-tests.py", "--all")


@nox.session(name="docs")
def build_docs(session):
    """Build the documentation and load it in a browser tab, rebuilding on changes."""
    envbindir = session.bin
    session.install("-e", ".[all,docs]")
    with session.chdir("docs/"):
        session.run(
            "sphinx-autobuild",
            "-j",
            "auto",
            "--open-browser",
            "-qT",
            ".",
            f"{envbindir}/../tmp/html",
        )


@nox.session(name="pre-commit")
def lint(session):
    """Check all files against the defined pre-commit hooks."""
    session.install("pre-commit")
    session.run("pre-commit", "run", "--all-files")
