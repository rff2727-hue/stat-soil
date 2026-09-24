"""
Análises complementares: correlações e componentes principais.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class ResultadoCorrelacao:
    nomes: list
    R: np.ndarray
    P: np.ndarray
    n: np.ndarray
    metodo: str
    base: str

    def tabela(self, idioma="pt"):
        k = len(self.nomes)
        t = pd.DataFrame("", index=self.nomes, columns=self.nomes)
        for i in range(k):
            for j in range(k):
                if i == j:
                    t.iloc[i, j] = "1"
                elif j < i:
                    est = "***" if self.P[i, j] < 0.001 else "**" if self.P[i, j] < 0.01 else "*" if self.P[i, j] < 0.05 else "ns"
                    v = f"{self.R[i, j]:.2f}"
                    if idioma == "pt":
                        v = v.replace(".", ",")
                    t.iloc[i, j] = f"{v.replace('-', '−')}{est if est != 'ns' else ''}"
        return t


def correlacoes(df: pd.DataFrame, variaveis: list, metodo="pearson", agrupar_por=None) -> ResultadoCorrelacao:
    """Correlação entre variáveis; se `agrupar_por` for dado, usa médias dos tratamentos."""
    d = df[variaveis].apply(pd.to_numeric, errors="coerce")
    base = "observações"
    if agrupar_por:
        d = d.groupby(df[agrupar_por].astype(str) if isinstance(agrupar_por, str)
                      else [df[c].astype(str) for c in agrupar_por]).mean()
        base = "médias de tratamentos"
    k = len(variaveis)
    R = np.eye(k)
    P = np.zeros((k, k))
    N = np.zeros((k, k), int)
    for i in range(k):
        for j in range(i + 1, k):
            par = d.iloc[:, [i, j]].dropna()
            N[i, j] = N[j, i] = len(par)
            if len(par) < 3 or par.iloc[:, 0].std() == 0 or par.iloc[:, 1].std() == 0:
                R[i, j] = R[j, i] = np.nan
                P[i, j] = P[j, i] = np.nan
                continue
            if metodo == "spearman":
                r, p = stats.spearmanr(par.iloc[:, 0], par.iloc[:, 1])
            else:
                r, p = stats.pearsonr(par.iloc[:, 0], par.iloc[:, 1])
            R[i, j] = R[j, i] = r
            P[i, j] = P[j, i] = p
    return ResultadoCorrelacao([str(v) for v in variaveis], R, P, N,
                               "Pearson" if metodo == "pearson" else "Spearman", base)


@dataclass
class ResultadoPCA:
    nomes: list
    escores: np.ndarray
    cargas: np.ndarray            # correlações variável × componente
    autovalores: np.ndarray
    explicada: np.ndarray
    grupos: np.ndarray
    rotulos_linhas: list
    base: str

    def tabela_autovalores(self):
        k = len(self.autovalores)
        return pd.DataFrame({"Componente": [f"CP{i + 1}" for i in range(k)], "Autovalor": self.autovalores,
                             "Variância explicada (%)": 100 * self.explicada,
                             "Acumulada (%)": 100 * np.cumsum(self.explicada)})

    def tabela_cargas(self, n=None):
        n = n or min(4, self.cargas.shape[1])
        return pd.DataFrame(self.cargas[:, :n], index=self.nomes, columns=[f"CP{i + 1}" for i in range(n)])


def pca(df: pd.DataFrame, variaveis: list, grupo=None, usar_medias=False) -> ResultadoPCA:
    d = df[variaveis].apply(pd.to_numeric, errors="coerce")
    g = df[grupo].astype(str).to_numpy() if grupo else np.array([""] * len(df))
    if usar_medias and grupo:
        d = d.groupby(g).mean()
        ordem = list(dict.fromkeys(g))
        d = d.reindex(ordem)
        g = np.array(ordem)
        rot = ordem
        base = "médias de tratamentos"
    else:
        ok = d.notna().all(axis=1).to_numpy()
        d = d[ok]
        g = g[ok]
        rot = [str(i + 2) for i in np.where(ok)[0]]
        base = "observações"
    X = d.to_numpy(float)
    sd = X.std(axis=0, ddof=1)
    manter = sd > 0
    X = X[:, manter]
    nomes = [str(v) for v, m in zip(variaveis, manter) if m]
    Z = (X - X.mean(axis=0)) / X.std(axis=0, ddof=1)
    U, s, Vt = np.linalg.svd(Z, full_matrices=False)
    n = Z.shape[0]
    autov = s ** 2 / (n - 1)
    expl = autov / autov.sum()
    escores = U * s
    cargas = Vt.T * np.sqrt(autov)  # correlação variável-componente
    # convenção de sinal: maior carga absoluta positiva em cada componente
    for j in range(cargas.shape[1]):
        if cargas[np.argmax(np.abs(cargas[:, j])), j] < 0:
            cargas[:, j] *= -1
            escores[:, j] *= -1
    return ResultadoPCA(nomes, escores, cargas, autov, expl, g, rot, base)
