"""
Motor de ANOVA.

Duas vias de cálculo, ambas expressas sobre o vetor de médias de células
(combinações de tratamentos) e sua matriz de covariâncias:

* Um estrato de erro (DIC, DBC, DQL, fatoriais, fatorial + adicionais):
  modelo de médias de células com efeitos de bloco/linha/coluna codificados
  por soma-zero, ajustado por mínimos quadrados. Médias ajustadas (LS means),
  testes de Wald para cada termo (= SQ tipo III), válidos também para dados
  desbalanceados.

* Vários estratos (parcelas subdivididas, sub-subdivididas, faixas):
  dados balanceados; somas de quadrados clássicas por inclusão-exclusão de
  médias marginais, cada termo testado contra o erro do seu estrato. Para
  contrastes que atravessam estratos (desdobramentos), a variância é a
  combinação linear dos quadrados médios dos estratos, com graus de
  liberdade de Satterthwaite — o procedimento de livro-texto, obtido aqui
  de forma geral pelas projeções de estrato.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from . import comparacoes as cmp
from . import pressupostos as prs
from . import regressao as reg
from .modelo import (ERRO_ROTULO, DadosPreparados, Especificacao, ErroDelineamento,
                     preparar, rotulo_transformacao, _num)


# ============================================================================
# Estruturas de resultado
# ============================================================================
@dataclass
class LinhaAnova:
    fonte: str
    gl: float
    sq: float
    qm: float | None = None
    f: float | None = None
    p: float | None = None
    tipo: str = "efeito"          # efeito | bloco | erro | total | contraste
    nivel: int = 0                # recuo na tabela
    termo: tuple | None = None
    erro: str | None = None       # nome do erro usado no teste

    def as_dict(self):
        return dict(Fonte=("    " * self.nivel) + self.fonte, GL=self.gl, SQ=self.sq, QM=self.qm, F=self.f,
                    p=self.p, tipo=self.tipo)


@dataclass
class Fatia:
    """Um conjunto de médias comparadas: níveis do fator `fator` dentro de uma
    combinação `condicao` dos fatores com os quais ele interage."""
    fator: int
    condicao: dict                    # {indice_fator: nivel}
    niveis: list
    medias: np.ndarray                # escala analisada (ajustadas)
    medias_orig: np.ndarray           # escala original (para apresentação)
    ep_modelo: np.ndarray
    ep_dados: np.ndarray
    dp_dados: np.ndarray
    n: np.ndarray
    var_dif: np.ndarray
    gl: float
    qm_erro: float
    f: float | None
    p: float | None
    gl_num: int
    comparacao: cmp.ResultadoComparacao | None = None
    regressao: "reg.ResultadoRegressao | None" = None
    polinomial: list = field(default_factory=list)  # linhas da decomposição polinomial
    obs: pd.DataFrame | None = None   # observações (x, y_orig) para gráficos


@dataclass
class ResultadoVariavel:
    variavel: str
    spec: Especificacao
    dados: DadosPreparados
    anova: list
    media_geral: float
    cv: dict
    r2: float
    residuos: np.ndarray
    ajustados: np.ndarray
    residuos_std: np.ndarray
    pressupostos: "prs.ResultadoPressupostos"
    fatias: list
    desdobramento: list
    tabelas_duplas: list
    descritiva: pd.DataFrame
    avisos: list
    transformacao: str | None
    metodo: str
    alfa: float
    extras: dict = field(default_factory=dict)

    def termo_sig(self, termo):
        for l in self.anova:
            if l.termo == termo and l.p is not None:
                return l.p < self.alfa
        return False


# ============================================================================
# Álgebra auxiliar
# ============================================================================
def _dummies(codigos: np.ndarray, k: int) -> np.ndarray:
    X = np.zeros((len(codigos), k))
    X[np.arange(len(codigos)), codigos] = 1.0
    return X


def _soma_zero(codigos: np.ndarray, k: int) -> np.ndarray:
    """Codificação soma-zero (k-1 colunas)."""
    D = _dummies(codigos, k)
    if k < 2:
        return np.zeros((len(codigos), 0))
    return D[:, :-1] - D[:, [-1]]


def _codificar(s: pd.Series, ordem=None):
    ordem = list(ordem) if ordem is not None else list(dict.fromkeys(s))
    mapa = {v: i for i, v in enumerate(ordem)}
    return s.map(mapa).to_numpy(int), ordem


def _base_contraste(n: int) -> np.ndarray:
    """Base ortonormal (n-1 × n) de contrastes."""
    C = np.eye(n) - 1.0 / n
    q, _ = np.linalg.qr(C.T)
    return q[:, : n - 1].T


def _media_grupo(v: np.ndarray, grupos: np.ndarray) -> np.ndarray:
    """Substitui cada elemento pela média do seu grupo (projeção)."""
    if grupos is None:
        return np.full_like(v, v.mean(), dtype=float)
    s = pd.DataFrame(v).groupby(grupos).transform("mean").to_numpy()
    return s.reshape(v.shape)


def _nome_termo(termo, spec):
    return " × ".join(spec.fatores[i].rotulo for i in termo)


def _termos(nf):
    out = []
    for k in range(1, nf + 1):
        out += list(itertools.combinations(range(nf), k))
    return out


# ============================================================================
# Estimadores (covariância das médias de células)
# ============================================================================
class EstimadorUmEstrato:
    def __init__(self, dados: DadosPreparados):
        d, spec = dados.d, dados.spec
        self.celulas = dados.celulas
        cod, _ = _codificar(d["CEL"], self.celulas)
        c = len(self.celulas)
        blocos = []
        Xc = _dummies(cod, c)
        nuis = {}
        if spec.base == "DBC":
            b, lv = _codificar(d["BL"], sorted(d["BL"].unique(), key=_ord))
            nuis["Blocos"] = _soma_zero(b, len(lv))
        if spec.base == "DQL":
            l_, lv = _codificar(d["LIN"], sorted(d["LIN"].unique(), key=_ord))
            c_, cv = _codificar(d["COL"], sorted(d["COL"].unique(), key=_ord))
            nuis["Linhas"] = _soma_zero(l_, len(lv))
            nuis["Colunas"] = _soma_zero(c_, len(cv))
        self.nuis_nomes = list(nuis)
        X = np.hstack([Xc] + list(nuis.values()))
        y = d["y"].to_numpy(float)
        self.X, self.y = X, y
        XtX_inv = np.linalg.pinv(X.T @ X)
        beta = XtX_inv @ X.T @ y
        self.ajustados = X @ beta
        self.residuos = y - self.ajustados
        rank = np.linalg.matrix_rank(X)
        self.gl_res = len(y) - rank
        if self.gl_res <= 0:
            raise ErroDelineamento("Graus de liberdade do resíduo ≤ 0: é preciso mais repetições.")
        self.sq_res = float(self.residuos @ self.residuos)
        self.qm_res = self.sq_res / self.gl_res
        self.m = beta[:c]
        self.V = self.qm_res * XtX_inv[:c, :c]
        # alavancas
        U, s, _ = np.linalg.svd(X, full_matrices=False)
        U = U[:, s > s.max() * 1e-10]
        self.h = np.sum(U ** 2, axis=1)
        # SQ dos efeitos de incômodo (tipo II: ajustados para tratamentos)
        self.nuis = []
        for nome, Z in nuis.items():
            outros = [Xc] + [v for k, v in nuis.items() if k != nome]
            X0 = np.hstack(outros)
            b0 = np.linalg.lstsq(X0, y, rcond=None)[0]
            sq = float(np.sum((y - X0 @ b0) ** 2) - self.sq_res)
            self.nuis.append((nome, Z.shape[1], sq))
        self.estratos = {"Resíduo": (self.qm_res, self.gl_res)}

    def cov(self, K):
        return K @ self.V @ K.T

    def gl(self, K):
        return float(self.gl_res)

    def erro_combinado(self, K):
        """QM do erro 'equivalente' e GL para o contraste K."""
        return self.qm_res, float(self.gl_res)


class EstimadorMultiEstrato:
    def __init__(self, dados: DadosPreparados, estratos_proj: dict, ms: dict):
        d = dados.d
        self.celulas = dados.celulas
        cod, _ = _codificar(d["CEL"], self.celulas)
        c = len(self.celulas)
        C = _dummies(cod, c)
        nc = C.sum(axis=0)
        C = C / nc                           # colunas = contrastes "média da célula"
        self.m = C.T @ d["y"].to_numpy(float)
        self.ms = ms                         # {nome: (qm, gl)}
        self.M = {}
        for nome, proj in estratos_proj.items():
            PC = proj(C)
            self.M[nome] = PC.T @ PC
        self.estratos = ms

    def cov(self, K):
        V = sum(self.ms[s][0] * self.M[s] for s in self.ms)
        return K @ V @ K.T

    def _pesos(self, K):
        K = np.atleast_2d(K)
        Mt = sum(self.M.values())
        KMtK = K @ Mt @ K.T
        inv = np.linalg.pinv(KMtK)
        q = np.linalg.matrix_rank(KMtK)
        a = {s: float(np.trace(K @ self.M[s] @ K.T @ inv)) / max(q, 1) for s in self.ms}
        return a

    def erro_combinado(self, K):
        a = self._pesos(K)
        qm = sum(a[s] * self.ms[s][0] for s in a)
        den = sum((a[s] * self.ms[s][0]) ** 2 / self.ms[s][1] for s in a if a[s] > 1e-10)
        gl = qm ** 2 / den if den > 0 else np.inf
        return qm, gl

    def gl(self, K):
        return self.erro_combinado(K)[1]


def _ord(v):
    try:
        return (0, float(str(v).replace(",", ".")), "")
    except ValueError:
        return (1, 0.0, str(v))


# ============================================================================
# Matrizes de contraste
# ============================================================================
def _K_termo(dados: DadosPreparados, termo) -> np.ndarray:
    blocos = []
    for i, lv in enumerate(dados.niveis):
        n = len(lv)
        blocos.append(_base_contraste(n) if i in termo else np.full((1, n), 1.0 / n))
    K = blocos[0]
    for B in blocos[1:]:
        K = np.kron(K, B)
    return _expandir(dados, K)


def _expandir(dados, Kfat):
    """Acrescenta colunas zeradas para os tratamentos adicionais."""
    na = len(dados.adicionais)
    if na == 0:
        return Kfat
    return np.hstack([Kfat, np.zeros((Kfat.shape[0], na))])


def _K_medias(dados: DadosPreparados, fator: int, condicao: dict) -> np.ndarray:
    """Linhas = níveis do fator; médias não ponderadas das células que casam
    com o nível e com a condição (média sobre os demais fatores)."""
    celulas = dados.celulas_fatoriais
    K = np.zeros((len(dados.niveis[fator]), len(celulas)))
    for r, nivel in enumerate(dados.niveis[fator]):
        idx = [j for j, cel in enumerate(celulas)
               if cel[fator] == nivel and all(cel[k] == v for k, v in condicao.items())]
        K[r, idx] = 1.0 / len(idx)
    return _expandir(dados, K)


def _wald(est, K):
    """F de Wald e GL do numerador para H0: K m = 0."""
    Km = K @ est.m
    S = est.cov(K)
    q = np.linalg.matrix_rank(S)
    F = float(Km @ np.linalg.pinv(S) @ Km) / max(q, 1)
    return F, q


# ============================================================================
# Estratos (projeções) para delineamentos multiestrato
# ============================================================================
def _chave(d, cols):
    return d[cols].astype(str).agg("|".join, axis=1).to_numpy() if cols else None


def _estratos_multiestrato(dados: DadosPreparados):
    d, spec = dados.d, dados.spec
    fk = [f"F{i}" for i in range(len(spec.fatores))]
    base_bl = spec.base == "DBC"
    G_bl = _chave(d, ["BL"]) if base_bl else None

    def proj_dif(g_hi, g_lo):
        def f(C):
            hi = _media_grupo(C, g_hi) if g_hi is not None else C
            lo = _media_grupo(C, g_lo)
            return hi - lo
        return f

    projs = {}
    if spec.estrutura == "faixas":
        iA = [i for i, f in enumerate(spec.fatores) if f.estrato == 1][0]
        iB = [i for i, f in enumerate(spec.fatores) if f.estrato == 2][0]
        G_A = _chave(d, ["BL", fk[iA]])
        G_B = _chave(d, ["BL", fk[iB]])
        projs["Erro (a)"] = proj_dif(G_A, G_bl)
        projs["Erro (b)"] = proj_dif(G_B, G_bl)

        def res(C):
            return C - _media_grupo(C, G_A) - _media_grupo(C, G_B) + _media_grupo(C, G_bl)
        projs["Erro (c)"] = res
        return projs, {"G_A": G_A, "G_B": G_B, "G_bl": G_bl}
    L = spec.n_niveis_estrato
    grupos = []
    for l in range(1, L):
        cols = ["BL"] + [fk[i] for i, f in enumerate(spec.fatores) if f.estrato <= l]
        grupos.append(_chave(d, cols))
    anterior = G_bl
    for l in range(1, L):
        projs[ERRO_ROTULO[l]] = proj_dif(grupos[l - 1], anterior)
        anterior = grupos[l - 1]
    ultimo = anterior
    projs[ERRO_ROTULO[L]] = lambda C, g=ultimo: C - _media_grupo(C, g)
    return projs, {"grupos": grupos, "G_bl": G_bl}


def _sq_marg(y, grupos):
    if grupos is None:
        return 0.0
    mu = y.mean()
    g = _media_grupo(y, grupos)
    return float(np.sum((g - mu) ** 2))


# ============================================================================
# ANOVA
# ============================================================================
def _anova_um_estrato(dados, alfa):
    est = EstimadorUmEstrato(dados)
    spec = dados.spec
    y = dados.d["y"].to_numpy(float)
    linhas = []
    for nome, gl, sq in est.nuis:
        qm = sq / gl if gl else np.nan
        F = qm / est.qm_res
        linhas.append(LinhaAnova(nome, gl, sq, qm, F, float(stats.f.sf(F, gl, est.gl_res)), tipo="bloco",
                                 erro="Resíduo"))
    nf = len(spec.fatores)
    if spec.estrutura == "fatorial_adicional":
        c = len(dados.celulas)
        Kt = _base_contraste(c)
        F, q = _wald(est, Kt)
        linhas.append(LinhaAnova("Tratamentos", q, F * q * est.qm_res, F * est.qm_res, F,
                                 float(stats.f.sf(F, q, est.gl_res)), tipo="efeito", erro="Resíduo"))
        nfc = len(dados.celulas_fatoriais)
        na = len(dados.adicionais)
        for termo in _termos(nf):
            K = _K_termo(dados, termo)
            F, q = _wald(est, K)
            linhas.append(LinhaAnova(_nome_termo(termo, spec), q, F * q * est.qm_res, F * est.qm_res, F,
                                     float(stats.f.sf(F, q, est.gl_res)), nivel=1, termo=termo, erro="Resíduo"))
        k = np.concatenate([np.full(nfc, 1.0 / nfc), np.full(na, -1.0 / na)])[None, :]
        F, q = _wald(est, k)
        rot = "Fatorial vs. adicional" if na == 1 else "Fatorial vs. adicionais"
        linhas.append(LinhaAnova(rot, 1, F * est.qm_res, F * est.qm_res, F, float(stats.f.sf(F, 1, est.gl_res)),
                                 nivel=1, tipo="contraste", termo=("fat_vs_adic",), erro="Resíduo"))
        if na > 1:
            K = np.hstack([np.zeros((na - 1, nfc)), _base_contraste(na)])
            F, q = _wald(est, K)
            linhas.append(LinhaAnova("Entre adicionais", q, F * q * est.qm_res, F * est.qm_res, F,
                                     float(stats.f.sf(F, q, est.gl_res)), nivel=1, tipo="contraste",
                                     termo=("entre_adic",), erro="Resíduo"))
    else:
        for termo in _termos(nf):
            K = _K_termo(dados, termo)
            F, q = _wald(est, K)
            linhas.append(LinhaAnova(_nome_termo(termo, spec), q, F * q * est.qm_res, F * est.qm_res, F,
                                     float(stats.f.sf(F, q, est.gl_res)), termo=termo, erro="Resíduo"))
    linhas.append(LinhaAnova("Resíduo", est.gl_res, est.sq_res, est.qm_res, tipo="erro"))
    sqt = float(np.sum((y - y.mean()) ** 2))
    linhas.append(LinhaAnova("Total", len(y) - 1, sqt, tipo="total"))
    cv = {"CV (%)": 100 * math.sqrt(est.qm_res) / abs(y.mean())}
    r2 = 1 - est.sq_res / sqt if sqt > 0 else np.nan
    return est, linhas, cv, r2, est.residuos, est.ajustados, est.h, est.qm_res


def _anova_multiestrato(dados, alfa):
    d, spec = dados.d, dados.spec
    y = d["y"].to_numpy(float)
    fk = [f"F{i}" for i in range(len(spec.fatores))]
    nf = len(spec.fatores)
    termos = _termos(nf)
    ssm = {}

    def SSM(idx_fatores, com_bloco=False):
        key = (tuple(sorted(idx_fatores)), com_bloco)
        if key not in ssm:
            cols = (["BL"] if com_bloco else []) + [fk[i] for i in sorted(idx_fatores)]
            ssm[key] = _sq_marg(y, _chave(d, cols)) if cols else 0.0
        return ssm[key]

    sq_termo = {}
    for T in termos:
        s = 0.0
        for k in range(0, len(T) + 1):
            for S in itertools.combinations(T, k):
                s += (-1) ** (len(T) - len(S)) * SSM(S)
        sq_termo[T] = s
    gl_termo = {T: int(np.prod([len(dados.niveis[i]) - 1 for i in T])) for T in termos}
    nb = d["BL"].nunique()
    dbc = spec.base == "DBC"
    sq_bl = SSM((), True) if dbc else 0.0
    sqt = float(np.sum((y - y.mean()) ** 2))

    erros = {}
    if spec.estrutura == "faixas":
        iA = [i for i, f in enumerate(spec.fatores) if f.estrato == 1][0]
        iB = [i for i, f in enumerate(spec.fatores) if f.estrato == 2][0]
        a, b = len(dados.niveis[iA]), len(dados.niveis[iB])
        erros["Erro (a)"] = (SSM((iA,), True) - sq_bl - sq_termo[(iA,)], (nb - 1) * (a - 1))
        erros["Erro (b)"] = (SSM((iB,), True) - sq_bl - sq_termo[(iB,)], (nb - 1) * (b - 1))
        estrato_termo = {(iA,): "Erro (a)", (iB,): "Erro (b)", tuple(sorted((iA, iB))): "Erro (c)"}
        L = 3
    else:
        L = spec.n_niveis_estrato
        estrato_termo = {T: ERRO_ROTULO[max(spec.fatores[i].estrato for i in T)] for T in termos}
        acum_sq, acum_gl = sq_bl, (nb - 1) if dbc else 0
        for l in range(1, L):
            fat_l = [i for i, f in enumerate(spec.fatores) if f.estrato <= l]
            sq_u = SSM(fat_l, True)
            n_units = nb * int(np.prod([len(dados.niveis[i]) for i in fat_l]))
            sq_t = sum(sq_termo[T] for T in termos if max(spec.fatores[i].estrato for i in T) <= l)
            gl_t = sum(gl_termo[T] for T in termos if max(spec.fatores[i].estrato for i in T) <= l)
            sq_e = sq_u - sq_t - (sq_bl if dbc else 0.0) - sum(erros[k][0] for k in erros)
            gl_e = (n_units - 1) - gl_t - ((nb - 1) if dbc else 0) - sum(erros[k][1] for k in erros)
            erros[ERRO_ROTULO[l]] = (sq_e, gl_e)
    sq_res = sqt - sq_bl - sum(sq_termo.values()) - sum(v[0] for v in erros.values())
    gl_res = (len(y) - 1) - ((nb - 1) if dbc else 0) - sum(gl_termo.values()) - sum(v[1] for v in erros.values())
    erros[ERRO_ROTULO[L]] = (sq_res, gl_res)
    for k, (sq, gl) in erros.items():
        if gl <= 0:
            raise ErroDelineamento(f"{k} sem graus de liberdade — verifique repetições/blocos.")
    ms = {k: (v[0] / v[1], v[1]) for k, v in erros.items()}

    linhas = []
    if dbc:
        qm_bl = sq_bl / (nb - 1)
        e1 = ms["Erro (a)"]
        Fb = qm_bl / e1[0]
        linhas.append(LinhaAnova("Blocos", nb - 1, sq_bl, qm_bl, Fb, float(stats.f.sf(Fb, nb - 1, e1[1])),
                                 tipo="bloco", erro="Erro (a)"))

    def linha_termo(T):
        e = estrato_termo[T]
        qm = sq_termo[T] / gl_termo[T]
        F = qm / ms[e][0]
        return LinhaAnova(_nome_termo(T, spec), gl_termo[T], sq_termo[T], qm, F,
                          float(stats.f.sf(F, gl_termo[T], ms[e][1])), termo=T, erro=e)

    ordem_erros = list(erros)
    for e in ordem_erros:
        for T in termos:
            if estrato_termo[T] == e:
                linhas.append(linha_termo(T))
        sq, gl = erros[e]
        linhas.append(LinhaAnova(e, gl, sq, sq / gl, tipo="erro"))
    linhas.append(LinhaAnova("Total", len(y) - 1, sqt, tipo="total"))

    projs, grupos = _estratos_multiestrato(dados)
    est = EstimadorMultiEstrato(dados, projs, ms)
    mu = abs(y.mean())
    cv = {f"CV {k.replace('Erro ', '')} (%)": 100 * math.sqrt(v[0]) / mu for k, v in ms.items()}
    # resíduos do estrato mais baixo: projeção sobre [unidades do penúltimo estrato + células]
    cod, _ = _codificar(d["CEL"], dados.celulas)
    Xc = _dummies(cod, len(dados.celulas))
    if spec.estrutura == "faixas":
        ga, _ = _codificar(pd.Series(grupos["G_A"]))
        gb, _ = _codificar(pd.Series(grupos["G_B"]))
        X = np.hstack([Xc, _dummies(ga, ga.max() + 1), _dummies(gb, gb.max() + 1)])
    else:
        gu, _ = _codificar(pd.Series(grupos["grupos"][-1]))
        X = np.hstack([Xc, _dummies(gu, gu.max() + 1)])
    U, s, _ = np.linalg.svd(X, full_matrices=False)
    U = U[:, s > s.max() * 1e-10]
    ajust = U @ (U.T @ y)
    h = np.sum(U ** 2, axis=1)
    res = y - ajust
    r2 = 1 - sq_res / sqt if sqt > 0 else np.nan
    est.estrato_termo = estrato_termo
    est.qm_res, est.gl_res = ms[ERRO_ROTULO[L]]
    est.X, est.y = X, y
    return est, linhas, cv, r2, res, ajust, h, ms[ERRO_ROTULO[L]][0]


# ============================================================================
# Análise completa de uma variável
# ============================================================================
@dataclass
class Opcoes:
    alfa: float = 0.05
    metodo: str = "tukey"
    transformacao: str | None = None
    controle: str | None = None           # para Dunnett
    modelos_regressao: list | None = None  # None = todos adequados
    comparar_quantitativos: bool = False   # também aplicar teste de médias a fatores quantitativos
    alfa_interacao: float | None = None    # por padrão = alfa


def analisar(df: pd.DataFrame, spec: Especificacao, variavel: str, opcoes: Opcoes | None = None) -> ResultadoVariavel:
    op = opcoes or Opcoes()
    alfa = op.alfa
    alfa_int = op.alfa_interacao or alfa
    dados = preparar(df, spec, variavel, op.transformacao)
    avisos = list(dados.avisos)
    if spec.multiestrato:
        est, linhas, cv, r2, res, ajust, h, qm_res = _anova_multiestrato(dados, alfa)
    else:
        est, linhas, cv, r2, res, ajust, h, qm_res = _anova_um_estrato(dados, alfa)
    d = dados.d
    y = d["y"].to_numpy(float)
    gl_res = est.gl_res
    with np.errstate(divide="ignore", invalid="ignore"):
        rstd = res / np.sqrt(qm_res * np.clip(1 - h, 1e-12, None))
    media_geral = float(d["y_orig"].mean())
    if op.transformacao:
        cv = {k + " [escala transformada]": v for k, v in cv.items()}

    # ------------------------------------------------------------ pressupostos
    Xbc = est.X
    pres = prs.avaliar(res, ajust, rstd, d["CEL"].to_numpy(), d, spec, qm_res, gl_res,
                       y_orig=d["y_orig"].to_numpy(float), X_modelo=Xbc, transformacao=op.transformacao)

    # ------------------------------------------------------------ fatias de médias
    sig = {l.termo: (l.p is not None and l.p < alfa_int) for l in linhas if l.termo}
    nf = len(spec.fatores)
    fatias = []
    for i in range(nf):
        parceiros = set()
        for T, s in sig.items():
            if s and isinstance(T[0], int) and i in T and len(T) > 1:
                parceiros |= set(T) - {i}
        parceiros = sorted(parceiros)
        combos = list(itertools.product(*[dados.niveis[j] for j in parceiros])) if parceiros else [()]
        for combo in combos:
            cond = dict(zip(parceiros, combo))
            fatias.append(_fatia(dados, est, i, cond, op, alfa))

    # desdobramento (ANOVA das fatias quando há interação)
    desdobr = []
    for fa in fatias:
        if fa.condicao:
            cond_txt = ", ".join(f"{spec.fatores[k].rotulo} = {v}" for k, v in fa.condicao.items())
            n_ = float(np.mean(fa.n))
            sq = fa.f * fa.gl_num * fa.qm_erro if fa.f is not None else np.nan
            desdobr.append(dict(Fonte=f"{spec.fatores[fa.fator].rotulo} d. {cond_txt}", GL=fa.gl_num, SQ=sq,
                                QM=sq / fa.gl_num if fa.gl_num else np.nan, F=fa.f, p=fa.p,
                                **{"QM erro": fa.qm_erro, "GL erro": fa.gl}))

    # tabelas de dupla entrada (interação dupla significativa, fatores qualitativos ou não)
    duplas = _tabelas_duplas(dados, fatias, sig, spec)

    # fatorial + adicional: comparação de todos os tratamentos e Dunnett vs adicionais
    extras = {}
    if spec.estrutura == "fatorial_adicional":
        extras.update(_extras_adicional(dados, est, op, alfa))
    elif nf == 1 and op.metodo != "dunnett" and op.controle:
        pass

    desc = _descritiva(dados)
    res_obj = ResultadoVariavel(
        variavel=variavel, spec=spec, dados=dados, anova=linhas, media_geral=media_geral, cv=cv, r2=r2,
        residuos=res, ajustados=ajust, residuos_std=rstd, pressupostos=pres, fatias=fatias,
        desdobramento=desdobr, tabelas_duplas=duplas, descritiva=desc, avisos=avisos,
        transformacao=op.transformacao, metodo=op.metodo, alfa=alfa, extras=extras)
    if op.transformacao:
        avisos.append(f"Análise na escala transformada ({rotulo_transformacao(op.transformacao)}); médias apresentadas "
                      "na escala original com as letras do teste na escala transformada.")
    return res_obj


def _obs_fatia(dados, fator, cond):
    d = dados.d
    fk = f"F{fator}"
    mask = np.ones(len(d), bool)
    if "ADIC" in d:
        mask &= ~d["ADIC"].to_numpy()
    for k, v in cond.items():
        mask &= (d[f"F{k}"] == v).to_numpy()
    sub = d.loc[mask, [fk, "y", "y_orig"]].rename(columns={fk: "nivel"})
    return sub, mask


def _fatia(dados, est, i, cond, op, alfa):
    spec = dados.spec
    niveis = dados.niveis[i]
    K = _K_medias(dados, i, cond)
    m = K @ est.m
    V = est.cov(K)
    k = len(niveis)
    var_dif = np.zeros((k, k))
    gls = []
    for a in range(k):
        for b in range(a + 1, k):
            c = K[a] - K[b]
            var_dif[a, b] = var_dif[b, a] = float(est.cov(c[None, :])[0, 0])
            gls.append(est.gl(c[None, :]))
    gl = float(np.median(gls)) if gls else float(est.gl_res)
    Kc = _base_contraste(k) @ K
    F, q = _wald(est, Kc)
    qm_e, gl_e = est.erro_combinado(Kc)
    p = float(stats.f.sf(F, q, gl_e))
    sub, mask = _obs_fatia(dados, i, cond)
    g = sub.groupby("nivel")
    n = g.size().reindex(niveis).fillna(0).to_numpy(float)
    dp = g["y_orig"].std(ddof=1).reindex(niveis).to_numpy(float)
    ep_d = dp / np.sqrt(n)
    med_orig = g["y_orig"].mean().reindex(niveis).to_numpy(float) if op.transformacao else m
    fa = Fatia(fator=i, condicao=cond, niveis=niveis, medias=m, medias_orig=med_orig,
               ep_modelo=np.sqrt(np.diag(V)), ep_dados=ep_d, dp_dados=dp, n=n, var_dif=var_dif, gl=gl_e,
               qm_erro=qm_e, f=F, p=p, gl_num=q, obs=sub.assign(_linha=dados.d.loc[mask, "_linha"].to_numpy()))
    f = spec.fatores[i]
    quant = f.quantitativo and k >= 3
    if (not quant) or op.comparar_quantitativos:
        metodo = op.metodo
        controle = op.controle if (metodo == "dunnett" and op.controle in niveis) else None
        if metodo == "dunnett" and controle is None:
            controle = niveis[0]
        fa.comparacao = cmp.comparar(metodo, niveis, m, var_dif, gl, alfa, controle=controle)
    if quant:
        x = dados.valores_quant(i)
        # decomposição polinomial (contrastes ortogonais) dentro da ANOVA
        n_med = float(np.mean(n))
        P = _polinomios_ortogonais(x, min(3, k - 1))
        linhas = []
        sq_tot = 0.0
        for grau in range(P.shape[0]):
            c = P[grau] @ K
            Fj, _ = _wald(est, c[None, :])
            cm = float(P[grau] @ m)
            sq = n_med * cm ** 2 / float(P[grau] @ P[grau])
            qm_j, gl_j = est.erro_combinado(c[None, :])
            sq_tot += sq
            linhas.append(dict(Fonte=["Linear", "Quadrático", "Cúbico"][grau], GL=1, SQ=sq, QM=sq, F=Fj,
                               p=float(stats.f.sf(Fj, 1, gl_j))))
        sq_fat = F * q * qm_e
        gl_desv = k - 1 - P.shape[0]
        if gl_desv > 0:
            sq_d = max(sq_fat - sq_tot, 0.0)
            Fd = (sq_d / gl_desv) / qm_e
            linhas.append(dict(Fonte="Desvios da regressão", GL=gl_desv, SQ=sq_d, QM=sq_d / gl_desv, F=Fd,
                               p=float(stats.f.sf(Fd, gl_desv, gl_e))))
        fa.polinomial = linhas
        # ajuste e ranqueamento de modelos (na escala original quando há transformação)
        yb = fa.medias_orig
        e_sub = None
        ss_puro = float(np.sum((sub["y_orig"] - sub.groupby("nivel")["y_orig"].transform("mean")) ** 2))
        fa.regressao = reg.ajustar_modelos(x, yb, n, qm_e if not op.transformacao else None, gl_e, ss_puro,
                                           alfa=alfa, modelos=op.modelos_regressao,
                                           obs_x=np.array([_num(v) for v in sub["nivel"]]),
                                           obs_y=sub["y_orig"].to_numpy(float))
    return fa


def _polinomios_ortogonais(x, grau):
    x = np.asarray(x, float)
    X = np.vander(x - x.mean(), grau + 1, increasing=True)
    q, _ = np.linalg.qr(X)
    P = q[:, 1:grau + 1].T
    # sinal: coeficiente positivo associado a x^grau
    for g in range(P.shape[0]):
        if np.polyfit(x, P[g], g + 1)[0] < 0:
            P[g] = -P[g]
    return P


def _tabelas_duplas(dados, fatias, sig, spec):
    out = []
    for T, s in sig.items():
        if not s or not isinstance(T[0], int) or len(T) != 2:
            continue
        a, b = T
        # só monta quando não há interação tripla significativa envolvendo a e b
        if any(sig.get(U) for U in sig if isinstance(U[0], int) and len(U) > 2 and set(T) <= set(U)):
            continue
        fa_a = {tuple(f.condicao.items()): f for f in fatias if f.fator == a and set(f.condicao) == {b}}
        fa_b = {tuple(f.condicao.items()): f for f in fatias if f.fator == b and set(f.condicao) == {a}}
        if not fa_a or not fa_b:
            continue
        la, lb = dados.niveis[a], dados.niveis[b]
        med = pd.DataFrame(index=la, columns=lb, dtype=float)
        ep = pd.DataFrame(index=la, columns=lb, dtype=float)
        let = pd.DataFrame("", index=la, columns=lb)
        for nb_ in lb:
            f = fa_a.get(((b, nb_),))
            for r, na_ in enumerate(la):
                med.loc[na_, nb_] = f.medias_orig[r]
                ep.loc[na_, nb_] = f.ep_dados[r]
                if f.comparacao:
                    let.loc[na_, nb_] = f.comparacao.letras[r]
        for na_ in la:
            f = fa_b.get(((a, na_),))
            for r, nb_ in enumerate(lb):
                if f.comparacao:
                    let.loc[na_, nb_] = let.loc[na_, nb_] + " " + f.comparacao.letras[r].upper()
        out.append(dict(fatores=(a, b), medias=med, ep=ep, letras=let,
                        linhas=spec.fatores[a].rotulo, colunas=spec.fatores[b].rotulo,
                        quant=(spec.fatores[a].quantitativo, spec.fatores[b].quantitativo)))
    return out


def _extras_adicional(dados, est, op, alfa):
    trat = dados.celulas
    c = len(trat)
    m = est.m
    V = est.cov(np.eye(c))
    var_dif = np.diag(V)[:, None] + np.diag(V)[None, :] - 2 * V
    gl = est.gl_res
    metodo = op.metodo if op.metodo != "dunnett" else "tukey"
    todos = cmp.comparar(metodo, trat, m, var_dif, gl, alfa)
    d = dados.d
    g = d.groupby("CEL")["y_orig"]
    medias_orig = g.mean().reindex(trat).to_numpy() if op.transformacao else m
    ep = (g.std(ddof=1) / np.sqrt(g.size())).reindex(trat).to_numpy()
    dun = []
    for ad in dados.adicionais:
        dun.append(cmp.dunnett(trat, m, var_dif, gl, alfa, controle=ad))
    return {"todos_tratamentos": dict(comparacao=todos, medias_orig=medias_orig, ep=ep,
                                      n=g.size().reindex(trat).to_numpy()),
            "dunnett_adicionais": dun}


def _descritiva(dados):
    d = dados.d
    g = d.groupby("CEL")["y_orig"]
    t = pd.DataFrame({"n": g.size(), "Média": g.mean(), "DP": g.std(ddof=1), "Mín.": g.min(), "Máx.": g.max()})
    t["EP"] = t["DP"] / np.sqrt(t["n"])
    t["CV (%)"] = 100 * t["DP"] / t["Média"].abs()
    t = t.reindex(dados.celulas)
    t.index.name = "Tratamento"
    return t[["n", "Média", "DP", "EP", "Mín.", "Máx.", "CV (%)"]]
