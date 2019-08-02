#
# Test for the scikit-fem Finite Element Mesh class
#
import pybamm
import unittest


@unittest.skipIf(pybamm.have_scikit_fem(), "scikit-fem not installed")
class TestScikitFiniteElement2DSubMesh(unittest.TestCase):
    def test_mesh_creation(self):
        param = pybamm.ParameterValues(
            base_parameters={
                "Electrode depth [m]": 0.4,
                "Electrode height [m]": 0.5,
                "Negative tab width [m]": 0.1,
                "Negative tab centre y-coordinate [m]": 0.1,
                "Negative tab centre z-coordinate [m]": 0.5,
                "Positive tab width [m]": 0.1,
                "Positive tab centre y-coordinate [m]": 0.3,
                "Positive tab centre z-coordinate [m]": 0.5,
                "Negative electrode width [m]": 0.3,
                "Separator width [m]": 0.3,
                "Positive electrode width [m]": 0.3,
            }
        )

        geometry = pybamm.Geometryxp1DMacro(cc_dimension=2)
        param.process_geometry(geometry)

        var = pybamm.standard_spatial_vars
        var_pts = {var.x_n: 10, var.x_s: 7, var.x_p: 12, var.y: 16, var.z: 24}

        submesh_types = {
            "negative electrode": pybamm.Uniform1DSubMesh,
            "separator": pybamm.Uniform1DSubMesh,
            "positive electrode": pybamm.Uniform1DSubMesh,
            "current collector": pybamm.Scikit2DSubMesh,
        }

        mesh_type = pybamm.Mesh

        # create mesh
        mesh = mesh_type(geometry, submesh_types, var_pts)

        # check boundary locations
        self.assertEqual(mesh["negative electrode"][0].edges[0], 0)
        self.assertEqual(mesh["positive electrode"][0].edges[-1], 1)

        # check internal boundary locations
        self.assertEqual(
            mesh["negative electrode"][0].edges[-1], mesh["separator"][0].edges[0]
        )
        self.assertEqual(
            mesh["positive electrode"][0].edges[0], mesh["separator"][0].edges[-1]
        )
        for domain in mesh:
            if domain == "current collector":
                # NOTE: only for degree 1
                npts = var_pts[var.y] * var_pts[var.z]
                self.assertEqual(mesh[domain][0].npts, npts)
            else:
                self.assertEqual(
                    len(mesh[domain][0].edges), len(mesh[domain][0].nodes) + 1
                )

    def test_init_failure(self):
        submesh_types = {
            "negative electrode": pybamm.Uniform1DSubMesh,
            "separator": pybamm.Uniform1DSubMesh,
            "positive electrode": pybamm.Uniform1DSubMesh,
            "current collector": pybamm.Scikit2DSubMesh,
        }
        geometry = pybamm.Geometryxp1DMacro(cc_dimension=2)
        with self.assertRaises(KeyError):
            pybamm.Mesh(geometry, submesh_types, {})

        var = pybamm.standard_spatial_vars
        var_pts = {var.x_n: 10, var.x_s: 10, var.x_p: 10, var.y: 10, var.z: 10}
        with self.assertRaises(TypeError):
            pybamm.Mesh(geometry, submesh_types, var_pts)

        lims = {var.x_n: {"min": pybamm.Scalar(0), "max": pybamm.Scalar(1)}}
        with self.assertRaises(pybamm.GeometryError):
            pybamm.Scikit2DSubMesh(lims, None, None)

        lims = {
            var.x_n: {"min": pybamm.Scalar(0), "max": pybamm.Scalar(1)},
            var.x_p: {"min": pybamm.Scalar(0), "max": pybamm.Scalar(1)},
        }
        with self.assertRaises(pybamm.DomainError):
            pybamm.Scikit2DSubMesh(lims, None, None)

        lims = {
            var.y: {"min": pybamm.Scalar(0), "max": pybamm.Scalar(1)},
            var.z: {"min": pybamm.Scalar(0), "max": pybamm.Scalar(1)},
        }
        npts = {var.y.id: 10, var.z.id: 10}
        var.z.coord_sys = "not cartesian"
        with self.assertRaises(pybamm.DomainError):
            pybamm.Scikit2DSubMesh(lims, npts, None)
        var.z.coord_sys = "cartesian"

    def test_tab_error(self):
        # set variables and submesh types
        var = pybamm.standard_spatial_vars
        var_pts = {var.x_n: 2, var.x_s: 2, var.x_p: 2, var.y: 64, var.z: 64}

        submesh_types = {
            "negative electrode": pybamm.Uniform1DSubMesh,
            "separator": pybamm.Uniform1DSubMesh,
            "positive electrode": pybamm.Uniform1DSubMesh,
            "current collector": pybamm.Scikit2DSubMesh,
        }

        mesh_type = pybamm.Mesh

        # set base parameters
        param = pybamm.ParameterValues(
            base_parameters={
                "Electrode depth [m]": 0.4,
                "Electrode height [m]": 0.5,
                "Negative tab width [m]": 0.1,
                "Negative tab centre y-coordinate [m]": 0.1,
                "Negative tab centre z-coordinate [m]": 0.5,
                "Positive tab centre y-coordinate [m]": 10,
                "Positive tab centre z-coordinate [m]": 10,
                "Positive tab width [m]": 0.1,
                "Negative electrode width [m]": 0.3,
                "Separator width [m]": 0.3,
                "Positive electrode width [m]": 0.3,
            }
        )

        # check error raised if tab not on boundary
        geometry = pybamm.Geometryxp1DMacro(cc_dimension=2)
        param.process_geometry(geometry)
        with self.assertRaises(pybamm.GeometryError):
            mesh_type(geometry, submesh_types, var_pts)

    def test_tab_left_right(self):
        # set variables and submesh types
        var = pybamm.standard_spatial_vars
        var_pts = {var.x_n: 2, var.x_s: 2, var.x_p: 2, var.y: 64, var.z: 64}

        submesh_types = {
            "negative electrode": pybamm.Uniform1DSubMesh,
            "separator": pybamm.Uniform1DSubMesh,
            "positive electrode": pybamm.Uniform1DSubMesh,
            "current collector": pybamm.Scikit2DSubMesh,
        }

        mesh_type = pybamm.Mesh

        # set base parameters
        param = pybamm.ParameterValues(
            base_parameters={
                "Electrode depth [m]": 0.4,
                "Electrode height [m]": 0.5,
                "Negative tab width [m]": 0.1,
                "Negative tab centre y-coordinate [m]": 0.0,
                "Negative tab centre z-coordinate [m]": 0.25,
                "Positive tab centre y-coordinate [m]": 0.4,
                "Positive tab centre z-coordinate [m]": 0.25,
                "Positive tab width [m]": 0.1,
                "Negative electrode width [m]": 0.3,
                "Separator width [m]": 0.3,
                "Positive electrode width [m]": 0.3,
            }
        )

        # check error raised if tab not on boundary
        geometry = pybamm.Geometryxp1DMacro(cc_dimension=2)
        param.process_geometry(geometry)
        mesh_type(geometry, submesh_types, var_pts)


if __name__ == "__main__":
    print("Add -v for more debug output")
    import sys

    if "-v" in sys.argv:
        debug = True
    pybamm.settings.debug_mode = True
    unittest.main()
