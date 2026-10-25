from pathlib import Path
import threading
import time
from typing import List, Optional
from PySide6.QtCore import QObject, Signal

from core.case_model import SimulationCase, CaseStatus
from simulation.fluent_runner import FluentRunner
from simulation.mock_runner import MockFluentRunner
from postprocessing.postprocessor import process_case_results


class QueueWorker(QObject):
    """Travailleur d'arrière-plan exécutant la file de simulations sans bloquer le GUI."""

    case_started = Signal(str)                          # case_id
    case_progress = Signal(str, int, int)              # case_id, current, total
    case_log = Signal(str, str)                        # case_id, log_line
    case_finished = Signal(str, bool, str)             # case_id, success, error_message
    queue_state_changed = Signal(bool, bool)           # is_running, is_paused
    queue_finished = Signal()

    def __init__(
        self,
        cases_getter,
        fluent_exe_getter,
        mode_getter,
        base_runs_dir: Path = Path("runs"),
        mock_speed_factor: float = 1.0,
    ):
        super().__init__()
        self.cases_getter = cases_getter
        self.fluent_exe_getter = fluent_exe_getter
        self.mode_getter = mode_getter
        self.base_runs_dir = base_runs_dir
        self.mock_speed_factor = mock_speed_factor

        self._is_running = False
        self._is_paused = False
        self._stop_requested = False
        self._current_runner = None
        self._thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def start_queue(self) -> None:
        if self._is_running:
            if self._is_paused:
                self._is_paused = False
                self.queue_state_changed.emit(True, False)
            return

        self._is_running = True
        self._is_paused = False
        self._stop_requested = False
        self.queue_state_changed.emit(True, False)

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def pause_queue(self) -> None:
        """Met en pause la file. Le calcul en cours se termine proprement."""
        if self._is_running:
            self._is_paused = True
            self.queue_state_changed.emit(True, True)

    def resume_queue(self) -> None:
        if self._is_running and self._is_paused:
            self._is_paused = False
            self.queue_state_changed.emit(True, False)

    def cancel_current_simulation(self) -> None:
        """Annule immédiatement la simulation en cours d'exécution."""
        if self._current_runner:
            self._current_runner.cancel()

    def stop_all(self) -> None:
        """Arrête la file et annule le cas en cours."""
        self._stop_requested = True
        self._is_paused = False
        self.cancel_current_simulation()

    def _run_loop(self) -> None:
        try:
            cases: List[SimulationCase] = self.cases_getter()

            for case in cases:
                if self._stop_requested:
                    break

                # Attente en cas de pause
                while self._is_paused and not self._stop_requested:
                    time.sleep(0.3)

                if self._stop_requested:
                    break

                # On ne traite que les cas en attente
                if case.status != CaseStatus.EN_ATTENTE:
                    continue

                self._process_single_case(case)

        finally:
            self._is_running = False
            self._is_paused = False
            self._stop_requested = False
            self._current_runner = None
            self.queue_state_changed.emit(False, False)
            self.queue_finished.emit()

    def _process_single_case(self, case: SimulationCase) -> None:
        self.case_started.emit(case.id)

        mode = self.mode_getter()  # "real" ou "mock"
        fluent_exe = Path(self.fluent_exe_getter())
        mesh_path = Path(case.parameters.mesh_file)
        if not mesh_path.is_absolute():
            if (Path.cwd() / mesh_path).is_file():
                mesh_path = Path.cwd() / mesh_path
            elif (Path.cwd() / "data" / mesh_path).is_file():
                mesh_path = Path.cwd() / "data" / mesh_path
            else:
                mesh_path = Path.cwd() / mesh_path

        def log_cb(line: str):
            self.case_log.emit(case.id, line)

        def prog_cb(cur: int, tot: int):
            self.case_progress.emit(case.id, cur, tot)

        if mode == "mock":
            runner = MockFluentRunner(
                base_runs_dir=self.base_runs_dir,
                on_log=log_cb,
                on_progress=prog_cb,
                speed_factor=self.mock_speed_factor,
            )
        else:
            runner = FluentRunner(
                fluent_exe=fluent_exe,
                base_runs_dir=self.base_runs_dir,
                on_log=log_cb,
                on_progress=prog_cb,
            )

        self._current_runner = runner
        run_ok = runner.run(case, mesh_path)
        self._current_runner = None

        if not run_ok:
            self.case_finished.emit(case.id, False, case.error_message)
            return

        # Étape de Post-traitement automatique
        case.status = CaseStatus.POST_TRAITEMENT
        log_cb("[POST-TRAITEMENT] Lecture des rapports et génération des graphiques...")

        try:
            results = process_case_results(Path(case.work_dir), case.parameters)
            case.results = results
            if results.postprocess_success:
                if results.is_converged:
                    case.status = CaseStatus.TERMINEE_CONVERGEE
                    log_cb(f"[QUALITÉ VALIDÉE] Convergence satisfaite ! CL = {results.cl_final:.5f}, CD = {results.cd_final:.5f}, Finesse = {results.cl_cd_ratio:.2f}")
                else:
                    case.status = CaseStatus.TERMINEE_NON_CONVERGEE
                    log_cb(f"[AVERTISSEMENT CONVERGENCE] Calcul terminé sans stabilisation asymptotique stricte : {results.quality_message}")
                self.case_finished.emit(case.id, True, "")
            else:
                case.status = CaseStatus.INCOMPLETE
                case.error_message = "Post-traitement incomplet : données de portance/traînée invalides."
                log_cb(f"[ERREUR] {case.error_message}")
                self.case_finished.emit(case.id, False, case.error_message)
        except Exception as exc:
            case.status = CaseStatus.ECHEC
            case.error_message = f"Échec du post-traitement : {exc}"
            log_cb(f"[ERREUR] {case.error_message}")
            self.case_finished.emit(case.id, False, case.error_message)
