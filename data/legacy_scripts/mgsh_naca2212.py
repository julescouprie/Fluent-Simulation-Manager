import os
import gmsh
import numpy as np

def generate_naca4(m=0.02, p=0.2, t=0.12, c=1.0, n_pts=80):
    """Génère les coordonnées (x, y) du profil NACA."""
    beta = np.linspace(0, np.pi, n_pts)
    x = c * 0.5 * (1.0 - np.cos(beta))
    xc = x / c

    yc = np.where(xc < p,
                  (m / (p**2)) * (2.0 * p * xc - xc**2),
                  (m / ((1.0 - p)**2)) * ((1.0 - 2.0 * p) + 2.0 * p * xc - xc**2))
    dyc_dx = np.where(xc < p,
                      (2.0 * m / (p**2)) * (p - xc),
                      (2.0 * m / ((1.0 - p)**2)) * (p - xc))

    yt = 5.0 * t * (0.2969*np.sqrt(xc) - 0.1260*xc - 0.3516*(xc**2) + 0.2843*(xc**3) - 0.1015*(xc**4))
    theta = np.arctan(dyc_dx)

    xu, yu = x - yt * c * np.sin(theta), yc + yt * c * np.cos(theta)
    xl, yl = x + yt * c * np.sin(theta), yc - yt * c * np.cos(theta)

    return np.vstack([
        np.column_stack([xu[::-1], yu[::-1]]),
        np.column_stack([xl[1:], yl[1:]])
    ])

