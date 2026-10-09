"""
Modelo misto (REML) para parcelas subdivididas, sub-subdivididas e faixas com
unidades experimentais perdidas.

Efeitos fixos: médias de células (combinações de tratamentos) + blocos.
Efeitos aleatórios: unidades de cada estrato (parcela; subparcela; faixas).
Testes F de Wald sobre as médias de células, com GL do estrato do termo
calculados pelo método de "contenção" (posto das matrizes de unidades).
"""
from __future__ import annotations

import math
import warnings

import numpy as np
import pandas as pd
from scipy import stats

from .modelo import ERRO_ROTULO, ErroDelineamento


def _dummies(cod, k):
    X = np.zeros((len(cod), k))
    X[np.arange(len(cod)), cod] = 1.0
    return X


def _cod(s):
    lv = list(dict.fromkeys(s))
    m = {v: i for i, v in enumerate(lv)}
    return np.array([m[v] for v in s]), lv


def _rank(*mats):
    M = np.hstack([m for m in mats if m is not None and m.shape[1]])
    return np.linalg.matrix_rank(M) if M.size else 0


def reml(y, X, Zs, inicios=(-2.0, 0.0, 2.0)):
    """REML com componentes de variância (σ² perfilado). Zs: matrizes de incidência dos efeitos aleatórios."""
    from scipy import optimize
    n, p = X.shape
    ZZ = [Z @ Z.T for Z in Zs]
    r = np.linalg.matrix_rank(X)

    def partes(theta):
        g = np.exp(theta)
        H = np.eye(n) + sum(gi * M for gi, M in zip(g, ZZ))
        L = np.linalg.cholesky(H)
        Hi = np.linalg.inv(H)
        XtHiX = X.T @ Hi @ X
        A = np.linalg.pinv(XtHiX)
        P = Hi - Hi @ X @ A @ X.T @ Hi
        s2 = float(y @ P @ y) / (n - r)
        ld_H = 2 * np.sum(np.log(np.diag(L)))
        sv = np.linalg.svd(XtHiX, compute_uv=False)
        ld_X = np.sum(np.log(sv[sv > sv.max() * 1e-10]))
        return g, H, Hi, A, s2, ld_H, ld_X

    def negll(theta):
        try:
            *_, s2, ld_H, ld_X = partes(theta)
        except np.linalg.LinAlgError:
            return 1e30
        if s2 <= 0:
            return 1e30
        return 0.5 * ((n - r) * np.log(s2) + ld_H + ld_X)

    k = len(Zs)
    melhor = None
    for ini in inicios:
        x0 = np.full(k, ini)
        res = optimize.minimize(negll, x0, method="L-BFGS-B", bounds=[(-25, 12)] * k)
        if melhor is None or res.fun < melhor.fun:
            melhor = res
    g, H, Hi, A, s2, *_ = partes(melhor.x)
    beta = A @ X.T @ Hi @ y
    resid_m = y - X @ beta
    ajust = X @ beta + sum(gi * (Z @ (Z.T @ (Hi @ resid_m))) for gi, Z in zip(g, Zs))
    return {"beta": beta, "cov_beta": s2 * A, "sigma2": s2, "componentes": [float(gi * s2) for gi in g],
            "ajustados": ajust, "convergiu": bool(melhor.success)}


