import os
from pathlib import Path
from typing import Tuple
import numpy as np

try:
    import gmsh
    GMSH_AVAILABLE = True
except ImportError:
    GMSH_AVAILABLE = False


def generate_naca4_coords(m: float = 0.02, p: float = 0.20, t: float = 0.12, c: float = 1.0, n_pts: int = 100) -> np.ndarray:
    """Génère les coordonnées (x, y) d'un profil NACA 4-chiffres quelconque."""
    beta = np.linspace(0, np.pi, n_pts)
    x = c * 0.5 * (1.0 - np.cos(beta))
    xc = x / c

    if m > 1e-6 and p > 1e-6:
        yc = np.where(
            xc < p,
            (m / (p**2)) * (2.0 * p * xc - xc**2),
            (m / ((1.0 - p)**2)) * ((1.0 - 2.0 * p) + 2.0 * p * xc - xc**2)
        )
        dyc_dx = np.where(
            xc < p,
            (2.0 * m / (p**2)) * (p - xc),
            (2.0 * m / ((1.0 - p)**2)) * (p - xc)
        )
    else:
        yc = np.zeros_like(xc)
        dyc_dx = np.zeros_like(xc)

    yt = 5.0 * t * (0.2969 * np.sqrt(np.maximum(0.0, xc)) - 0.1260 * xc - 0.3516 * (xc**2) + 0.2843 * (xc**3) - 0.1015 * (xc**4))
    theta = np.arctan(dyc_dx)

    xu, yu = x - yt * c * np.sin(theta), yc + yt * c * np.cos(theta)
    xl, yl = x + yt * c * np.sin(theta), yc - yt * c * np.cos(theta)

    return np.vstack([
        np.column_stack([xu[::-1], yu[::-1]]),
        np.column_stack([xl[1:], yl[1:]])
    ])


