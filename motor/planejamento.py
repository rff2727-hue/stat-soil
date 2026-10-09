"""
Planejamento: número de repetições, poder do teste F e diferença mínima
significativa esperada a partir de um coeficiente de variação.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def _q(p, k, gl):
    """Quantil da amplitude studentizada (tabela interpolada do statsmodels: rápida e com ~3 dígitos,
    suficiente para planejamento); recorre ao SciPy fora da faixa tabelada."""
    try:
        from statsmodels.stats.libqsturng import qsturng
        if 2 <= k <= 200 and gl >= 1 and 0.1 <= p <= 0.999:
            return float(qsturng(p, k, gl))
    except Exception:
        pass
    return float(stats.studentized_range.ppf(p, k, gl))


def poder_repeticoes(t, cv, diferenca_pct, alfa=0.05, delineamento="DBC", r_max=20):
    """Para cada nº de repetições r: GL do resíduo, poder do teste F para detectar duas médias que diferem
    em `diferenca_pct` % da média geral (configuração menos favorável), e DMS de Tukey em % da média."""
    linhas = []
    for r in range(2, r_max + 1):
        gl2 = (t - 1) * (r - 1) if delineamento == "DBC" else t * (r - 1)
        if gl2 < 1:
            continue
        gl1 = t - 1
        lam = r * (diferenca_pct ** 2 / 2) / cv ** 2
        fcrit = stats.f.ppf(1 - alfa, gl1, gl2)
        poder = 1 - stats.ncf.cdf(fcrit, gl1, gl2, lam)
        q = _q(1 - alfa, t, gl2)
        dms = q * cv / np.sqrt(r)
        linhas.append({"Repetições": r, "GL resíduo": gl2, "Poder (%)": 100 * poder, "DMS Tukey (% da média)": dms})
    return pd.DataFrame(linhas)


def repeticoes_necessarias(t, cv, diferenca_pct, alfa=0.05, poder_alvo=0.8, delineamento="DBC"):
    tab = poder_repeticoes(t, cv, diferenca_pct, alfa, delineamento, r_max=60)
    ok = tab[tab["Poder (%)"] >= 100 * poder_alvo]
    return (int(ok.iloc[0]["Repetições"]) if len(ok) else None), tab
