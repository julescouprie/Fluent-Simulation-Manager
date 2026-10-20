# Fluent Simulation Manager - ANSYS Fluent 2026 R1

**Fluent Simulation Manager** est une application de bureau Windows conçue pour les élèves ingénieurs et chercheurs en aérodynamique. Elle permet de préparer, lancer en série, surveiller en direct et post-traiter automatiquement plusieurs simulations CFD **ANSYS Fluent 2026 R1** sans avoir à manipuler la console ou le terminal manuellement.

Le cas d'application de référence est l'étude aérodynamique 2D du profil d'aile **NACA 2212** (calcul des coefficients de portance $C_L$, de traînée $C_D$, de finesse $C_L/C_D$, de l'historique de convergence et de la distribution du coefficient de pression $C_p$).

---

## 🚀 Fonctionnalités principales

1. **Tableau de bord et indicateurs clés :**
   - Suivi des compteurs : Total, En attente, En cours, Terminées, Échecs, Temps de calcul écoulé.
2. **Gestion de file d'attente (Batch Manager) :**
   - Création, modification, duplication et suppression de cas de simulation.
   - Import de listes de simulations par fichier **CSV** ou **JSON**.
   - Sauvegarde et réouverture de projets de calcul (`.fsm`).
   - Exécution séquentielle maîtrisée (une simulation à la fois par défaut pour respecter les licences ANSYS).
   - Dossier de travail et journal Fluent dédiés et isolés pour chaque calcul (aucun risque d'écrasement).
3. **Paramétrage physique rigoureux :**
   - Angle d'incidence $\alpha$ avec projection trigonométrique automatique des vitesses ($V_x, V_y$) et des vecteurs de force aérodynamique (Portance $\vec{l} = (-\sin\alpha, \cos\alpha)$, Traînée $\vec{d} = (\cos\alpha, \sin\alpha)$).
   - Vitesse d'écoulement $U$, longueur de corde $c$, masse volumique $\rho$, pression de référence $p_{\text{ref}}$.
   - Nombre d'itérations et cœurs CPU alloués.
   - Modèle de turbulence $k$-$\omega$ SST (validé sous Fluent 2026 R1).
4. **Contrôle d'exécution sécurisé :**
   - Vérification préalable des chemins, de la validité de `fluent.exe` et des fichiers de maillage (`.bdf`).
   - Dialogue de confirmation affichant le récapitulatif avant lancement.
   - Bouton de **Pause** propre (laisse se terminer le calcul en cours sans interrompre brutalement le solveur).
   - Bouton d'**Arrêt propre** (arrête uniquement l'arbre de processus Fluent de l'application sans toucher aux autres tâches du système).
   - Mode double : **Calcul Réel ANSYS Fluent** ou **Mode Test / Simulation Fictive** (pour travailler ou vérifier l'enchaînement même sans licence ANSYS active).
5. **Surveillance en temps réel :**
   - Détection en direct des itérations effectuées et progression en pourcentage.
   - Console intégrée avec flux texte stdout de Fluent, filtre par mot-clé et défilement automatique.
6. **Post-traitement et Comparaisons intégrées :**
   - Extraction automatique des coefficients $C_L$ et $C_D$ finaux.
   - Tracé interactif Matplotlib :
     - Polaire de portance $C_L = f(\alpha)$
     - Traînée $C_D = f(\alpha)$
     - Finesse aérodynamique $C_L / C_D = f(\alpha)$
     - Superposition des courbes de convergence
     - Distribution de pression $C_p = f(x/c)$ sur l'extrados et l'intrados
   - Export des résultats comparatifs en **CSV** et en classeur **Excel (.xlsx)**.

---

## 📁 Organisation du projet

```
App CFD/
├── main.py                     # Point d'entrée de l'application graphique PySide6
├── start_app.bat               # Lanceur en un clic pour Windows
├── requirements.txt            # Dépendances Python
├── README.md                   # Ce guide d'utilisation
├── fsm_config.json             # Configuration utilisateur persistante
├── profil_test.bdf             # Fichier de maillage Nastran généré
├── mgsh_naca2212.py            # Générateur Gmsh du profil NACA 2212
├── solve_test.jou              # Journal de référence Fluent
├── run_workflow.py             # Script de référence Fluent
├── postprocess_fluent.py       # Script de post-traitement de référence
├── config/
│   ├── default_config.json     # Configuration d'usine
│   └── settings_manager.py     # Détection Fluent et gestion des préférences
├── core/
│   ├── case_model.py           # Modèle de données SimulationCase et PhysicalParameters
│   ├── project_manager.py      # Gestion des projets (.fsm) et import/export CSV
│   └── queue_worker.py         # File d'attente asynchrone non bloquante (QThread)
├── simulation/
│   ├── journal_generator.py    # Génération paramétrique de solve.jou (syntaxe 2026 R1)
│   ├── fluent_runner.py        # Pilote d'exécution d'ANSYS Fluent
│   ├── mock_runner.py          # Simulateur réaliste pour tests et démonstrations
│   └── process_manager.py      # Arrêt propre des processus enfants Windows
├── postprocessing/
│   ├── postprocessor.py        # Extraction CL, CD, convergence, Cp et graphiques
│   └── exporter.py             # Export vers CSV et Excel
├── ui/
│   ├── theme.py                # Feuille de style moderne sobre et technique
│   ├── main_window.py          # Fenêtre principale et menus
│   ├── dashboard_widget.py     # Cartes d'indicateurs métriques
│   ├── simulation_table.py     # Tableau des simulations avec jauges et badges
│   ├── case_dialog.py          # Boîte de dialogue création/édition de cas
│   ├── settings_dialog.py      # Configuration de l'environnement Fluent
│   ├── confirmation_dialog.py  # Validation préalable et confirmation
│   ├── log_viewer_widget.py    # Console de logs Fluent en direct
│   └── comparison_widget.py    # Visualisation interactive Matplotlib
└── tests/
    ├── run_all_tests.py        # Lanceur global des tests
    ├── test_case_model.py
    ├── test_journal_generator.py
    ├── test_project_manager.py
    ├── test_fluent_path_validation.py
    ├── test_mock_runner.py
    ├── test_postprocessor.py
    ├── test_queue_worker.py
    └── test_gui_headless.py
```

---

## 🛠️ Installation et Prérequis

### Prérequis
- **Système :** Windows 10 / 11 (64 bits).
- **Python :** Version 3.10 ou supérieure.
- **CFD :** ANSYS Fluent 2026 R1 (optionnel si utilisation en mode simulation fictive).

### Installation des bibliothèques Python
Ouvrez PowerShell ou une invite de commandes dans le dossier du projet :

```powershell
pip install -r requirements.txt
```

Les dépendances installées comprennent :
- `PySide6` : Interface graphique native Qt.
- `matplotlib` : Tracés scientifiques haute fidélité.
- `pandas` & `numpy` : Analyse numérique et traitement des tableaux.
- `openpyxl` : Exportation sous format Excel.
- `gmsh` : Générateur de maillage pour profil aérodynamique.

---

## 🚦 Démarrage rapide

### Option A : Double-clic sur Windows
Double-cliquez simplement sur le fichier :
```
start_app.bat
```

### Option B : Ligne de commande
```powershell
python main.py
```

---

## 📖 Mode d'emploi

### 1. Configuration initiale d'ANSYS Fluent
1. Allez dans le menu **Outils > Préférences & Configuration Fluent...**.
2. Cliquez sur **🔍 Auto-détection** ou cliquez sur **Parcourir...** pour sélectionner l'exécutable `fluent.exe` (par exemple : `C:\Program Files\ANSYS Inc\v261\fluent\ntbin\win64\fluent.exe`).
3. Choisissez le mode d'exécution :
   - **Exécution réelle ANSYS Fluent** : Lance les véritables calculs ANSYS.
   - **Mode Test / Simulation Fictive** : Permet de tester l'ensemble du flux sans licence active.
4. Cliquez sur **OK**.

### 2. Définition des simulations
- **Ajout unitaire :** Cliquez sur **➕ Nouveau cas**, renseignez l'angle d'incidence $\alpha$, la vitesse, la corde, le nombre d'itérations et le fichier de maillage (`profil_test.bdf`).
- **Duplication :** Sélectionnez un cas et cliquez sur **📑 Dupliquer** pour créer rapidement une variante (ex: changer l'angle $\alpha$).
- **Import par lot :** Cliquez sur **📥 Importer CSV** et sélectionnez un fichier CSV (un modèle `exemples_simulations.csv` est fourni).
- **Sauvegarde :** Enregistrez votre projet avec **Ctrl+S** au format `.fsm`.

### 3. Lancement et suivi des calculs
1. Cliquez sur le grand bouton bleu **🚀 LANCER LES SIMULATIONS**.
2. Une boîte de dialogue de validation vérifie que le maillage et Fluent sont accessibles, et résume la file d'attente.
3. Confirmez pour démarrer.
4. Suivez l'avancement en temps réel :
   - Colonne **Progression** du tableau.
   - Onglet **Journal d'exécution Fluent** affichant les résidus et messages console.
5. Vous pouvez suspendre la file avec **⏸️ Pause** ou l'interrompre proprement avec **⏹️ Arrêter**.

### 4. Analyse et Comparaison des résultats
1. Basculez sur l'onglet **📊 Analyse & Comparaison des Résultats**.
2. Cochez les simulations terminées à inclure dans le comparatif.
3. Sélectionnez le graphique désiré :
   - **Polaire : CL vs Alpha**
   - **Traînée : CD vs Alpha**
   - **Finesse : CL / CD vs Alpha**
   - **Convergence : CL & CD vs Itérations**
   - **Distribution de pression : Cp vs x/c** (extrados / intrados)
4. Exportez les résultats au format **CSV**, **Excel** ou enregistrez l'image en **PNG**.

---

## 🧪 Validation et Tests Automatisés

Le projet comprend une suite complète de tests unitaires et d'intégration validant chaque couche logicielle :

```powershell
python tests/run_all_tests.py
```

**Couverture des tests :**
1. Modélisation physique et calculs d'angles / vecteurs aérodynamiques.
2. Génération fidèle du journal Fluent (`solve.jou`).
3. Gestion des projets (ajout, suppression, duplication, sauvegarde/chargement `.fsm`, import CSV).
4. Détection et signalement d'un chemin Fluent invalide.
5. Exécution du simulateur de test (Mock Runner) et gestion des erreurs de divergence.
6. Post-traitement complet ($C_L, C_D$, convergence, distribution $C_p$).
7. Exécution end-to-end de la file d'attente multi-cas et des signaux asynchrones.
8. Initialisation et rendu de l'interface graphique en mode offscreen.

---

## ⚙️ Détails techniques ANSYS Fluent 2026 R1

### Automatisation de l'incidence aérodynamique
Dans Fluent 2D, l'angle d'incidence $\alpha$ est pris en compte à la fois dans les conditions limites d'entrée et dans la définition des coefficients :
- **Composantes de vitesse en entrée :**
  $$V_x = V_\infty \cos(\alpha), \quad V_y = V_\infty \sin(\alpha)$$
- **Vecteur de force pour la portance ($C_L$) :**
  $$\vec{l} = (-\sin\alpha, \cos\alpha)$$
- **Vecteur de force pour la traînée ($C_D$) :**
  $$\vec{d} = (\cos\alpha, \sin\alpha)$$
- **Valeurs de référence Fluent :**
  Surface $S = c \times 1.0\text{ m}$, longueur $c$, vitesse $V_\infty$, masse volumique $\rho$.

### Isolation stricte des exécutions
Pour garantir l'intégrité absolue des résultats :
- Chaque simulation s'exécute dans un dossier distinct horodaté : `runs/<ID>_<Nom>_<Horodatage>/`.
- Le maillage est copié dans le dossier et le journal Fluent généré n'utilise que des chemins relatifs simples, évitant tout problème d'espaces ou d'accents sous Windows.
- Les résultats antérieurs ne sont jamais écrasés.