def generate_airfoil_mesh(
    output_path: Path,
    m: float = 0.02,
    p: float = 0.20,
    t: float = 0.12,
    c: float = 1.0,
    verbosity: int = 0,
) -> Path:
    """Génère un maillage Nastran .bdf avec Gmsh en garantissant la conformité stricte avec Fluent 2026 R1.
    
    Attribution des tags physiques identiques à solve_test.jou :
    - Tag 1 : Surface fluide (solid-1 -> fluid)
    - Tag 2 : wall-2 -> Inlet_top
    - Tag 3 : wall-3 -> Inlet_bottom
    - Tag 4 : wall-4 -> bottom (symétrie)
    - Tag 5 : wall-5 -> outlet
    - Tag 6 : wall-6 -> top (symétrie)
    - Tag 7 : wall-7 -> airfoil (profil)
    """
    if not GMSH_AVAILABLE:
        raise RuntimeError("La bibliothèque Gmsh n'est pas installée dans l'environnement Python.")

    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Verbosity", verbosity)
        gmsh.model.add(f"naca_{int(round(m*100)):01d}{int(round(p*10)):01d}{int(round(t*100)):02d}")

        r_far = 15.0 * c
        x_wake = 20.0 * c
        lc_le_te, lc_mid, lc_far = 0.001 * c, 0.005 * c, 1.0 * c

        # 1. Coordonnées et courbe spline du profil
        coords = generate_naca4_coords(m=m, p=p, t=t, c=c)
        airfoil_pts = []
        for x, y in coords:
            lc = lc_le_te if (x < 0.05 * c or x > 0.95 * c) else lc_mid
            airfoil_pts.append(gmsh.model.geo.addPoint(x, y, 0.0, lc))
        airfoil_pts.append(airfoil_pts[0])
        airfoil_spline = gmsh.model.geo.addSpline(airfoil_pts)
        airfoil_loop = gmsh.model.geo.addCurveLoop([airfoil_spline])

        # 2. Contour extérieur en C
        c_center = gmsh.model.geo.addPoint(0.0, 0.0, 0.0, lc_far)
        p_top = gmsh.model.geo.addPoint(0.0, r_far, 0.0, lc_far)
        p_inlet = gmsh.model.geo.addPoint(-r_far, 0.0, 0.0, lc_far)
        p_bot = gmsh.model.geo.addPoint(0.0, -r_far, 0.0, lc_far)
        p_wake_top = gmsh.model.geo.addPoint(x_wake, r_far, 0.0, lc_far)
        p_wake_bot = gmsh.model.geo.addPoint(x_wake, -r_far, 0.0, lc_far)

        arc_top = gmsh.model.geo.addCircleArc(p_top, c_center, p_inlet)
        arc_bot = gmsh.model.geo.addCircleArc(p_inlet, c_center, p_bot)
        l_bot_wake = gmsh.model.geo.addLine(p_bot, p_wake_bot)
        l_outlet = gmsh.model.geo.addLine(p_wake_bot, p_wake_top)
        l_top_wake = gmsh.model.geo.addLine(p_wake_top, p_top)

        domain_loop = gmsh.model.geo.addCurveLoop([arc_top, arc_bot, l_bot_wake, l_outlet, l_top_wake])
        surface = gmsh.model.geo.addPlaneSurface([domain_loop, airfoil_loop])
        gmsh.model.geo.synchronize()

        # 3. Couche limite prismatique
        bl = gmsh.model.mesh.field.add("BoundaryLayer")
        gmsh.model.mesh.field.setNumbers(bl, "CurvesList", [airfoil_spline])
        gmsh.model.mesh.field.setNumber(bl, "Size", 0.0001 * c)
        gmsh.model.mesh.field.setNumber(bl, "Ratio", 1.18)
        gmsh.model.mesh.field.setNumber(bl, "Thickness", 0.02 * c)
        gmsh.model.mesh.field.setNumber(bl, "Quads", 1)
        gmsh.model.mesh.field.setAsBoundaryLayer(bl)

        # 4. Raffinement sillage
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

        # 5. Attributions strictes des groupes physiques pour Fluent 2026 R1
        gmsh.model.addPhysicalGroup(2, [surface], tag=1, name="fluid")
        gmsh.model.addPhysicalGroup(1, [arc_top], tag=2, name="Inlet_top")
        gmsh.model.addPhysicalGroup(1, [arc_bot], tag=3, name="Inlet_bottom")
        gmsh.model.addPhysicalGroup(1, [l_bot_wake], tag=4, name="bottom")
        gmsh.model.addPhysicalGroup(1, [l_outlet], tag=5, name="outlet")
        gmsh.model.addPhysicalGroup(1, [l_top_wake], tag=6, name="top")
        gmsh.model.addPhysicalGroup(1, [airfoil_spline], tag=7, name="airfoil")

        # Génération
        gmsh.option.setNumber("Mesh.Algorithm", 6)
        gmsh.model.mesh.generate(2)
        gmsh.write(str(output_path))
    finally:
        gmsh.finalize()

    return output_path


class MeshManager:
    """Gestionnaire de cache et de génération à la volée des maillages CFD."""

    def __init__(self, cache_dir: Path = Path("meshes")):
        self.cache_dir = Path(cache_dir).resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_mesh_for_parameters(
        self,
        m: float = 0.02,
        p: float = 0.20,
        t: float = 0.12,
        c: float = 1.0,
        base_fallback: Optional[Path] = None,
    ) -> Path:
        """Fournit le fichier de maillage correspondant aux paramètres, en le générant si nécessaire."""
        # Si paramètres correspondent exactement au cas NACA 2212 de référence et que profil_test.bdf existe
        is_default_2212 = (
            abs(m - 0.02) < 1e-4 and
            abs(p - 0.20) < 1e-4 and
            abs(t - 0.12) < 1e-4 and
            abs(c - 1.0) < 1e-4
        )
        if is_default_2212:
            candidate = Path("profil_test.bdf").resolve()
            if candidate.is_file():
                return candidate

        m_code = int(round(m * 100))
        p_code = int(round(p * 10)) if m > 1e-4 else 0
        t_code = int(round(t * 100))
        c_code = int(round(c * 1000))

        filename = f"naca_{m_code:01d}{p_code:01d}{t_code:02d}_c{c_code}mm.bdf"
        cached_mesh = self.cache_dir / filename

        if cached_mesh.is_file():
            return cached_mesh

        # Génération dynamique avec Gmsh
        generate_airfoil_mesh(cached_mesh, m=m, p=p, t=t, c=c)
        return cached_mesh
