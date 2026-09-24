"""
Testes de comparação de médias e atribuição de letras.

Todos os testes recebem:
    medias : array (k,)            médias (ou médias ajustadas) dos grupos
    var_dif: array (k, k)          variância da diferença entre cada par de médias
    gl     : float                 graus de liberdade do erro associado
    alfa   : float                 nível de significância

A variância da diferença (e não um único QME/r) é o que permite usar o mesmo
código para dados desbalanceados (Tukey-Kramer) e para desdobramentos de
parcelas subdivididas, cujos erros combinados vêm da aproximação de
Satterthwaite.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
from scipy import stats, optimize

METODOS = {
    "tukey": "Tukey (HSD)",
    "scott_knott": "Scott-Knott",
    "lsd": "LSD de Fisher (t)",
    "duncan": "Duncan",
    "snk": "Student-Newman-Keuls (SNK)",
    "bonferroni": "t com correção de Bonferroni",
    "dunnett": "Dunnett (vs. controle)",
}

METODOS_EN = {
    "tukey": "Tukey's HSD",
    "scott_knott": "Scott-Knott",
    "lsd": "Fisher's LSD",
    "duncan": "Duncan's multiple range",
    "snk": "Student-Newman-Keuls",
    "bonferroni": "Bonferroni-adjusted t",
    "dunnett": "Dunnett (vs. control)",
}


@dataclass
class ResultadoComparacao:
    metodo: str
    grupos: list
    medias: np.ndarray
    letras: list                      # uma string por grupo (vazio para Dunnett)
    pares: list = field(default_factory=list)   # dicts: g1, g2, dif, ep, p, sig
    dms: float | None = None          # diferença mínima significativa (balanceado)
    gl: float | None = None
    ep_medio: float | None = None     # erro padrão médio de uma média
    controle: str | None = None
    obs: str = ""

    def tabela_letras(self):
        return {g: l for g, l in zip(self.grupos, self.letras)}


# ----------------------------------------------------------------------------
# Quantis da amplitude studentizada (cache — o ppf é relativamente caro)
# ----------------------------------------------------------------------------
@lru_cache(maxsize=4096)
def _q_crit(prob: float, k: int, gl: float) -> float:
    gl = float(min(gl, 1e4))
    return float(stats.studentized_range.ppf(prob, k, gl))


def _q_sf(q: float, k: int, gl: float) -> float:
    gl = float(min(gl, 1e4))
    return float(stats.studentized_range.sf(q, k, gl))


# ----------------------------------------------------------------------------
# Letras: algoritmo insert-absorb (Piepho, 2004) a partir da matriz de
# significância. Letra "a" para o grupo de maior média.
# ----------------------------------------------------------------------------
def letras_de_matriz(medias: np.ndarray, sig: np.ndarray, maiusculas=False, decrescente=True) -> list:
    k = len(medias)
    if k == 0:
        return []
    ordem = np.argsort(-medias if decrescente else medias, kind="stable")
    conjuntos = [set(range(k))]
    for a_ in range(k):
        for b_ in range(a_ + 1, k):
            i, j = ordem[a_], ordem[b_]
            if not sig[i, j]:
                continue
            novos = []
            for s in conjuntos:
                if i in s and j in s:
                    novos.append(s - {i})
                    novos.append(s - {j})
                else:
                    novos.append(s)
            # absorção: remove conjuntos contidos em outros
            novos = [s for s in novos if s]
            unicos = []
            for s in novos:
                if s not in unicos:
                    unicos.append(s)
            conjuntos = [s for s in unicos if not any((s < t) for t in unicos)]
    # ordena conjuntos pela posição (no ranking) do seu melhor membro
    rank = {g: r for r, g in enumerate(ordem)}
    conjuntos.sort(key=lambda s: (min(rank[g] for g in s), -len(s)))
    alfabeto = _alfabeto(len(conjuntos), maiusculas)
    letras = ["" for _ in range(k)]
    for L, s in zip(alfabeto, conjuntos):
        for g in s:
            letras[g] += L
    return letras


def _alfabeto(n, maiusculas=False):
    base = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if maiusculas else "abcdefghijklmnopqrstuvwxyz"
    out = []
    for i in range(n):
        if i < 26:
            out.append(base[i])
        else:  # a1, b1 ... para mais de 26 grupos
            out.append(base[i % 26] + str(i // 26))
    return out


def _letras_de_particao(medias, grupos_idx, maiusculas=False):
    """Letras para testes que produzem partições (Scott-Knott)."""
    grupos_idx = sorted(grupos_idx, key=lambda g: -max(medias[i] for i in g))
    alfabeto = _alfabeto(len(grupos_idx), maiusculas)
    letras = [""] * len(medias)
    for L, g in zip(alfabeto, grupos_idx):
        for i in g:
            letras[i] = L
    return letras


# ----------------------------------------------------------------------------
# Testes baseados em pares
# ----------------------------------------------------------------------------
def _pares_base(medias, var_dif):
    k = len(medias)
    dif = medias[:, None] - medias[None, :]
    ep = np.sqrt(np.maximum(var_dif, 0))
    return k, dif, ep


def _montar_pares(grupos, medias, dif, ep, p, sig):
    out = []
    k = len(grupos)
    for i in range(k):
        for j in range(i + 1, k):
            out.append(dict(g1=grupos[i], g2=grupos[j], dif=float(dif[i, j]), ep_dif=float(ep[i, j]),
                            p=(None if p is None else float(p[i, j])), sig=bool(sig[i, j])))
    return out


def tukey(grupos, medias, var_dif, gl, alfa=0.05, maiusculas=False):
    medias = np.asarray(medias, float)
    k, dif, ep = _pares_base(medias, var_dif)
    p = np.ones((k, k))
    for i in range(k):
        for j in range(i + 1, k):
            q = abs(dif[i, j]) / (ep[i, j] / math.sqrt(2)) if ep[i, j] > 0 else np.inf
            p[i, j] = p[j, i] = _q_sf(q, k, gl) if k > 1 else 1.0
    sig = p < alfa
    qc = _q_crit(1 - alfa, k, gl) if k > 1 else np.nan
    dms = qc * np.nanmean(ep[np.triu_indices(k, 1)]) / math.sqrt(2) if k > 1 else None
    return ResultadoComparacao("tukey", list(grupos), medias, letras_de_matriz(medias, sig, maiusculas),
                               _montar_pares(grupos, medias, dif, ep, p, sig), dms, gl,
                               _ep_media(ep, k))


def lsd(grupos, medias, var_dif, gl, alfa=0.05, maiusculas=False, bonferroni=False):
    medias = np.asarray(medias, float)
    k, dif, ep = _pares_base(medias, var_dif)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.abs(dif) / ep
    p = 2 * stats.t.sf(t, gl)
    np.fill_diagonal(p, 1.0)
    m = k * (k - 1) / 2
    if bonferroni:
        p = np.minimum(p * m, 1.0)
    sig = p < alfa
    a_ = alfa / m if bonferroni else alfa
    dms = stats.t.ppf(1 - a_ / 2, gl) * np.nanmean(ep[np.triu_indices(k, 1)]) if k > 1 else None
    return ResultadoComparacao("bonferroni" if bonferroni else "lsd", list(grupos), medias,
                               letras_de_matriz(medias, sig, maiusculas),
                               _montar_pares(grupos, medias, dif, ep, p, sig), dms, gl, _ep_media(ep, k))


def _amplitudes_multiplas(grupos, medias, var_dif, gl, alfa, metodo, maiusculas):
    """SNK e Duncan: testes de amplitude múltipla com regra de fechamento."""
    medias = np.asarray(medias, float)
    k, dif, ep = _pares_base(medias, var_dif)
    ordem = np.argsort(-medias, kind="stable")
    sig = np.zeros((k, k), bool)
    naosig_intervalos = []
    # testa dos maiores intervalos para os menores
    for span in range(k, 1, -1):
        for a_ in range(0, k - span + 1):
            b_ = a_ + span - 1
            i, j = ordem[a_], ordem[b_]
            # fechamento: se contido num intervalo não significativo, não é sig
            if any(lo <= a_ and b_ <= hi for lo, hi in naosig_intervalos):
                continue
            if metodo == "snk":
                prob = 1 - alfa
            else:  # duncan
                prob = (1 - alfa) ** (span - 1)
            qc = _q_crit(prob, span, gl)
            crit = qc * ep[i, j] / math.sqrt(2)
            if abs(dif[i, j]) > crit:
                sig[i, j] = sig[j, i] = True
            else:
                naosig_intervalos.append((a_, b_))
    return ResultadoComparacao(metodo, list(grupos), medias, letras_de_matriz(medias, sig, maiusculas),
                               _montar_pares(grupos, medias, dif, ep, None, sig), None, gl, _ep_media(ep, k))


def snk(grupos, medias, var_dif, gl, alfa=0.05, maiusculas=False):
    return _amplitudes_multiplas(grupos, medias, var_dif, gl, alfa, "snk", maiusculas)


def duncan(grupos, medias, var_dif, gl, alfa=0.05, maiusculas=False):
    return _amplitudes_multiplas(grupos, medias, var_dif, gl, alfa, "duncan", maiusculas)


def _ep_media(ep, k):
    if k < 2:
        return None
    return float(np.nanmean(ep[np.triu_indices(k, 1)]) / math.sqrt(2))


# ----------------------------------------------------------------------------
# Scott-Knott (1974)
# ----------------------------------------------------------------------------
def scott_knott(grupos, medias, var_dif, gl, alfa=0.05, maiusculas=False):
    """
    Agrupamento de Scott & Knott (1974), Biometrics 30:507-512.
    s²_ȳ = variância de uma média = var_dif/2 (média dos pares, dados balanceados).
    """
    medias = np.asarray(medias, float)
    k = len(medias)
    ep_m = _ep_media(np.sqrt(np.maximum(var_dif, 0)), k) if k > 1 else 0.0
    s2m = (ep_m or 0.0) ** 2
    v = float(gl)

    def particiona(idx):
        idx = sorted(idx, key=lambda i: -medias[i])
        n = len(idx)
        if n < 2:
            return [idx]
        y = medias[idx]
        melhor_B, melhor_c = -1.0, None
        tot = y.sum()
        for c in range(1, n):
            T1, T2 = y[:c].sum(), y[c:].sum()
            B = T1 ** 2 / c + T2 ** 2 / (n - c) - tot ** 2 / n
            if B > melhor_B + 1e-15:
                melhor_B, melhor_c = B, c
        s0 = (np.sum((y - y.mean()) ** 2) + v * s2m) / (n + v)
        if s0 <= 0:
            return [idx]
        lam = math.pi / (2 * (math.pi - 2)) * melhor_B / s0
        crit = stats.chi2.ppf(1 - alfa, n / (math.pi - 2))
        if lam > crit:
            return particiona(idx[:melhor_c]) + particiona(idx[melhor_c:])
        return [idx]

    parts = particiona(list(range(k)))
    letras = _letras_de_particao(medias, parts, maiusculas)
    sig = np.ones((k, k), bool)
    for g in parts:
        for i in g:
            for j in g:
                sig[i, j] = False
    dif = medias[:, None] - medias[None, :]
    ep = np.sqrt(np.maximum(var_dif, 0))
    return ResultadoComparacao("scott_knott", list(grupos), medias, letras,
                               _montar_pares(grupos, medias, dif, ep, None, sig), None, gl, ep_m)


# ----------------------------------------------------------------------------
# Dunnett bilateral (todos vs. um controle)
# ----------------------------------------------------------------------------
def _dunnett_crit(m, gl, alfa, rho=0.5):
    """Valor crítico bilateral de Dunnett via t multivariada (correlação rho)."""
    if m == 1:
        return float(stats.t.ppf(1 - alfa / 2, gl))
    cov = np.full((m, m), rho)
    np.fill_diagonal(cov, 1.0)
    mvt = stats.multivariate_t(loc=np.zeros(m), shape=cov, df=min(gl, 1e4))
    rng = np.random.default_rng(20260924)

    def f(c):
        lo = np.full(m, -c)
        hi = np.full(m, c)
        return mvt.cdf(hi, lower_limit=lo, random_state=rng) - (1 - alfa)

    return float(optimize.brentq(f, 1.0, 10.0, xtol=1e-4))


def dunnett(grupos, medias, var_dif, gl, alfa=0.05, controle=None, maiusculas=False):
    medias = np.asarray(medias, float)
    grupos = list(grupos)
    k = len(grupos)
    ic = grupos.index(controle) if controle in grupos else 0
    outros = [i for i in range(k) if i != ic]
    ep = np.sqrt(np.maximum(var_dif, 0))
    # correlação entre comparações (balanceado: 0,5)
    rho = 0.5
    crit = _dunnett_crit(len(outros), gl, alfa, rho)
    pares, letras = [], [""] * k
    # p-valores ajustados via t multivariada
    cov = np.full((len(outros), len(outros)), rho)
    np.fill_diagonal(cov, 1)
    mvt = stats.multivariate_t(loc=np.zeros(len(outros)), shape=cov, df=min(gl, 1e4)) if len(outros) > 1 else None
    rng = np.random.default_rng(1)
    for i in outros:
        d = medias[i] - medias[ic]
        t = abs(d) / ep[i, ic] if ep[i, ic] > 0 else np.inf
        if mvt is None:
            p = 2 * stats.t.sf(t, gl)
        else:
            p = 1 - mvt.cdf(np.full(len(outros), t), lower_limit=np.full(len(outros), -t), random_state=rng)
        s = t > crit
        letras[i] = "*" if s else "ns"
        pares.append(dict(g1=grupos[i], g2=grupos[ic], dif=float(d), ep_dif=float(ep[i, ic]),
                          p=float(max(p, 0)), sig=bool(s)))
    letras[ic] = "(controle)"
    dms = crit * float(np.mean([ep[i, ic] for i in outros])) if outros else None
    return ResultadoComparacao("dunnett", grupos, medias, letras, pares, dms, gl,
                               _ep_media(ep, k), controle=grupos[ic])


def comparar(metodo, grupos, medias, var_dif, gl, alfa=0.05, maiusculas=False, controle=None):
    var_dif = np.asarray(var_dif, float)
    if len(grupos) == 1:
        return ResultadoComparacao(metodo, list(grupos), np.asarray(medias, float),
                                   ["A" if maiusculas else "a"], [], None, gl, None)
    if metodo == "tukey":
        return tukey(grupos, medias, var_dif, gl, alfa, maiusculas)
    if metodo == "lsd":
        return lsd(grupos, medias, var_dif, gl, alfa, maiusculas)
    if metodo == "bonferroni":
        return lsd(grupos, medias, var_dif, gl, alfa, maiusculas, bonferroni=True)
    if metodo == "snk":
        return snk(grupos, medias, var_dif, gl, alfa, maiusculas)
    if metodo == "duncan":
        return duncan(grupos, medias, var_dif, gl, alfa, maiusculas)
    if metodo == "scott_knott":
        return scott_knott(grupos, medias, var_dif, gl, alfa, maiusculas)
    if metodo == "dunnett":
        return dunnett(grupos, medias, var_dif, gl, alfa, controle, maiusculas)
    raise ValueError(f"Método desconhecido: {metodo}")
