"""
Alternativas quando os pressupostos da ANOVA falham.

* ANOVA de Welch (variâncias heterogêneas) + Games-Howell;
* Kruskal-Wallis (DIC) + Dunn com correção de Holm;
* Friedman (DBC completo) + Conover (1999) com correção de Holm.

Todas tratam as combinações de tratamentos como um único fator.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from .comparacoes import letras_de_matriz


@dataclass
class ResultadoRobusto:
    teste: str
    estatistica: float
    gl: str
    p: float
    posthoc: str
    tabela: pd.DataFrame          # por tratamento: n, média/mediana, posto médio, letras
    pares: pd.DataFrame           # comparações par a par
    nota: str = ""


def _holm(p):
    p = np.asarray(p, float)
    m = len(p)
    o = np.argsort(p)
    adj = np.empty(m)
    acc = 0.0
    for r, i in enumerate(o):
        acc = max(acc, min(1.0, (m - r) * p[i]))
        adj[i] = acc
    return adj


def _pares_df(nomes, pares):
    return pd.DataFrame(pares, columns=["Tratamento 1", "Tratamento 2", "Diferença", "Estatística", "p ajustado"])


def welch_games_howell(y, g, alfa=0.05):
    df = pd.DataFrame({"y": y, "g": g})
    grupos = list(dict.fromkeys(g))
    d = df.groupby("g", sort=False)["y"]
    n = d.size().reindex(grupos).to_numpy(float)
    m = d.mean().reindex(grupos).to_numpy(float)
    v = d.var(ddof=1).reindex(grupos).to_numpy(float)
    k = len(grupos)
    w = n / v
    mw = np.sum(w * m) / np.sum(w)
    A = np.sum(w * (m - mw) ** 2) / (k - 1)
    tmp = np.sum((1 - w / np.sum(w)) ** 2 / (n - 1))
    B = 1 + 2 * (k - 2) / (k ** 2 - 1) * tmp
    F = A / B
    gl2 = (k ** 2 - 1) / (3 * tmp)
    p = float(stats.f.sf(F, k - 1, gl2))
    sig = np.zeros((k, k), bool)
    pares = []
    for i in range(k):
        for j in range(i + 1, k):
            se = math.sqrt(v[i] / n[i] + v[j] / n[j])
            q = abs(m[i] - m[j]) / se * math.sqrt(2)
            glw = (v[i] / n[i] + v[j] / n[j]) ** 2 / ((v[i] / n[i]) ** 2 / (n[i] - 1) + (v[j] / n[j]) ** 2 / (n[j] - 1))
            pij = float(stats.studentized_range.sf(q, k, glw))
            sig[i, j] = sig[j, i] = pij < alfa
            pares.append((grupos[i], grupos[j], m[i] - m[j], q, pij))
    tab = pd.DataFrame({"Tratamento": grupos, "n": n.astype(int), "Média": m, "DP": np.sqrt(v),
                        "Letras": letras_de_matriz(m, sig)})
    return ResultadoRobusto("ANOVA de Welch", float(F), f"{k - 1}; {gl2:.1f}".replace(".", ","), p, "Games-Howell", tab,
                            _pares_df(grupos, pares), "Não supõe variâncias iguais entre tratamentos.")


def kruskal_dunn(y, g, alfa=0.05):
    df = pd.DataFrame({"y": y, "g": g})
    grupos = list(dict.fromkeys(g))
    amostras = [df.loc[df.g == gg, "y"].to_numpy(float) for gg in grupos]
    H, p = stats.kruskal(*amostras)
    r = stats.rankdata(df["y"])
    df["r"] = r
    N = len(df)
    n = df.groupby("g", sort=False).size().reindex(grupos).to_numpy(float)
    R = df.groupby("g", sort=False)["r"].mean().reindex(grupos).to_numpy(float)
    _, cont = np.unique(df["y"], return_counts=True)
    empates = np.sum(cont ** 3 - cont) / (12 * (N - 1))
    s2 = N * (N + 1) / 12 - empates
    k = len(grupos)
    brutos, idx = [], []
    for i in range(k):
        for j in range(i + 1, k):
            z = (R[i] - R[j]) / math.sqrt(s2 * (1 / n[i] + 1 / n[j]))
            brutos.append(2 * stats.norm.sf(abs(z)))
            idx.append((i, j, z))
    adj = _holm(brutos) if brutos else []
    sig = np.zeros((k, k), bool)
    pares = []
    for (i, j, z), pa in zip(idx, adj):
        sig[i, j] = sig[j, i] = pa < alfa
        pares.append((grupos[i], grupos[j], R[i] - R[j], z, pa))
    med = df.groupby("g", sort=False)["y"].median().reindex(grupos).to_numpy(float)
    tab = pd.DataFrame({"Tratamento": grupos, "n": n.astype(int), "Mediana": med, "Posto médio": R,
                        "Letras": letras_de_matriz(R, sig)})
    return ResultadoRobusto("Kruskal-Wallis", float(H), str(k - 1), float(p), "Dunn (Holm)", tab,
                            _pares_df(grupos, pares), "Teste baseado em postos; letras ordenadas pelo posto médio.")


def friedman_conover(y, g, bloco, alfa=0.05):
    df = pd.DataFrame({"y": y, "g": g, "b": bloco})
    tab = df.pivot_table(index="b", columns="g", values="y", aggfunc="mean")
    grupos = [gg for gg in dict.fromkeys(g) if gg in tab.columns]
    tab = tab[grupos].dropna()
    b, k = tab.shape
    if b < 2 or k < 2:
        raise ValueError("Friedman requer blocos completos.")
    chi2, p = stats.friedmanchisquare(*[tab[c].to_numpy() for c in grupos])
    ranks = tab.rank(axis=1).to_numpy()
    Ri = ranks.sum(axis=0)
    A = np.sum(ranks ** 2)
    gl = (b - 1) * (k - 1)
    denom = math.sqrt(2 * (b * A - np.sum(Ri ** 2)) / gl) if (b * A - np.sum(Ri ** 2)) > 0 else np.nan
    brutos, idx = [], []
    for i in range(k):
        for j in range(i + 1, k):
            t = abs(Ri[i] - Ri[j]) / denom if denom and np.isfinite(denom) else np.inf
            brutos.append(2 * stats.t.sf(t, gl))
            idx.append((i, j, t))
    adj = _holm(brutos) if brutos else []
    sig = np.zeros((k, k), bool)
    pares = []
    for (i, j, t), pa in zip(idx, adj):
        sig[i, j] = sig[j, i] = pa < alfa
        pares.append((grupos[i], grupos[j], (Ri[i] - Ri[j]) / b, t, pa))
    med = tab.median().to_numpy(float)
    out = pd.DataFrame({"Tratamento": grupos, "Blocos": b, "Mediana": med, "Posto médio": Ri / b,
                        "Letras": letras_de_matriz(Ri, sig)})
    return ResultadoRobusto("Friedman", float(chi2), str(k - 1), float(p), "Conover (Holm)", out,
                            _pares_df(grupos, pares), "Teste baseado em postos dentro de cada bloco.")


def alternativas(res, alfa=None):
    """Executa as alternativas adequadas ao delineamento de um ResultadoVariavel."""
    alfa = alfa or res.alfa
    d = res.dados.d
    y = d["y_orig"].to_numpy(float)
    g = d["CEL"].astype(str).to_numpy()
    out = []
    try:
        out.append(welch_games_howell(y, g, alfa))
    except Exception:
        pass
    spec = res.spec
    if spec.base == "DBC" and not spec.multiestrato:
        try:
            out.append(friedman_conover(y, g, d["BL"].astype(str).to_numpy(), alfa))
        except Exception:
            pass
    if spec.base == "DIC" or spec.base == "DBC":
        try:
            out.append(kruskal_dunn(y, g, alfa))
        except Exception:
            pass
    return out
