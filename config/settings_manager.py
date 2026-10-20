import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class SettingsManager:
    """Gestionnaire de configuration persistante pour Fluent Simulation Manager."""

    DEFAULT_SETTINGS_PATH = Path(__file__).resolve().parent / "default_config.json"
    USER_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "fsm_config.json"

    def __init__(self, config_file: Optional[Path] = None):
        self.config_path = config_file or self.USER_SETTINGS_PATH
        self.settings: Dict[str, Any] = self._load_defaults()
        self.load()

    def _load_defaults(self) -> Dict[str, Any]:
        if self.DEFAULT_SETTINGS_PATH.exists():
            try:
                with open(self.DEFAULT_SETTINGS_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "fluent_exe": r"C:\Program Files\ANSYS Inc\v261\fluent\ntbin\win64\fluent.exe",
            "default_cores": 4,
            "default_iterations": 200,
            "default_mesh": "profil_test.bdf",
            "runs_dir": "runs",
            "simulation_mode": "real",
            "theme": "dark_tech",
            "recent_projects": [],
        }

    def load(self) -> None:
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.settings.update(data)
            except Exception:
                pass

    def save(self) -> None:
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            print(f"[SettingsManager] Erreur lors de la sauvegarde : {exc}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.settings[key] = value
        self.save()

    @property
    def fluent_exe(self) -> str:
        return self.settings.get("fluent_exe", "")

    @fluent_exe.setter
    def fluent_exe(self, path: str) -> None:
        self.set("fluent_exe", path)

    @property
    def simulation_mode(self) -> str:
        return self.settings.get("simulation_mode", "real")

    @simulation_mode.setter
    def simulation_mode(self, mode: str) -> None:
        self.set("simulation_mode", mode)

    @property
    def default_cores(self) -> int:
        return int(self.settings.get("default_cores", 4))

    @property
    def default_mesh(self) -> str:
        return self.settings.get("default_mesh", "profil_test.bdf")

    def is_fluent_valid(self) -> bool:
        exe = Path(self.fluent_exe)
        return exe.is_file() and exe.name.lower().startswith("fluent")

    @staticmethod
    def detect_fluent_installations() -> List[str]:
        """Recherche automatique des installations Fluent connues sous Windows."""
        candidates: List[Path] = []

        # 1. Variables d'environnement standard ANSYS (ex: AWP_ROOT261, AWP_ROOT252, etc.)
        for env_var, value in os.environ.items():
            if env_var.startswith("AWP_ROOT") and value:
                candidate = Path(value) / "fluent" / "ntbin" / "win64" / "fluent.exe"
                if candidate.is_file():
                    candidates.append(candidate)

        # 2. Dossiers classiques Program Files
        base_paths = [
            Path(r"C:\Program Files\ANSYS Inc"),
            Path(r"D:\Program Files\ANSYS Inc"),
            Path(r"C:\Program Files (x86)\ANSYS Inc"),
        ]

        # Versions connues : de v261 à v201
        known_versions = ["v261", "v260", "v252", "v251", "v242", "v241", "v232", "v231", "v222", "v221"]

        for base in base_paths:
            if base.exists():
                for ver in known_versions:
                    candidate = base / ver / "fluent" / "ntbin" / "win64" / "fluent.exe"
                    if candidate.is_file():
                        candidates.append(candidate)

        return [str(c) for c in candidates if c.exists()]
