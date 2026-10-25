from pathlib import Path
from typing import Union
from core.case_model import PhysicalParameters, SimulationCase


def generate_fluent_journal(
    case_or_params: Union[SimulationCase, PhysicalParameters],
    output_path: Path,
    mesh_filename: str = "profil_test.bdf",
) -> Path:
    """Génère un journal Fluent (.jou) valide pour ANSYS Fluent 2026 R1.
    
    Repose sur la syntaxe testée et validée dans solve_test.jou :
    - Import Nastran bulkdata
    - Renommage et attribution des types de zones
    - Modèle de turbulence k-omega SST
    - Vitesse de l'écoulement projetée selon l'angle d'incidence alpha
    - Solveur Coupled et schémas du second ordre
    - Valeurs de référence (vitesse, densité, longueur, aire)
    - Définitions de CL et CD avec projection des vecteurs de force aérodynamique
    - Export des coefficients et de la distribution de pression
    """
    if isinstance(case_or_params, SimulationCase):
        p = case_or_params.parameters
    else:
        p = case_or_params

    output_path = Path(output_path)
    mesh_name = Path(mesh_filename).name

    # Calculs aérodynamiques
    vx = p.vx
    vy = p.vy
    fx_lift, fy_lift = p.lift_force_vector
    fx_drag, fy_drag = p.drag_force_vector
    area = p.chord * 1.0  # Profondeur unitaire 1m en 2D

    journal_content = f"""; =====================================================================
; Journal Fluent généré automatiquement par Fluent Simulation Manager
; Profil : NACA 2212 2D
; Incidence alpha : {p.alpha_deg:.2f}° | Vitesse : {p.velocity:.2f} m/s
; Corde : {p.chord:.3f} m | Masse volumique : {p.density:.4f} kg/m3
; Itérations : {p.iterations} | Modèle : {p.turbulence_model}
; =====================================================================

; 1. Import du maillage + controles dans la console
/file/import/nastran/bulkdata "{mesh_name}"
/mesh/check
/define/boundary-conditions/list-zones

; 2. Zone de cellules : renommer d'abord, puis changer le type en fluide
/define/boundary-conditions/modify-zones/zone-name solid-1 fluid
/define/boundary-conditions/modify-zones/zone-type fluid fluid
; Materiau air (arguments valides en 2026 R1)
/define/boundary-conditions/fluid fluid yes air no no no no 0 no 0 no no no no

; 3. Frontieres : renommer AVANT de changer le type
/define/boundary-conditions/modify-zones/zone-name wall-2 Inlet_top
/define/boundary-conditions/modify-zones/zone-name wall-3 Inlet_bottom
/define/boundary-conditions/modify-zones/zone-name wall-4 bottom
/define/boundary-conditions/modify-zones/zone-name wall-5 outlet
/define/boundary-conditions/modify-zones/zone-name wall-6 top
/define/boundary-conditions/modify-zones/zone-name wall-7 airfoil

/define/boundary-conditions/modify-zones/zone-type Inlet_top velocity-inlet
/define/boundary-conditions/modify-zones/zone-type Inlet_bottom velocity-inlet
/define/boundary-conditions/modify-zones/zone-type outlet pressure-outlet
/define/boundary-conditions/modify-zones/zone-type bottom symmetry
/define/boundary-conditions/modify-zones/zone-type top symmetry

; 4. Modele de turbulence k-omega SST
/define/models/viscous/kw-sst? yes

; 5. Vitesse sur les entrees (Vx = {vx:.4f} m/s, Vy = {vy:.4f} m/s)
; Turbulence = Intensity and Viscosity Ratio (0.1 %, ratio 10)
/define/boundary-conditions/velocity-inlet inlet_top no yes yes no 0 no {vx:.6f} no {vy:.6f} no no yes 0.1 10
/define/boundary-conditions/velocity-inlet inlet_bottom no yes yes no 0 no {vx:.6f} no {vy:.6f} no no yes 0.1 10

; 6. Solveur Coupled et schemas du second ordre
/solve/set/p-v-coupling 24
/solve/set/discretization-scheme/pressure 12
/solve/set/discretization-scheme/mom 1
/solve/set/discretization-scheme/k 1
/solve/set/discretization-scheme/omega 1

; 7. Valeurs de reference
/report/reference-values/area {area:.4f}
/report/reference-values/length {p.chord:.4f}
/report/reference-values/velocity {p.velocity:.4f}
/report/reference-values/density {p.density:.4f}

; 8. Definitions de Cl et Cd avec vecteurs de force orientes
/solve/report-definitions/add cl-rep lift thread-names airfoil

force-vector {fx_lift:.6f} {fy_lift:.6f} scaled? yes q
/solve/report-definitions/add cd-rep drag thread-names airfoil

force-vector {fx_drag:.6f} {fy_drag:.6f} scaled? yes q
/solve/report-definitions/list

; 9. Fichiers de rapport des coefficients par iteration
/solve/report-files/add cl-file active? yes report-defs cl-rep () file-name "cl_test.txt" print? no q
/solve/report-files/add cd-file active? yes report-defs cd-rep () file-name "cd_test.txt" print? no q

; 10. Criteres de convergence stricts
/solve/monitors/residual/convergence-criteria 1e-8 1e-8 1e-8 1e-8 1e-8

; 11. Initialisation hybride et sauvegarde pre-calcul
/solve/initialize/hyb-initialization
/file/write-case before_run.cas.h5

; 12. Calcul
/solve/iterate {p.iterations}

; 13. Sauvegarde finale
/file/write-case-data result.cas.h5

; 14. Export automatique des donnees de pression sur le profil
/file/export/ascii airfoil_pressure.csv
airfoil yes x-coordinate y-coordinate pressure total-pressure () no

; 15. Fermeture
/exit yes
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(journal_content)
    return output_path
