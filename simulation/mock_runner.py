import math
from pathlib import Path
import random
import re
import shutil
import time
from typing import Callable, Optional
import numpy as np
from core.case_model import SimulationCase, CaseStatus, DataOrigin


class MockFluentRunner:
    """Simulateur de calcul ANSYS Fluent pour tests, démonstration et validation sans licence."""

    def __init__(
        self,
        base_runs_dir: Path = Path("runs"),
        on_log: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
        speed_factor: float = 1.0,  # 1.0 = simulation en quelques secondes
    ):
        self.base_runs_dir = Path(base_runs_dir)
        self.on_log = on_log
        self.on_progress = on_progress
        self.speed_factor = speed_factor
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True
        self._log("[ANNULATION] Annulation demandée pour la simulation fictive...")

    def _log(self, message: str) -> None:
        if self.on_log:
            self.on_log(message)

    def _update_progress(self, current: int, total: int) -> None:
        if self.on_progress:
            self.on_progress(current, total)

    def run(self, case: SimulationCase, original_mesh_path: Optional[Path] = None) -> bool:
        self._is_cancelled = False
        case.start_time = time.time()
        case.status = CaseStatus.PREPARATION
        case.data_origin = DataOrigin.SYNTHETIC_MOCK
        case.error_message = ""
        case.current_iteration = 0
        case.total_iterations = case.parameters.iterations
        self._update_progress(0, case.total_iterations)

        # Vérification si échec simulé demandé
        should_fail = (
            "fail" in case.name.lower()
            or "echec" in case.name.lower()
            or "erreur" in case.name.lower()
        )

        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", case.name)
        case_dir = (self.base_runs_dir / f"{case.id}_{safe_name}_{timestamp_str}").resolve()
        case_dir.mkdir(parents=True, exist_ok=True)

        case.work_dir = str(case_dir)
        case.log_file = str(case_dir / "fluent_execution.log")
        log_path = Path(case.log_file)

        self._log(f"=== [MODE FICTIF] Démarrage du calcul test pour {case.name} [{case.id}] ===")
        self._log(f"Dossier de travail : {case_dir}")
        self._log(f"Paramètres : Alpha={case.parameters.alpha_deg:.2f}°, V={case.parameters.velocity:.2f} m/s, Iters={case.parameters.iterations}")
        case.status = CaseStatus.EN_COURS

        start_time = time.time()
        total_iters = case.parameters.iterations
        step_count = min(total_iters, 25)  # 25 étapes d'affichage pour une simulation fluide
        iter_step = max(1, total_iters // step_count)

        with open(log_path, "w", encoding="utf-8") as log_f:
            header = "  iter  continuity     x-velocity     y-velocity          k      omega     time/iter\n"
            log_f.write(header)
            self._log(header.strip())

            current_it = 0
            for step in range(1, step_count + 1):
                if self._is_cancelled:
                    case.status = CaseStatus.ANNULEE
                    case.error_message = "Simulation fictive annulée par l'utilisateur."
                    case.end_time = time.time()
                    case.duration_seconds = case.end_time - start_time
                    self._log(f"[ANNULATION] {case.name} interrompue.")
                    return False

                # Si simulation d'échec programmée au milieu du calcul
                if should_fail and step >= (step_count // 2):
                    case.status = CaseStatus.ECHEC
                    case.error_message = "Divergence numérique simulée (Floating point exception: divergence detected)."
                    case.end_time = time.time()
                    case.duration_seconds = case.end_time - start_time
                    self._log(f"[ERREUR FICTIVE] {case.error_message}")
                    log_f.write(f"\n[FATAL ERROR] {case.error_message}\n")
                    return False

                current_it = min(total_iters, step * iter_step)
                res_cont = 1.0 * (0.85 ** step)
                res_vx = 0.8 * (0.87 ** step)
                res_vy = 0.7 * (0.88 ** step)
                line = f"{current_it:6d}  {res_cont:1.4e}     {res_vx:1.4e}     {res_vy:1.4e}  1.234e-03  4.567e-02  0:00:01  {total_iters}\n"
                log_f.write(line)
                log_f.flush()
                self._log(line.strip())

                case.current_iteration = current_it
                case.progress_percent = min(100, int((current_it / total_iters) * 100))
                self._update_progress(current_it, total_iters)

                time.sleep(0.04 * (1.0 / self.speed_factor))

            case.current_iteration = total_iters
            case.progress_percent = 100
            self._update_progress(total_iters, total_iters)

        case.end_time = time.time()
        case.duration_seconds = case.end_time - start_time

        # Génération des fichiers de résultats réalistes pour un NACA 2212
        self._generate_synthetic_results(case, case_dir)

        case.status = CaseStatus.POST_TRAITEMENT
        self._log(f"[MODE FICTIF] Calcul terminé avec succès pour {case.id}.")
        return True

    def _generate_synthetic_results(self, case: SimulationCase, case_dir: Path) -> None:
        """Produit des fichiers cl_test.txt, cd_test.txt et airfoil_pressure.csv réalistes fondés sur la théorie aérodynamique."""
        alpha = case.parameters.alpha_deg
        m = case.parameters.camber_m
        t = case.parameters.thickness_t
        p = case.parameters.camber_p

        # Théorie des profils minces (Abbott & von Doenhoff) :
        # Pente de portance ~ 2*pi / rad = 0.1097 / deg
        # Angle de portance nulle alpha_0 ~ -115 * m deg
        alpha_0 = -115.0 * m
        cl_asymptote = 0.1097 * (alpha - alpha_0)

        # Traînée de frottement et de profil Cd0 fonction de l'épaisseur + traînée induite k*CL^2
        cd0 = 0.0055 + 0.035 * t + 0.015 * m
        cd_asymptote = cd0 + (0.040 + 0.02 * t) * (cl_asymptote ** 2)

        total_iters = case.parameters.iterations
        cl_file = case_dir / "cl_test.txt"
        cd_file = case_dir / "cd_test.txt"

        # Écriture cl_test.txt et cd_test.txt
        with open(cl_file, "w", encoding="utf-8") as f_cl, open(cd_file, "w", encoding="utf-8") as f_cd:
            f_cl.write('((cl-rep "lift")\n')
            f_cd.write('((cd-rep "drag")\n')

            for it in range(1, total_iters + 1):
                decay = math.exp(- 15.0 * it / max(1, total_iters))
                noise_cl = (random.random() - 0.5) * 0.005 * decay
                noise_cd = (random.random() - 0.5) * 0.001 * decay
                val_cl = cl_asymptote * (1.0 - 0.3 * decay) + noise_cl
                val_cd = cd_asymptote * (1.0 + 0.5 * decay) + noise_cd

                f_cl.write(f" {it} {val_cl:.6f}\n")
                f_cd.write(f" {it} {val_cd:.6f}\n")

            f_cl.write(")\n")
            f_cd.write(")\n")

        # Écriture airfoil_pressure.csv
        # Coordonnées NACA 2212 et distribution de pression Cp
        csv_file = case_dir / "airfoil_pressure.csv"
        chord = case.parameters.chord
        q_ref = case.parameters.dynamic_pressure
        p_ref = case.parameters.pressure_ref

        n_pts = 100
        x_norm = np.linspace(0.0, 1.0, n_pts)
        
        # Succion extrados (upper) et suppression intrados (lower)
        # Cp_upper : pic de succion à x/c ~ 0.05
        cp_upper = - (1.2 + 0.25 * max(0.0, alpha)) * np.exp(-x_norm / 0.15) + (1.0 - x_norm) * 0.15
        cp_lower = 0.8 * (1.0 - x_norm) * np.exp(-x_norm / 0.3)

        rows = []
        # Upper surface (extrados) de x=0 à 1
        for x_val, cp in zip(x_norm, cp_upper):
            x_m = x_val * chord
            y_m = 0.12 * math.sin(math.pi * x_val) * chord
            p_static = p_ref + cp * q_ref
            p_total = p_static + q_ref
            rows.append((x_m, y_m, p_static, p_total))

        # Lower surface (intrados) de x=1 à 0
        for x_val, cp in zip(reversed(x_norm), reversed(cp_lower)):
            x_m = x_val * chord
            y_m = -0.06 * math.sin(math.pi * x_val) * chord
            p_static = p_ref + cp * q_ref
            p_total = p_static + q_ref
            rows.append((x_m, y_m, p_static, p_total))

        with open(csv_file, "w", encoding="utf-8") as f:
            f.write('"x-coordinate","y-coordinate","pressure","total-pressure"\n')
            for r in rows:
                f.write(f"{r[0]:.6f},{r[1]:.6f},{r[2]:.4f},{r[3]:.4f}\n")
