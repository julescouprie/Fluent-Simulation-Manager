"""
Application Streamlit de Prédiction Aérodynamique par Krigeage (V2).

Plateforme interactive d'ingénierie permettant :
- Le chargement et l'inspection des données CFD d'apprentissage.
- La sélection dynamique des variables d'entrée (m_%, p, etc.) et des grandeurs cibles (Cl, Cd).
- L'entraînement contrôlé du modèle de krigeage avec ou sans optimisation des theta.
- La prédiction interactive ponctuelle avec alertes de sortie de domaine.
- La visualisation scientifique avancée :
    * Courbes d'influence 1D interactives
    * Cartes de prédiction 2D (contours / surfaces de réponse)
    * Graphique de parité (Données CFD vs Prédictions du modèle sur l'apprentissage)
    * Tableaux de bord des hyperparamètres theta
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# Import du moteur de krigeage (V1 modulaire)
try:
    from kriging_model import (
        KrigingModel,
        charger_donnees_csv,
        entrainer_modele,
    )
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from kriging_model import (
        KrigingModel,
        charger_donnees_csv,
        entrainer_modele,
    )


# ==============================================================================
# CONFIGURATION DE LA PAGE STREAMLIT
# ==============================================================================

st.set_page_config(
    page_title="AéroKriging V2 | Prédiction CFD",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Style CSS épuré, blanc et moderne (thème technique professionnel)
st.markdown(
    """
    <style>
    /* Typographie et marges globales */
    .main .block-container {
        padding-top: 1.8rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }
    h1, h2, h3, h4 {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #0f172a;
        font-weight: 600;
    }
    /* Badges de métriques techniques */
    .metric-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 12px;
    }
    .metric-title {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748b;
        font-weight: 600;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #0f172a;
    }
    .metric-sub {
        font-size: 0.78rem;
        color: #94a3b8;
    }
    /* Alertes et encarts discrets */
    .scientific-notice {
        background-color: #f0fdf4;
        border-left: 3px solid #22c55e;
        padding: 10px 14px;
        border-radius: 4px;
        font-size: 0.85rem;
        color: #166534;
        margin-bottom: 15px;
    }
    .warning-notice {
        background-color: #fffbeb;
        border-left: 3px solid #f59e0b;
        padding: 10px 14px;
        border-radius: 4px;
        font-size: 0.85rem;
        color: #92400e;
        margin-bottom: 15px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ==============================================================================
# FONCTIONS DE MISE EN CACHE ET D'ENTRAINEMENT
# ==============================================================================

@st.cache_data(show_spinner=False)
def load_csv_data(filepath_or_buffer) -> Tuple[pd.DataFrame, List[str], List[str], Dict]:
    """Charge et analyse le fichier CSV."""
    return charger_donnees_csv(filepath_or_buffer)


@st.cache_resource(show_spinner=False)
def train_cached_model(
    _df: pd.DataFrame,
    feature_names: Tuple[str, ...],
    target_name: str,
    optimize_theta: bool,
    custom_theta: Optional[Tuple[float, ...]],
) -> KrigingModel:
    """Entraîne et met en cache un modèle de krigeage pour éviter les recalculs inutiles."""
    X = _df[list(feature_names)].to_numpy(dtype=float)
    Y = _df[target_name].to_numpy(dtype=float)

    c_theta = list(custom_theta) if custom_theta is not None else None

    return entrainer_modele(
        X=X,
        Y=Y,
        feature_names=list(feature_names),
        target_name=target_name,
        optimize_theta=optimize_theta,
        custom_theta=c_theta,
    )


# ==============================================================================
# EN-TETE PRINCIPALE
# ==============================================================================

col_head1, col_head2 = st.columns([3, 1])
with col_head1:
    st.title("AéroKriging V2")
    st.caption("Modélisation de substitution par processus gaussien (Krigeage Ordinaire) — Aérodynamique CFD")

with col_head2:
    st.markdown(
        """
        <div style="text-align: right; padding-top: 15px;">
            <span style="background-color: #e0f2fe; color: #0369a1; padding: 4px 10px; border-radius: 12px; font-size: 0.82rem; font-weight: 600;">
                Moteur V1 + UI V2
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")


# ==============================================================================
# BARRE LATERALE : CONFIGURATION DU MODELE ET DONNEES
# ==============================================================================

st.sidebar.markdown("### 📁 1. Données d'apprentissage")

# Chemin par défaut vers recapitulatif_campagne.csv
default_csv = Path(__file__).resolve().parent / "recapitulatif_campagne.csv"
if not default_csv.exists():
    # Fallback si exécuté depuis la racine
    default_csv = Path("Krigeage Code") / "recapitulatif_campagne.csv"

source_choice = st.sidebar.radio(
    "Fichier source",
    ["Fichier de référence (recapitulatif_campagne.csv)", "Importer un autre fichier CSV"],
    index=0,
    label_visibility="collapsed",
)

uploaded_file = None
csv_to_load = None

if source_choice == "Importer un autre fichier CSV":
    uploaded_file = st.sidebar.file_uploader("Fichier CSV", type=["csv"])
    if uploaded_file is not None:
        csv_to_load = uploaded_file
else:
    if default_csv.exists():
        csv_to_load = default_csv
    else:
        st.sidebar.error("Fichier recapitulatif_campagne.csv introuvable.")

if csv_to_load is None:
    st.warning("Veuillez sélectionner ou charger un fichier CSV pour continuer.")
    st.stop()

try:
    df, input_candidates, output_candidates, info = load_csv_data(csv_to_load)
except Exception as exc:
    st.error(f"Erreur lors du chargement des données : {exc}")
    st.stop()

st.sidebar.caption(f"✓ {info['nb_lignes']} simulations chargées ({len(info['colonnes'])} colonnes)")


# ------------------------------------------------------------------------------
# SELECTION DES VARIABLES D'ENTREE
# ------------------------------------------------------------------------------
st.sidebar.markdown("### ⚙️ 2. Variables d'entrée (X)")

if not input_candidates:
    st.sidebar.error("Aucune variable d'entrée numérique détectée.")
    st.stop()

# Par défaut, sélectionner m_% et p s'ils existent
default_inputs = [c for c in ["m_%", "p"] if c in input_candidates]
if not default_inputs:
    default_inputs = input_candidates[:2]

selected_inputs = []
for col_name in input_candidates:
    checked = col_name in default_inputs
    if st.sidebar.checkbox(col_name, value=checked, key=f"chk_in_{col_name}"):
        selected_inputs.append(col_name)

if not selected_inputs:
    st.sidebar.warning("Sélectionnez au moins une variable d'entrée.")
    st.stop()


# ------------------------------------------------------------------------------
# SELECTION DES GRANDEURS CIBLES A CALCULER
# ------------------------------------------------------------------------------
st.sidebar.markdown("### 🎯 3. Grandeurs à calculer (Y)")

# Détection de Cl et Cd
available_targets = [t for t in ["Cl", "Cd"] if t in output_candidates]
if not available_targets:
    available_targets = output_candidates

selected_targets = []
for target_name in available_targets:
    # Par défaut on coche Cl et Cd
    if st.sidebar.checkbox(f"Coefficient {target_name}", value=True, key=f"chk_out_{target_name}"):
        selected_targets.append(target_name)

if not selected_targets:
    st.sidebar.warning("Sélectionnez au moins une grandeur à prédire (Cl ou Cd).")
    st.stop()


# ------------------------------------------------------------------------------
# PARAMETRES DU MODELE ET OPTIMISATION DES THETA
# ------------------------------------------------------------------------------
st.sidebar.markdown("### 🎛️ 4. Paramètres du modèle")

optimize_theta = st.sidebar.toggle(
    "Optimiser les theta (Maximum de vraisemblance)",
    value=True,
    help="Utilise l'algorithme L-BFGS-B pour maximiser la vraisemblance concentrée sur les données d'apprentissage.",
)

custom_theta_values: Dict[str, List[float]] = {}

if not optimize_theta:
    st.sidebar.caption("Saisie manuelle des theta :")
    for t_name in selected_targets:
        st.sidebar.markdown(f"**Theta pour {t_name} :**")
        t_vals = []
        for feat in selected_inputs:
            val = st.sidebar.number_input(
                f"θ_{feat} ({t_name})",
                min_value=1e-3,
                max_value=100.0,
                value=1.0,
                step=0.1,
                format="%.4f",
                key=f"manual_theta_{t_name}_{feat}",
            )
            t_vals.append(val)
        custom_theta_values[t_name] = t_vals


# ==============================================================================
# ENTRAINEMENT DES MODELES SELECTIONNES (AVEC CACHE)
# ==============================================================================

trained_models: Dict[str, KrigingModel] = {}
training_errors: Dict[str, str] = {}

feature_tuple = tuple(selected_inputs)

for t_name in selected_targets:
    custom_t = tuple(custom_theta_values[t_name]) if not optimize_theta else None
    try:
        model = train_cached_model(
            _df=df,
            feature_names=feature_tuple,
            target_name=t_name,
            optimize_theta=optimize_theta,
            custom_theta=custom_t,
        )
        trained_models[t_name] = model
    except Exception as exc:
        training_errors[t_name] = str(exc)

if training_errors:
    for t_name, err in training_errors.items():
        st.error(f"Échec de l'entraînement du modèle pour {t_name} : {err}")
    st.stop()


# Avertissement éventuel si un modèle a nécessité un nugget minimal
for t_name, model in trained_models.items():
    if model.warning:
        st.markdown(
            f"""
            <div class="warning-notice">
                ℹ️ <b>Régularisation numérique ({t_name}) :</b> {model.warning}
            </div>
            """,
            unsafe_allow_html=True,
        )


# ==============================================================================
# ONGLETS DE L'INTERFACE PRINCIPALE
# ==============================================================================

tab_pred, tab_curve, tab_map, tab_diag, tab_data = st.tabs([
    "🎯 Prédiction interactive",
    "📈 Courbe d'influence 1D",
    "🗺️ Carte 2D",
    "🔬 Diagnostic & Theta",
    "📋 Données d'apprentissage",
])


# ==============================================================================
# ONGLET 1 : PREDICTION INTERACTIVE PONCTUELLE
# ==============================================================================

with tab_pred:
    st.subheader("Prédiction ponctuelle d'une configuration")
    st.caption("Modifiez les paramètres géométriques pour évaluer instantanément les coefficients aérodynamiques.")

    col_in, col_res = st.columns([1, 1], gap="large")

    # Définition des bornes d'apprentissage pour chaque entrée
    reference_model = next(iter(trained_models.values()))
    X_min = reference_model.X_min
    X_max = reference_model.X_max

    query_point: Dict[str, float] = {}

    with col_in:
        st.markdown("##### Paramètres géométriques d'entrée")
        for i, col_name in enumerate(selected_inputs):
            min_val = float(X_min[i])
            max_val = float(X_max[i])
            # Valeur par défaut au centre du domaine
            default_val = float(df[col_name].iloc[0])

            # Détermination du pas selon l'ordre de grandeur
            span = max_val - min_val
            step = 0.1 if span > 1.0 else 0.01

            val = st.number_input(
                f"{col_name} (Domaine CFD : [{min_val:.3f}, {max_val:.3f}])",
                value=default_val,
                step=step,
                format="%.4f",
                key=f"query_input_{col_name}",
            )
            query_point[col_name] = val

    with col_res:
        st.markdown("##### Résultats de prédiction (Krigeage)")

        # Calcul des prédictions
        all_inside = True
        warnings_list = []

        for t_name in selected_targets:
            m = trained_models[t_name]
            pred_res = m.predict(query_point)

            if not pred_res["is_inside_domain"]:
                all_inside = False
                for oob in pred_res["out_of_bounds"]:
                    warnings_list.append(f"{oob[0]} = {oob[1]:.3f} (hors du domaine [{oob[2]:.3f}, {oob[3]:.3f}])")

            y_val = pred_res["y_pred"]

            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-title">Coefficient {t_name} prédit</div>
                    <div class="metric-value">{y_val:.6f}</div>
                    <div class="metric-sub">Calculé par métamodèle de krigeage gaussien</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if not all_inside:
            warn_txt = "<br>• " + "<br>• ".join(set(warnings_list))
            st.markdown(
                f"""
                <div class="warning-notice">
                    ⚠️ <b>Attention — Extrapolation hors du domaine d'apprentissage :</b>{warn_txt}
                    <br><small>Les prédictions du krigeage perdent en fiabilité en dehors de l'enveloppe convexe des simulations CFD.</small>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="scientific-notice">
                    ✓ Point situé à l'intérieur du domaine d'apprentissage CFD.
                </div>
                """,
                unsafe_allow_html=True,
            )


# ==============================================================================
# ONGLET 2 : COURBE D'INFLUENCE 1D
# ==============================================================================

with tab_curve:
    st.subheader("Courbe d'influence aérodynamique (1D)")
    st.caption("Visualisez la sensibilité d'une grandeur prédite le long d'un axe géométrique tout en maintenant les autres paramètres fixes.")

    col_c1, col_c2, col_c3 = st.columns([1, 1, 1])

    with col_c1:
        x_axis_var = st.selectbox(
            "Variable en abscisse (X) :",
            selected_inputs,
            index=0,
            key="curve_x_var",
        )

    with col_c2:
        curve_target = st.selectbox(
            "Grandeur prédite (Y) :",
            selected_targets,
            index=0,
            key="curve_target_var",
        )

    # Paramètres fixés si plus d'une variable sélectionnée
    fixed_params_1d: Dict[str, float] = {}
    other_inputs = [col for col in selected_inputs if col != x_axis_var]

    with col_c3:
        if other_inputs:
            st.markdown("**Paramètres maintenus fixes :**")
            for col_other in other_inputs:
                idx_o = selected_inputs.index(col_other)
                min_o = float(X_min[idx_o])
                max_o = float(X_max[idx_o])
                val_o = st.number_input(
                    f"{col_other} (fixe dans [{min_o:.3f}, {max_o:.3f}])",
                    min_value=min_o,
                    max_value=max_o,
                    value=float(df[col_other].iloc[0]),
                    step=0.05 if (max_o - min_o) > 1.0 else 0.01,
                    key=f"fixed_1d_{col_other}",
                )
                fixed_params_1d[col_other] = val_o

    # Génération des points de la courbe
    idx_x = selected_inputs.index(x_axis_var)
    min_x = float(X_min[idx_x])
    max_x = float(X_max[idx_x])

    n_curve_pts = 150
    x_grid = np.linspace(min_x, max_x, n_curve_pts)

    batch_matrix = np.zeros((n_curve_pts, len(selected_inputs)))
    for j, col_name in enumerate(selected_inputs):
        if col_name == x_axis_var:
            batch_matrix[:, j] = x_grid
        else:
            batch_matrix[:, j] = fixed_params_1d[col_name]

    m_active = trained_models[curve_target]
    y_preds_curve, _ = m_active.predict_batch(batch_matrix)

    # Tracé Plotly
    fig_1d = go.Figure()

    # 1. Courbe du krigeage
    fig_1d.add_trace(
        go.Scatter(
            x=x_grid,
            y=y_preds_curve,
            mode="lines",
            name=f"{curve_target} (Modèle Krigeage)",
            line=dict(color="#2563eb", width=2.5),
            hovertemplate=f"{x_axis_var}: %{{x:.4f}}<br>{curve_target} prédit: %{{y:.6f}}<extra></extra>",
        )
    )

    # 2. Points d'apprentissage correspondant approximativement aux paramètres fixes
    # Si d > 1, on affiche les points dont les autres paramètres sont proches des valeurs fixes
    if other_inputs:
        tol = 0.15  # Tolérance relative pour afficher les points projetés
        match_mask = np.ones(len(df), dtype=bool)
        for col_other in other_inputs:
            rng = df[col_other].max() - df[col_other].min()
            tol_abs = (rng * tol) if rng > 0 else 0.01
            match_mask &= (np.abs(df[col_other] - fixed_params_1d[col_other]) <= tol_abs)

        df_match = df[match_mask]
        if not df_match.empty:
            fig_1d.add_trace(
                go.Scatter(
                    x=df_match[x_axis_var],
                    y=df_match[curve_target],
                    mode="markers",
                    name="Données CFD proches",
                    marker=dict(size=8, color="#0f172a", symbol="circle", line=dict(color="#ffffff", width=1.5)),
                    text=df_match["Cas"] if "Cas" in df_match else None,
                    hovertemplate=f"Cas: %{{text}}<br>{x_axis_var}: %{{x}}<br>{curve_target} réel: %{{y}}<extra></extra>",
                )
            )
    else:
        # En dimension 1, on affiche directement tous les points d'apprentissage
        fig_1d.add_trace(
            go.Scatter(
                x=df[x_axis_var],
                y=df[curve_target],
                mode="markers",
                name="Données CFD d'apprentissage",
                marker=dict(size=8, color="#0f172a", symbol="circle", line=dict(color="#ffffff", width=1.5)),
                text=df["Cas"] if "Cas" in df else None,
                hovertemplate=f"Cas: %{{text}}<br>{x_axis_var}: %{{x}}<br>{curve_target} réel: %{{y}}<extra></extra>",
            )
        )

    fixed_info_str = ", ".join([f"{k} = {v:.3f}" for k, v in fixed_params_1d.items()])
    title_suffix = f" (avec {fixed_info_str})" if fixed_info_str else ""

    fig_1d.update_layout(
        title=f"Évolution de {curve_target} en fonction de {x_axis_var}{title_suffix}",
        xaxis_title=x_axis_var,
        yaxis_title=f"Coefficient {curve_target}",
        template="plotly_white",
        hovermode="x unified",
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    st.plotly_chart(fig_1d, use_container_width=True)
    st.caption("ℹ️ *Les courbes lisses proviennent du métamodèle de krigeage interpolant. Les points noirs représentent les données d'apprentissage CFD réelles.*")


# ==============================================================================
# ONGLET 3 : CARTE DE PREDICTION 2D (SURFACE DE REPONSE)
# ==============================================================================

with tab_map:
    st.subheader("Carte de prédiction aérodynamique (2D)")
    st.caption("Surface de réponse interactive interpolée par krigeage sur deux axes géométriques.")

    if len(selected_inputs) < 2:
        st.info("Sélectionnez au moins deux variables d'entrée dans la barre latérale pour activer la cartographie 2D.")
    else:
        col_m1, col_m2, col_m3 = st.columns([1, 1, 1])

        with col_m1:
            map_x_var = st.selectbox(
                "Axe Horizontal (X) :",
                selected_inputs,
                index=0,
                key="map_x_var",
            )

        with col_m2:
            remaining_vars = [v for v in selected_inputs if v != map_x_var]
            map_y_var = st.selectbox(
                "Axe Vertical (Y) :",
                remaining_vars,
                index=0,
                key="map_y_var",
            )

        with col_m3:
            map_target = st.selectbox(
                "Grandeur affichée (Couleur) :",
                selected_targets,
                index=0,
                key="map_target_var",
            )

        # Fixer les éventuelles autres variables si d > 2
        extra_inputs = [v for v in selected_inputs if v not in (map_x_var, map_y_var)]
        fixed_params_2d: Dict[str, float] = {}

        if extra_inputs:
            st.markdown("**Autres paramètres maintenus fixes :**")
            cols_extra = st.columns(len(extra_inputs))
            for k, col_ex in enumerate(extra_inputs):
                with cols_extra[k]:
                    idx_ex = selected_inputs.index(col_ex)
                    min_ex = float(X_min[idx_ex])
                    max_ex = float(X_max[idx_ex])
                    val_ex = st.number_input(
                        f"{col_ex} (fixe)",
                        min_value=min_ex,
                        max_value=max_ex,
                        value=float(df[col_ex].iloc[0]),
                        key=f"fixed_2d_{col_ex}",
                    )
                    fixed_params_2d[col_ex] = val_ex

        # Grille 2D
        n_grid = 40
        idx_mx = selected_inputs.index(map_x_var)
        idx_my = selected_inputs.index(map_y_var)

        gx = np.linspace(float(X_min[idx_mx]), float(X_max[idx_mx]), n_grid)
        gy = np.linspace(float(X_min[idx_my]), float(X_max[idx_my]), n_grid)
        GX, GY = np.meshgrid(gx, gy)

        # Construction de la matrice pour batch predict
        flat_X = GX.ravel()
        flat_Y = GY.ravel()
        n_total_mesh = len(flat_X)

        mesh_batch = np.zeros((n_total_mesh, len(selected_inputs)))
        for col_idx, col_name in enumerate(selected_inputs):
            if col_name == map_x_var:
                mesh_batch[:, col_idx] = flat_X
            elif col_name == map_y_var:
                mesh_batch[:, col_idx] = flat_Y
            else:
                mesh_batch[:, col_idx] = fixed_params_2d[col_name]

        model_2d = trained_models[map_target]
        Z_flat, _ = model_2d.predict_batch(mesh_batch)
        Z_grid = Z_flat.reshape(GX.shape)

        # Tracé Plotly Contour
        fig_2d = go.Figure()

        fig_2d.add_trace(
            go.Contour(
                x=gx,
                y=gy,
                z=Z_grid,
                colorscale="Viridis",
                contours=dict(
                    coloring="heatmap",
                    showlabels=True,
                    labelfont=dict(size=11, color="white"),
                ),
                colorbar=dict(title=f"{map_target}"),
                hovertemplate=f"{map_x_var}: %{{x:.3f}}<br>{map_y_var}: %{{y:.3f}}<br>{map_target}: %{{z:.5f}}<extra></extra>",
            )
        )

        # Superposition des points CFD réels
        fig_2d.add_trace(
            go.Scatter(
                x=df[map_x_var],
                y=df[map_y_var],
                mode="markers",
                name="Points CFD réels",
                marker=dict(size=10, color="red", symbol="circle-open", line=dict(color="white", width=2)),
                text=df["Cas"] if "Cas" in df else None,
                hovertemplate=f"Cas: %{{text}}<br>{map_x_var}: %{{x}}<br>{map_y_var}: %{{y}}<br>CFD réel: %{{marker.color}}<extra></extra>",
            )
        )

        fig_2d.update_layout(
            title=f"Carte de sensibilité 2D : {map_target} = f({map_x_var}, {map_y_var})",
            xaxis_title=map_x_var,
            yaxis_title=map_y_var,
            template="plotly_white",
            margin=dict(l=40, r=40, t=50, b=40),
        )

        st.plotly_chart(fig_2d, use_container_width=True)
        st.caption(
            "⚠️ *La carte est générée à partir du métamodèle de krigeage. "
            "Les cercles rouges indiquent l'emplacement exact des calculs CFD d'entraînement.*"
        )


# ==============================================================================
# ONGLET 4 : DIAGNOSTIC DU MODELE, PARITE ET THETA
# ==============================================================================

with tab_diag:
    st.subheader("Diagnostic scientifique du krigeage")
    st.caption("Comparaison sur les données d'apprentissage et inspection des hyperparamètres optimisés.")

    # 1. Résumé des hyperparamètres Theta
    st.markdown("##### Paramètres optimaux du modèle (Theta & Vraisemblance)")

    theta_rows = []
    for t_name in selected_targets:
        m = trained_models[t_name]
        for f_idx, f_name in enumerate(m.feature_names):
            theta_rows.append({
                "Grandeur cible": t_name,
                "Variable d'entrée": f_name,
                "Theta optimal (θ)": f"{m.theta[f_idx]:.6f}",
                "Optimisé": "Oui (L-BFGS-B)" if m.is_optimized else "Non (Manuel)",
                "Statut optimisation": m.optimization_message,
                "Log-Vraisemblance concentrée": f"{m.objectif:.4f}",
                "Moyenne constante (μ)": f"{m.mu:.6f}",
                "Variance résiduelle (σ²)": f"{m.sigma2:.6e}",
                "Pépite (nugget)": f"{m.nugget:.1e}",
            })

    df_theta = pd.DataFrame(theta_rows)
    st.dataframe(df_theta, use_container_width=True)

    st.markdown("---")

    # 2. Graphiques de parité (Valeurs prédites vs Valeurs réelles CFD)
    st.markdown("##### Comparaison : Valeurs prédites vs Valeurs réelles (Données d'entraînement)")

    cols_par = st.columns(len(selected_targets))

    for idx_t, t_name in enumerate(selected_targets):
        with cols_par[idx_t]:
            m = trained_models[t_name]
            y_real = m.Y_train

            # Prédictions sur tous les points d'apprentissage
            X_train_phys = df[m.feature_names].to_numpy(dtype=float)
            y_pred, _ = m.predict_batch(X_train_phys)

            # Métriques d'erreur sur l'apprentissage
            res = y_real - y_pred
            rmse = float(np.sqrt(np.mean(res ** 2)))
            mae = float(np.mean(np.abs(res)))
            max_err = float(np.max(np.abs(res)))

            # Tracé
            fig_par = go.Figure()

            # Droite y = x
            min_lim = min(float(y_real.min()), float(y_pred.min()))
            max_lim = max(float(y_real.max()), float(y_pred.max()))
            delta = (max_lim - min_lim) * 0.05
            line_min = min_lim - delta
            line_max = max_lim + delta

            fig_par.add_trace(
                go.Scatter(
                    x=[line_min, line_max],
                    y=[line_min, line_max],
                    mode="lines",
                    name="Idéal y = x",
                    line=dict(color="#94a3b8", dash="dash"),
                )
            )

            # Points
            fig_par.add_trace(
                go.Scatter(
                    x=y_real,
                    y=y_pred,
                    mode="markers",
                    name=f"Points d'apprentissage ({t_name})",
                    marker=dict(size=9, color="#2563eb", symbol="circle"),
                    text=df["Cas"] if "Cas" in df else None,
                    hovertemplate="Cas: %{text}<br>Réel: %{x:.6f}<br>Prédit: %{y:.6f}<extra></extra>",
                )
            )

            fig_par.update_layout(
                title=f"Parité {t_name} (RMSE = {rmse:.2e})",
                xaxis_title=f"{t_name} réel (CFD)",
                yaxis_title=f"{t_name} prédit (Krigeage)",
                template="plotly_white",
                margin=dict(l=30, r=30, t=40, b=30),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )

            st.plotly_chart(fig_par, use_container_width=True)

            st.caption(
                f"**Métriques {t_name} (sur l'apprentissage) :**<br>"
                f"• RMSE : `{rmse:.6e}`<br>"
                f"• Erreur max : `{max_err:.6e}`",
                unsafe_allow_html=True,
            )

    st.markdown(
        """
        <div class="scientific-notice">
            <b>Note méthodologique importante :</b><br>
            Le krigeage sans pépite possède la propriété mathématique d'interpolation exacte (l'erreur aux points d'apprentissage est théoriquement nulle, aux tolérances numériques près).
            Ce graphique illustre la bonne reproduction des points d'entraînement mais <b>ne constitue pas à lui seul une validation de la capacité de généralisation</b> sur des points indépendants.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ==============================================================================
# ONGLET 5 : DONNEES BRUTES D'APPRENTISSAGE
# ==============================================================================

with tab_data:
    st.subheader("Données CFD d'apprentissage")
    st.caption("Visualisation du tableau de données d'origine.")

    st.dataframe(df, use_container_width=True)

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.markdown("**Statistiques descriptives des entrées :**")
        st.dataframe(df[selected_inputs].describe(), use_container_width=True)

    with col_d2:
        st.markdown("**Statistiques descriptives des sorties :**")
        st.dataframe(df[selected_targets].describe(), use_container_width=True)
