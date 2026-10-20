import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
from typing import Callable, Optional
from core.case_model import SimulationCase, CaseStatus
from .journal_generator import generate_fluent_journal
from .process_manager import terminate_process_tree


class FluentRunner:
    """Exécute ANSYS Fluent pour un cas de simulation spécifique."""

    ITER_REGEX = re.compile(r"^\s*(\d+)\s+[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?\s+")

    def __init__(
        self,
        fluent_exe: Path,
        base_runs_dir: Path = Path("runs"),
        on_log: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ):
        self.fluent_exe = Path(fluent_exe)
        self.base_runs_dir = Path(base_runs_dir)
        self.on_log = on_log
        self.on_progress = on_progress
        self.current_process: Optional[subprocess.Popen] = None
        self._is_cancelled = False

    def cancel(self) -> None:
        """Demande l'annulation et l'arrêt propre de Fluent."""
        self._is_cancelled = True
        if self.current_process and self.current_process.pid:
            self._log(f"[ANNULATION] Arrêt du processus Fluent (PID {self.current_process.pid})...")
            terminate_process_tree(self.current_process.pid)

    def _log(self, message: str) -> None:
        if self.on_log:
            self.on_log(message)

    def _update_progress(self, current: int, total: int) -> None:
        if self.on_progress:
            self.on_progress(current, total)

    def prepare_case_directory(self, case: SimulationCase, original_mesh_path: Path) -> Path:
        """Prépare un dossier de travail UNIQUE pour le cas sans écraser d'anciens résultats."""
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", case.name)
        folder_name = f"{case.id}_{safe_name}_{timestamp_str}"
        case_dir = (self.base_runs_dir / folder_name).resolve()
        case_dir.mkdir(parents=True, exist_ok=True)

        # Copie du maillage
        mesh_dest = case_dir / original_mesh_path.name
        shutil.copy2(original_mesh_path, mesh_dest)

        # Génération du journal Fluent
        journal_path = case_dir / "solve.jou"
        generate_fluent_journal(case, journal_path, mesh_filename=original_mesh_path.name)

        case.work_dir = str(case_dir)
        case.log_file = str(case_dir / "fluent_execution.log")
        return case_dir

    def run(self, case: SimulationCase, original_mesh_path: Path) -> bool:
        """Lance l'exécution de Fluent pour le cas donné."""
        self._is_cancelled = False
        case.start_time = time.time()
        case.status = CaseStatus.PREPARATION
        case.error_message = ""
        case.current_iteration = 0
        case.total_iterations = case.parameters.iterations
        self._update_progress(0, case.total_iterations)

        if not self.fluent_exe.is_file():
            case.status = CaseStatus.ECHEC
            case.error_message = f"Exécutable Fluent introuvable : {self.fluent_exe}"
            self._log(f"[ERREUR] {case.error_message}")
            return False

        if not original_mesh_path.is_file():
            case.status = CaseStatus.ECHEC
            case.error_message = f"Fichier de maillage introuvable : {original_mesh_path}"
            self._log(f"[ERREUR] {case.error_message}")
            return False

        # Préparation du répertoire
        try:
            case_dir = self.prepare_case_directory(case, original_mesh_path)
        except Exception as exc:
            case.status = CaseStatus.ECHEC
            case.error_message = f"Erreur lors de la préparation du dossier : {exc}"
            self._log(f"[ERREUR] {case.error_message}")
            return False

        journal_file = case_dir / "solve.jou"
        log_file_path = Path(case.log_file)

        # Construction de la commande Fluent
        cores = max(1, int(case.parameters.cores))
        cmd = [
            str(self.fluent_exe),
            "2d",
            f"-t{cores}",
            "-g",
            "-i",
            journal_file.name,
        ]

        self._log(f"=== Lancement du calcul pour {case.name} [{case.id}] ===")
        self._log(f"Dossier de travail : {case_dir}")
        self._log(f"Commande : {' '.join(cmd)}")
        case.status = CaseStatus.EN_COURS

        start_time = time.time()
        try:
            with open(log_file_path, "w", encoding="utf-8", errors="replace") as log_f:
                self.current_process = subprocess.Popen(
                    cmd,
                    cwd=str(case_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
                )

                # Lecture en temps réel de stdout
                for line in iter(self.current_process.stdout.readline, ""):
                    log_f.write(line)
                    log_f.flush()
                    clean_line = line.strip()
                    if clean_line:
                        self._log(clean_line)
                        match = self.ITER_REGEX.match(clean_line)
                        if match:
                            try:
                                it_num = int(match.group(1))
                                case.current_iteration = it_num
                                case.progress_percent = min(100, int((it_num / case.total_iterations) * 100))
                                self._update_progress(it_num, case.total_iterations)
                            except ValueError:
                                pass

                self.current_process.wait()
                ret_code = self.current_process.returncode

        except Exception as exc:
            case.status = CaseStatus.ECHEC
            case.error_message = f"Erreur de lancement : {exc}"
            self._log(f"[ERREUR] {case.error_message}")
            return False
        finally:
            case.end_time = time.time()
            case.duration_seconds = case.end_time - start_time
            self.current_process = None

        if self._is_cancelled:
            case.status = CaseStatus.ANNULEE
            case.error_message = "Simulation annulée par l'utilisateur."
            self._log(f"[ANNULÉ] {case.name} a été annulé.")
            return False

        if ret_code != 0:
            case.status = CaseStatus.ECHEC
            case.error_message = f"Fluent s'est terminé avec le code d'erreur {ret_code}."
            self._log(f"[ERREUR] {case.error_message}")
            return False

        # Vérification des fichiers indispensables
        cl_file = case_dir / "cl_test.txt"
        cd_file = case_dir / "cd_test.txt"
        csv_file = case_dir / "airfoil_pressure.csv"

        missing = []
        if not cl_file.exists():
            missing.append("cl_test.txt")
        if not cd_file.exists():
            missing.append("cd_test.txt")
        if not csv_file.exists():
            missing.append("airfoil_pressure.csv")

        if missing:
            case.status = CaseStatus.ECHEC
            case.error_message = f"Fichiers attendus manquants après le calcul : {', '.join(missing)}"
            self._log(f"[ERREUR] {case.error_message}")
            return False

        case.progress_percent = 100
        case.status = CaseStatus.POST_TRAITEMENT
        self._log(f"[SUCCÈS] Calcul Fluent terminé avec succès pour {case.id}.")
        return True
