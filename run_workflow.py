
from pathlib import Path
import os
import subprocess
import sys

# Dossier contenant ce script, le .jou et le .bdf
HERE = Path(__file__).resolve().parent

# Chemin standard de Fluent 2026 R1
FLUENT_EXE = Path(
    r"C:\Program Files\ANSYS Inc\v261\fluent\ntbin\win64\fluent.exe"
)

# Fichiers de résultats à nettoyer avant chaque simulation
PATTERNS_TO_DELETE = [
    "cl_test*.txt",
    "cd_test*.txt",
    "airfoil_pressure*.csv",
    "result.cas.h5",
    "result.dat.h5",
    "before_run.cas.h5",
]


def main():
    journal = HERE / "solve_test.jou"
    mesh = HERE / "profil_test.bdf"
    postprocess = HERE / "postprocess_fluent.py"

    # Vérification des fichiers nécessaires
    for fichier in (journal, mesh, postprocess):
        if not fichier.exists():
            raise SystemExit(
                f"Fichier introuvable : {fichier}"
            )

    # Possibilité de définir un autre chemin via FLUENT_EXE
    fluent_path = Path(
        os.environ.get("FLUENT_EXE", str(FLUENT_EXE))
    )

    if not fluent_path.is_file():
        raise SystemExit(
            "\nFluent est introuvable à cet emplacement :\n"
            f"{fluent_path}\n\n"
            "Vérifie le chemin de fluent.exe dans ce script."
        )

    # Nettoyage des anciens résultats
    for pattern in PATTERNS_TO_DELETE:
        for fichier in HERE.glob(pattern):
            try:
                fichier.unlink()
                print(f"Ancien résultat supprimé : {fichier.name}")
            except OSError as exc:
                raise SystemExit(
                    f"Impossible de supprimer {fichier.name}.\n"
                    "Ferme Fluent et les fichiers ouverts.\n"
                    f"Détail : {exc}"
                )

    # Lancement de Fluent
    cmd = [
        str(fluent_path),
        "2d",
        "-t4",
        "-g",
        "-i",
        str(journal),
    ]

    print("\nLancement de Fluent 2026 R1...")
    print(f"Dossier de travail : {HERE}")
    print(f"Journal : {journal.name}")

    try:
        result = subprocess.run(cmd, cwd=HERE)
    except OSError as exc:
        raise SystemExit(f"Impossible de lancer Fluent : {exc}")

    if result.returncode != 0:
        raise SystemExit(
            f"Fluent s'est terminé avec le code "
            f"{result.returncode}. Post-traitement annulé."
        )

    # Vérification de l'export CSV
    csv_path = HERE / "airfoil_pressure.csv"

    if not csv_path.exists():
        raise SystemExit(
            "Le fichier airfoil_pressure.csv est absent.\n"
            "Vérifie le bloc d'export dans solve_test.jou."
        )

    # Post-traitement Python
    print("\nCalcul des coefficients et génération des graphiques...")

    subprocess.run(
        [sys.executable, str(postprocess)],
        cwd=HERE,
        check=True,
    )

    print("\nWorkflow terminé.")
    print(f"Résultats disponibles dans : {HERE / 'post'}")


if __name__ == "__main__":
    main()