class EstimadorMisto:
    def __init__(self, dados):
        d, spec = dados.d, dados.spec
        fk = [f"F{i}" for i in range(len(spec.fatores))]
        self.celulas = dados.celulas
        cod, _ = _cod(d["CEL"].map(lambda x: x))
        mapa = {c: i for i, c in enumerate(self.celulas)}
        cod = d["CEL"].map(mapa).to_numpy()
        c = len(self.celulas)
        Xc = _dummies(cod, c)
        n = len(d)
        dbc = spec.base == "DBC"
        bl, lvb = _cod(d["BL"].astype(str))
        Xb = _dummies(bl, len(lvb))
        Zb = (Xb[:, :-1] - Xb[:, [-1]]) if (dbc and len(lvb) > 1) else np.zeros((n, 0))
        X = np.hstack([Xc, Zb])
        y = d["y"].to_numpy(float)
        # unidades aleatórias por estrato
        comps, unidades = {}, {}
        if spec.estrutura == "faixas":
            iA = [i for i, f in enumerate(spec.fatores) if f.estrato == 1][0]
            iB = [i for i, f in enumerate(spec.fatores) if f.estrato == 2][0]
            for nome, cols in (("Erro (a)", ["BL", fk[iA]]), ("Erro (b)", ["BL", fk[iB]])):
                u, lv = _cod(d[cols].astype(str).agg("|".join, axis=1))
                unidades[nome] = _dummies(u, len(lv))
            self.estrato_fator = {iA: "Erro (a)", iB: "Erro (b)"}
            residuo = "Erro (c)"
        else:
            L = spec.n_niveis_estrato
            for l in range(1, L):
                cols = ["BL"] + [fk[i] for i, f in enumerate(spec.fatores) if f.estrato <= l]
                u, lv = _cod(d[cols].astype(str).agg("|".join, axis=1))
                unidades[ERRO_ROTULO[l]] = _dummies(u, len(lv))
            self.estrato_fator = {i: ERRO_ROTULO[f.estrato] for i, f in enumerate(spec.fatores)}
            residuo = ERRO_ROTULO[L]
        self.residuo = residuo
        fit = reml(y, X, list(unidades.values()))
        self.fit = fit
        p = X.shape[1]
        fe = fit["beta"]
        cov = fit["cov_beta"]
        self.m = fe[:c]
        self.V = cov[:c, :c]
        self.X, self.y = X, y
        self.ajustados = fit["ajustados"]
        self.residuos = y - self.ajustados
        self.sigma2 = float(fit["sigma2"])
        vcomp = fit["componentes"]
        nomes_vc = list(unidades)
        self.componentes = {k: float(v) for k, v in zip(nomes_vc, vcomp)}
        self.componentes[residuo] = self.sigma2
        # GL por contenção
        gl = {}
        if spec.estrutura == "faixas":
            for nome, Z in unidades.items():
                fator = [i for i, e in self.estrato_fator.items() if e == nome][0]
                cod_f, lvf = _cod(d[fk[fator]].astype(str))
                gl[nome] = _rank(Z) - _rank(Xb if dbc else np.ones((n, 1)), _dummies(cod_f, len(lvf)))
            gl[residuo] = n - _rank(Xc, *unidades.values())
        else:
            anterior = Xb if dbc else np.ones((n, 1))
            nomes = list(unidades)
            for k, nome in enumerate(nomes):
                l = k + 1
                fat = [i for i, f in enumerate(spec.fatores) if f.estrato <= l]
                cel_l, lvl = _cod(d[[fk[i] for i in fat]].astype(str).agg("|".join, axis=1))
                gl[nome] = _rank(unidades[nome]) - _rank(anterior, _dummies(cel_l, len(lvl)))
                anterior = unidades[nome]
            gl[residuo] = n - _rank(Xc, anterior)
        self.gl_estrato = {k: max(int(v), 1) for k, v in gl.items()}
        self.gl_res = self.gl_estrato[residuo]
        nc = np.bincount(cod, minlength=c).astype(float)
        self.C_iid = np.diag(1.0 / nc)
        # E(QM) aproximado por estrato (para CV): σ² + n_sub·σ²_u
        tam = {}
        for nome, Z in unidades.items():
            tam[nome] = float(np.mean(Z.sum(axis=0)))
        self.qm_esperado = {}
        acum = self.sigma2
        for nome in reversed(list(unidades)):
            acum_n = self.sigma2 + sum(tam[k2] * self.componentes.get(k2, 0) for k2 in unidades
                                       if list(unidades).index(k2) >= list(unidades).index(nome)) \
                if spec.estrutura != "faixas" else self.sigma2 + tam[nome] * self.componentes.get(nome, 0)
            self.qm_esperado[nome] = acum_n
        self.qm_esperado[residuo] = self.sigma2
        self.qm_res = self.sigma2
        self.estratos = {k: (self.qm_esperado[k], self.gl_estrato[k]) for k in self.gl_estrato}
        U, s_, _ = np.linalg.svd(np.hstack([X] + list(unidades.values())), full_matrices=False)
        U = U[:, s_ > s_.max() * 1e-10]
        self.h = np.sum(U ** 2, axis=1)

    def cov(self, K):
        return K @ self.V @ K.T

    def gl(self, K):
        return self.erro_combinado(K)[1]

    def preparar_pesos(self, dados):
        from .anova import _estratos_multiestrato
        d = dados.d
        projs, _ = _estratos_multiestrato(dados)
        mapa = {c: i for i, c in enumerate(self.celulas)}
        cod = d["CEL"].map(mapa).to_numpy()
        C = _dummies(cod, len(self.celulas))
        C = C / C.sum(axis=0)
        self.M = {nome: (proj(C)).T @ proj(C) for nome, proj in projs.items()}

    def erro_combinado(self, K):
        """QM equivalente (por observação) e GL de Satterthwaite a partir dos pesos de estrato."""
        K = np.atleast_2d(K)
        Mt = sum(self.M.values())
        inv = np.linalg.pinv(K @ Mt @ K.T)
        q = max(np.linalg.matrix_rank(K @ Mt @ K.T), 1)
        a = {s: float(np.trace(K @ self.M[s] @ K.T @ inv)) / q for s in self.M}
        qm = sum(a[s] * self.qm_esperado[s] for s in a)
        den = sum((a[s] * self.qm_esperado[s]) ** 2 / self.gl_estrato[s] for s in a if a[s] > 1e-10)
        gl = qm ** 2 / den if den > 0 else float(self.gl_res)
        return float(qm), float(gl)


