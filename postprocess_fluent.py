from pathlib import Path
import re, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
OUT = HERE / 'post'
# Doivent correspondre aux Reference Values de Fluent et au cas simulé.
RHO_REF, U_REF, P_REF, CHORD = 1.225, 30.0, 0.0, 1.0
Q_REF = 0.5 * RHO_REF * U_REF**2


def read_report(path):
    if not path.exists():
        print(f'[AVERTISSEMENT] {path.name} absent')
        return pd.DataFrame(columns=['iteration', 'value'])
    rows = []
    for line in path.read_text(errors='ignore').splitlines():
        s = line.strip()
        if not s or s.startswith(('#', ';', '((')):
            continue
        nums = re.findall(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?', s)
        if len(nums) >= 2:
            try: rows.append((float(nums[0]), float(nums[-1])))
            except ValueError: pass
    if not rows:
        raise ValueError(f'Aucune paire iteration/valeur trouvée dans {path.name}')
    return (pd.DataFrame(rows, columns=['iteration', 'value'])
            .replace([np.inf, -np.inf], np.nan).dropna()
            .drop_duplicates('iteration', keep='last').sort_values('iteration'))


def plot_convergence(df, label, filename):
    if df.empty: return
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(df.iteration, df.value, linewidth=1.5)
    ax.set(xlabel='Itération', ylabel=label, title=f'Convergence de {label}')
    ax.grid(True, alpha=.3); fig.tight_layout(); fig.savefig(OUT/filename, dpi=180); plt.close(fig)


def read_pressure(path):
    if not path.exists():
        print('[AVERTISSEMENT] airfoil_pressure.csv absent : Cp/Cpt ne peuvent pas être tracés.')
        return None
    # CSV avec en-tête recommandé : x-coordinate,y-coordinate,pressure,total-pressure
    df = None
    for sep in [',', ';', '\\s+', '\\t']:
        try:
            temp = pd.read_csv(path, sep=sep, engine='python', comment='#')
            if temp.shape[1] >= 3: df = temp; break
        except Exception: pass
    if df is None: raise ValueError('Export pression illisible : fournir un CSV avec en-tête.')
    norm = {re.sub(r'[^a-z0-9]', '', str(c).lower()): c for c in df.columns}
    def col(*names):
        for n in names:
            k = re.sub(r'[^a-z0-9]', '', n.lower())
            if k in norm: return norm[k]
        return None
    x, y, p, pt = col('x-coordinate','x coordinate','x'), col('y-coordinate','y coordinate','y'), col('pressure','static-pressure'), col('total-pressure','total pressure','absolute-total-pressure')
    if x is None or p is None:
        raise ValueError('Colonnes x-coordinate et pressure introuvables dans airfoil_pressure.csv')
    out = pd.DataFrame({'x_m': pd.to_numeric(df[x], errors='coerce'), 'pressure_Pa': pd.to_numeric(df[p], errors='coerce')})
    if y: out['y_m'] = pd.to_numeric(df[y], errors='coerce')
    if pt: out['total_pressure_Pa'] = pd.to_numeric(df[pt], errors='coerce')
    return out.replace([np.inf,-np.inf],np.nan).dropna(subset=['x_m','pressure_Pa']).sort_values('x_m')


def plot_distribution(x, y, label, filename, invert=False):
    fig, ax = plt.subplots(figsize=(8, 4.8)); ax.plot(x, y, '-', linewidth=1.4)
    ax.set(xlabel='x/c', ylabel=label, title=f'Distribution de {label} sur le profil')
    ax.grid(True, alpha=.3)
    if invert: ax.invert_yaxis()
    fig.tight_layout(); fig.savefig(OUT/filename, dpi=180); plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    cl, cd = read_report(HERE/'cl_test.txt'), read_report(HERE/'cd_test.txt')
    plot_convergence(cl, 'Cl', 'cl_convergence.png'); plot_convergence(cd, 'Cd', 'cd_convergence.png')
    summary=[]
    for name, df in [('Cl',cl),('Cd',cd)]:
        if not df.empty: summary.append({'coefficient':name,'iteration_finale':df.iloc[-1].iteration,'valeur_finale':df.iloc[-1].value})
    if summary: pd.DataFrame(summary).to_csv(OUT/'coefficients.csv', index=False)
    pressure=read_pressure(HERE/'airfoil_pressure.csv')
    if pressure is not None:
        pressure['x_sur_c'] = pressure.x_m / CHORD
        pressure['Cp'] = (pressure.pressure_Pa-P_REF)/Q_REF
        plot_distribution(pressure.x_sur_c, pressure.Cp, 'Cp', 'cp_distribution.png', True)
        if 'total_pressure_Pa' in pressure:
            pressure['Cpt']=(pressure.total_pressure_Pa-P_REF)/Q_REF
            plot_distribution(pressure.x_sur_c, pressure.Cpt, 'Cpt', 'cpt_distribution.png', True)
        else: print('[AVERTISSEMENT] Champ total-pressure absent : Cpt non calculé.')
        pressure.to_csv(OUT/'pressure_distribution.csv', index=False)
    print(f'Post-traitement terminé : {OUT}')
    print('Vérifier RHO_REF, U_REF, P_REF et CHORD dans le script.')

if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print(f'[ERREUR POST-TRAITEMENT] {exc}', file=sys.stderr); sys.exit(1)
