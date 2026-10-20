import os
import subprocess
import sys
from typing import Optional


def terminate_process_tree(pid: int, timeout_sec: float = 3.0) -> bool:
    """Arrête proprement l'arborescence de processus liée à un PID spécifique.
    
    IMPORTANT : Ne cible EXCLUSIVEMENT que les sous-processus de l'arbre enfant du PID donné,
    afin de ne jamais interrompre d'autres calculs ANSYS Fluent ou d'autres applications de l'utilisateur.
    """
    if not pid:
        return True

    if sys.platform == "win32":
        try:
            # 1. Tentative d'arrêt gracieux avec taskkill /T (sans /F d'abord)
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T"],
                capture_output=True,
                check=False,
                timeout=timeout_sec,
            )
            # 2. Si le processus persiste, forcer la fermeture de cet arbre spécifique
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid), "/T"],
                capture_output=True,
                check=False,
                timeout=timeout_sec,
            )
            return True
        except Exception as exc:
            print(f"[ProcessManager] Avertissement lors de l'arrêt du processus {pid} : {exc}")
            return False
    else:
        try:
            import signal
            os.kill(pid, signal.SIGTERM)
            return True
        except Exception:
            return False