def anova_misto(dados, alfa, termos_fn, nome_termo, K_termo):
    est = EstimadorMisto(dados)
    est.preparar_pesos(dados)
    spec = dados.spec
    y = dados.d["y"].to_numpy(float)
    linhas_t = []
    from .anova import LinhaAnova  # import tardio para evitar ciclo
    nf = len(spec.fatores)
    if spec.estrutura == "faixas":
        iA = [i for i, f in enumerate(spec.fatores) if f.estrato == 1][0]
        iB = [i for i, f in enumerate(spec.fatores) if f.estrato == 2][0]
        estr = {(iA,): "Erro (a)", (iB,): "Erro (b)", tuple(sorted((iA, iB))): est.residuo}
    else:
        estr = {T: ERRO_ROTULO[max(spec.fatores[i].estrato for i in T)] for T in termos_fn(nf)}
    linhas = []
    for e in list(est.gl_estrato):
        for T in termos_fn(nf):
            if estr[T] != e:
                continue
            K = K_termo(dados, T)
            Km = K @ est.m
            S = est.cov(K)
            q = np.linalg.matrix_rank(S)
            F = float(Km @ np.linalg.pinv(S) @ Km) / max(q, 1)
            gl_d = est.gl_estrato[e]
            linhas.append(LinhaAnova(nome_termo(T, spec), q, None, None, F, float(stats.f.sf(F, q, gl_d)),
                                     termo=T, erro=e))
        linhas.append(LinhaAnova(f"{e} — variância", est.gl_estrato[e], None, est.componentes.get(e, np.nan),
                                 tipo="erro"))
    sqt = float(np.sum((y - y.mean()) ** 2))
    linhas.append(LinhaAnova("Total", len(y) - 1, sqt, tipo="total"))
    mu = abs(float(dados.d["y_orig"].mean()))
    cv = {f"CV {k.replace('Erro ', '')} (%)": 100 * math.sqrt(max(v, 0)) / mu for k, v in est.qm_esperado.items()}
    r2 = 1 - float(np.sum(est.residuos ** 2)) / sqt if sqt > 0 else np.nan
    est.estrato_termo = estr
    return est, linhas, cv, r2, est.residuos, est.ajustados, est.h, est.sigma2