def export_test_bdf(output_path, m=0.02, p=0.2):
    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 1)
    gmsh.model.add("c_grid_airfoil")

    c = 1.0
    r_far = 15.0 * c
    x_wake = 20.0 * c
    lc_le_te, lc_mid, lc_far = 0.001 * c, 0.005 * c, 1.0 * c

    # 1. Profil (airfoil)
    coords = generate_naca4(m=m, p=p, c=c)
    airfoil_pts = []
    for x, y in coords:
        lc = lc_le_te if (x < 0.05 * c or x > 0.95 * c) else lc_mid
        airfoil_pts.append(gmsh.model.geo.addPoint(x, y, 0.0, lc))
    airfoil_pts.append(airfoil_pts[0])
    airfoil_spline = gmsh.model.geo.addSpline(airfoil_pts)
    airfoil_loop = gmsh.model.geo.addCurveLoop([airfoil_spline])

    # 2. Contour extérieur en C
    c_center   = gmsh.model.geo.addPoint(0.0, 0.0, 0.0, lc_far)
    p_top      = gmsh.model.geo.addPoint(0.0, r_far, 0.0, lc_far)
    p_inlet    = gmsh.model.geo.addPoint(-r_far, 0.0, 0.0, lc_far)
    p_bot      = gmsh.model.geo.addPoint(0.0, -r_far, 0.0, lc_far)
    p_wake_top = gmsh.model.geo.addPoint(x_wake, r_far, 0.0, lc_far)
    p_wake_bot = gmsh.model.geo.addPoint(x_wake, -r_far, 0.0, lc_far)

    arc_top    = gmsh.model.geo.addCircleArc(p_top, c_center, p_inlet)
    arc_bot    = gmsh.model.geo.addCircleArc(p_inlet, c_center, p_bot)
    l_bot_wake = gmsh.model.geo.addLine(p_bot, p_wake_bot)
    l_outlet   = gmsh.model.geo.addLine(p_wake_bot, p_wake_top)
    l_top_wake = gmsh.model.geo.addLine(p_wake_top, p_top)

    domain_loop = gmsh.model.geo.addCurveLoop([arc_top, arc_bot, l_bot_wake, l_outlet, l_top_wake])
    surface = gmsh.model.geo.addPlaneSurface([domain_loop, airfoil_loop])
    gmsh.model.geo.synchronize()

    # 3. Couche limite prismatique sur la paroi
    bl = gmsh.model.mesh.field.add("BoundaryLayer")
    gmsh.model.mesh.field.setNumbers(bl, "CurvesList", [airfoil_spline])
    gmsh.model.mesh.field.setNumber(bl, "Size", 0.0001 * c)
    gmsh.model.mesh.field.setNumber(bl, "Ratio", 1.18)
    gmsh.model.mesh.field.setNumber(bl, "Thickness", 0.02 * c)
    gmsh.model.mesh.field.setNumber(bl, "Quads", 1)
    gmsh.model.mesh.field.setAsBoundaryLayer(bl)

    # 4. Raffinement du sillage et transition
    f_wake = gmsh.model.mesh.field.add("Box")
    gmsh.model.mesh.field.setNumber(f_wake, "VIn", 0.015 * c)
    gmsh.model.mesh.field.setNumber(f_wake, "VOut", lc_far)
    gmsh.model.mesh.field.setNumber(f_wake, "XMin", 0.0)
    gmsh.model.mesh.field.setNumber(f_wake, "XMax", 6.0 * c)
    gmsh.model.mesh.field.setNumber(f_wake, "YMin", -0.4 * c)
    gmsh.model.mesh.field.setNumber(f_wake, "YMax", 0.4 * c)

    f_dist = gmsh.model.mesh.field.add("Distance")
    gmsh.model.mesh.field.setNumbers(f_dist, "CurvesList", [airfoil_spline])

    f_thresh = gmsh.model.mesh.field.add("Threshold")
    gmsh.model.mesh.field.setNumber(f_thresh, "InField", f_dist)
    gmsh.model.mesh.field.setNumber(f_thresh, "SizeMin", 0.005 * c)
    gmsh.model.mesh.field.setNumber(f_thresh, "SizeMax", lc_far)
    gmsh.model.mesh.field.setNumber(f_thresh, "DistMin", 0.05 * c)
    gmsh.model.mesh.field.setNumber(f_thresh, "DistMax", 4.0 * c)

    f_min = gmsh.model.mesh.field.add("Min")
    gmsh.model.mesh.field.setNumbers(f_min, "FieldsList", [f_wake, f_thresh])
    gmsh.model.mesh.field.setAsBackgroundMesh(f_min)

    # -------------------------------------------------------------
    # ATTRIBUTION STRICTE DES TAGS POUR CORRESPONDRE AU JOURNAL FLUENT
    # -------------------------------------------------------------
    # Tag 1  -> solid-1 dans Fluent (Surface 2D fluide)
    gmsh.model.addPhysicalGroup(2, [surface], tag=1, name="fluid")

    # Tag 2  -> wall-2 dans Fluent (Inlet_top)
    gmsh.model.addPhysicalGroup(1, [arc_top], tag=2, name="Inlet_top")

    # Tag 3  -> wall-3 dans Fluent (Inlet_bottom)
    gmsh.model.addPhysicalGroup(1, [arc_bot], tag=3, name="Inlet_bottom")

    # Tag 4  -> wall-4 dans Fluent (bottom)
    gmsh.model.addPhysicalGroup(1, [l_bot_wake], tag=4, name="bottom")

    # Tag 5  -> wall-5 dans Fluent (outlet)
    gmsh.model.addPhysicalGroup(1, [l_outlet], tag=5, name="outlet")

    # Tag 6  -> wall-6 dans Fluent (top)
    gmsh.model.addPhysicalGroup(1, [l_top_wake], tag=6, name="top")

    # Tag 7  -> wall-7 dans Fluent (airfoil)
    gmsh.model.addPhysicalGroup(1, [airfoil_spline], tag=7, name="airfoil")

    # Génération et écriture du maillage BDF
    gmsh.option.setNumber("Mesh.Algorithm", 6)
    gmsh.model.mesh.generate(2)
    gmsh.write(output_path)
    gmsh.finalize()
    print(f"Fichier Nastran généré avec succès : {output_path}")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_bdf = os.path.join(script_dir, "profil_test.bdf")
    export_test_bdf(out_bdf, m=0.02, p=0.2)