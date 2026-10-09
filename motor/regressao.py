"""
Regressão para fatores quantitativos (doses, épocas, profundidades…).

Os modelos são ajustados às médias de cada nível, ponderadas pelo número de
observações, e testados com o quadrado médio do erro experimental — a forma
usual em Ciências Agrárias. O ranqueamento combina:

1. adequação: convergência, falta de ajuste não significativa e parâmetros
   de forma significativos;
2. AICc calculado no nível das observações (SQ desvios + SQ erro puro), que
   penaliza parâmetros extras de forma coerente entre modelos lineares e
   não lineares; ΔAICc e pesos de Akaike acompanham a tabela.
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field

import numpy as np
from scipy import optimize, stats

# ============================================================================
# Catálogo de modelos
# ============================================================================


@dataclass
class ModeloDef:
    codigo: str
    nome: str
    nome_en: str
    params: list
    chave: list                 # parâmetros de forma cujo teste t importa
    linear: bool                # linear nos parâmetros?
    exige_positivo: bool = False
    familia: str = ""


CATALOGO = {
    # ---- resposta a doses (padrão)
    "linear": ModeloDef("linear", "Linear", "Linear", ["a", "b"], ["b"], True, familia="dose"),
    "quadratico": ModeloDef("quadratico", "Quadrático", "Quadratic", ["a", "b", "c"], ["c"], True, familia="dose"),
    "cubico": ModeloDef("cubico", "Cúbico", "Cubic", ["a", "b", "c", "d"], ["d"], True, familia="dose"),
    "raiz": ModeloDef("raiz", "Raiz quadrada", "Square-root", ["a", "b", "c"], ["b", "c"], True, familia="dose"),
    "log": ModeloDef("log", "Logarítmico", "Logarithmic", ["a", "b"], ["b"], True, familia="dose"),
    "mitscherlich": ModeloDef("mitscherlich", "Exponencial assintótico (Mitscherlich)", "Asymptotic exponential (Mitscherlich)",
                              ["a", "b", "c"], ["b", "c"], False, familia="dose"),
    "linear_plato": ModeloDef("linear_plato", "Linear-platô", "Linear-plateau", ["a", "b", "x₀"], ["b"], False, familia="dose"),
    "quadratico_plato": ModeloDef("quadratico_plato", "Quadrático-platô", "Quadratic-plateau", ["a", "b", "c"], ["c"], False,
                                  familia="dose"),
    "exponencial": ModeloDef("exponencial", "Exponencial", "Exponential", ["a", "b"], ["b"], False, familia="dose"),
    "potencia": ModeloDef("potencia", "Potência", "Power", ["a", "b"], ["b"], False, exige_positivo=True, familia="dose"),
    "michaelis": ModeloDef("michaelis", "Hiperbólico (Michaelis-Menten)", "Hyperbolic (Michaelis-Menten)",
                           ["y₀", "a", "b"], ["a"], False, familia="dose"),
    # ---- crescimento / acúmulo
    "logistico": ModeloDef("logistico", "Logístico (3P)", "Logistic (3P)", ["a", "b", "c"], ["b"], False, familia="crescimento"),
    "gompertz": ModeloDef("gompertz", "Gompertz", "Gompertz", ["a", "b", "c"], ["b", "c"], False, familia="crescimento"),
    "weibull": ModeloDef("weibull", "Weibull (3P)", "Weibull (3P)", ["a", "b", "c"], ["b", "c"], False, familia="crescimento"),
    # ---- isotermas de adsorção (x = concentração de equilíbrio; y = quantidade adsorvida)
    "langmuir": ModeloDef("langmuir", "Langmuir", "Langmuir", ["Qmáx", "K"], ["Qmáx", "K"], False, familia="adsorcao"),
    "freundlich": ModeloDef("freundlich", "Freundlich", "Freundlich", ["Kf", "1/n"], ["Kf", "1/n"], False,
                            familia="adsorcao"),
    "temkin": ModeloDef("temkin", "Temkin", "Temkin", ["B", "A"], ["B"], False, exige_positivo=True, familia="adsorcao"),
    "sips": ModeloDef("sips", "Sips (Langmuir-Freundlich)", "Sips (Langmuir-Freundlich)", ["Qmáx", "K", "n"],
                      ["Qmáx", "K"], False, familia="adsorcao"),
    # ---- cinéticas de liberação, sorção e mineralização (x = tempo)
    "primeira_ordem": ModeloDef("primeira_ordem", "Primeira ordem (Stanford & Smith; pseudo-1ª ordem)",
                                "First order (Stanford & Smith; pseudo-first order)", ["q₀", "k"], ["q₀", "k"], False,
                                familia="cinetica"),
    "segunda_ordem": ModeloDef("segunda_ordem", "Pseudo-segunda ordem", "Pseudo-second order", ["qₑ", "k₂"], ["qₑ", "k₂"],
                               False, familia="cinetica"),
    "elovich": ModeloDef("elovich", "Elovich", "Elovich", ["α", "β"], ["α", "β"], False, familia="cinetica"),
    "parabolica": ModeloDef("parabolica", "Difusão parabólica", "Parabolic diffusion", ["a", "b"], ["b"], True,
                            familia="cinetica"),
    "dois_compart": ModeloDef("dois_compart", "Dois compartimentos (1ª ordem dupla)", "Two-pool first order",
                              ["C₁", "k₁", "C₂", "k₂"], ["C₁", "C₂"], False, familia="cinetica"),
}

FAMILIAS = {
    "dose": "Resposta a doses",
    "crescimento": "Crescimento e acúmulo",
    "adsorcao": "Isotermas de adsorção",
    "cinetica": "Cinéticas (liberação, sorção, mineralização)",
}

PADRAO = [c for c, m in CATALOGO.items() if m.familia == "dose"] + ["logistico"]


def modelos_da_familia(familias):
    return [c for c, m in CATALOGO.items() if m.familia in familias]


def _f(codigo, x, p, desloc_log=0.0):
    x = np.asarray(x, float)
    if codigo == "linear":
        return p[0] + p[1] * x
    if codigo == "quadratico":
        return p[0] + p[1] * x + p[2] * x ** 2
    if codigo == "cubico":
        return p[0] + p[1] * x + p[2] * x ** 2 + p[3] * x ** 3
    if codigo == "raiz":
        return p[0] + p[1] * np.sqrt(np.clip(x, 0, None)) + p[2] * x
    if codigo == "log":
        return p[0] + p[1] * np.log(x + desloc_log)
    if codigo == "mitscherlich":
        return p[0] - p[1] * np.exp(-p[2] * x)
    if codigo == "linear_plato":
        return p[0] + p[1] * np.minimum(x, p[2])
    if codigo == "quadratico_plato":
        a, b, c = p
        x0 = -b / (2 * c) if c != 0 else np.inf
        xx = np.minimum(x, x0) if c < 0 else x
        return a + b * xx + c * xx ** 2
    if codigo == "exponencial":
        return p[0] * np.exp(np.clip(p[1] * x, -700, 700))
    if codigo == "potencia":
        return p[0] * np.power(np.clip(x, 1e-300, None), p[1])
    if codigo == "michaelis":
        return p[0] + p[1] * x / (p[2] + x)
    if codigo == "logistico":
        return p[0] / (1 + np.exp(np.clip(-p[1] * (x - p[2]), -700, 700)))
    if codigo == "gompertz":
        return p[0] * np.exp(-p[1] * np.exp(np.clip(-p[2] * x, -700, 700)))
    if codigo == "weibull":
        return p[0] * (1 - np.exp(-np.power(np.clip(x, 0, None) / abs(p[1]), p[2])))
    if codigo == "langmuir":
        return p[0] * p[1] * x / (1 + p[1] * x)
    if codigo == "freundlich":
        return p[0] * np.power(np.clip(x, 0, None), p[1])
    if codigo == "temkin":
        return p[0] * np.log(np.clip(p[1] * x, 1e-300, None))
    if codigo == "sips":
        kx = np.power(np.clip(p[1] * x, 0, None), p[2])
        return p[0] * kx / (1 + kx)
    if codigo == "primeira_ordem":
        return p[0] * (1 - np.exp(-p[1] * x))
    if codigo == "segunda_ordem":
        return p[0] ** 2 * p[1] * x / (1 + p[0] * p[1] * x)
    if codigo == "elovich":
        return (1 / p[1]) * np.log(np.clip(1 + p[0] * p[1] * x, 1e-300, None))
    if codigo == "parabolica":
        return p[0] + p[1] * np.sqrt(np.clip(x, 0, None))
    if codigo == "dois_compart":
        return p[0] * (1 - np.exp(-p[1] * x)) + p[2] * (1 - np.exp(-p[3] * x))
    raise ValueError(codigo)


def _X_linear(codigo, x, desloc_log=0.0):
    x = np.asarray(x, float)
    um = np.ones_like(x)
    if codigo == "linear":
        return np.column_stack([um, x])
    if codigo == "quadratico":
        return np.column_stack([um, x, x ** 2])
    if codigo == "cubico":
        return np.column_stack([um, x, x ** 2, x ** 3])
    if codigo == "raiz":
        return np.column_stack([um, np.sqrt(x), x])
    if codigo == "log":
        return np.column_stack([um, np.log(x + desloc_log)])
    if codigo == "parabolica":
        return np.column_stack([um, np.sqrt(np.clip(x, 0, None))])
    raise ValueError(codigo)


# ============================================================================
# Resultado
# ============================================================================
@dataclass
class AjusteModelo:
    codigo: str
    nome: str
    params: np.ndarray
    ep: np.ndarray
    p_params: np.ndarray
    sq_desvio: float
    r2: float
    r2_aj: float | None
    rmse: float
    aicc: float
    bic: float
    gl_desvio: int
    f_falta: float | None
    p_falta: float | None
    adequado: bool
    convergiu: bool
    motivo: str = ""
    desloc_log: float = 0.0
    pontos: dict = field(default_factory=dict)
    delta_aicc: float | None = None
    peso: float | None = None
    rank: int | None = None
    cov: np.ndarray | None = None
    gl_erro: float | None = None

    def prever(self, x):
        return _f(self.codigo, x, self.params, self.desloc_log)

    def equacao(self, idioma="pt", digitos=4):
        return equacao(self, idioma, digitos)

    def falta_ajuste(self, idioma="pt", alfa=0.05):
        """Veredito legível do teste de falta de ajuste (p alto = bom ajuste)."""
        if self.p_falta is None or not np.isfinite(self.p_falta):
            return "sem GL para testar" if idioma == "pt" else "no df to test"
        if self.p_falta < 0.001:
            ptxt = "p < 0,001" if idioma == "pt" else "P < 0.001"
        else:
            ptxt = ("p = " if idioma == "pt" else "P = ") + fmt_num(self.p_falta, 2, idioma)
        if self.p_falta >= alfa:
            return f"não detectada ✓ ({ptxt})" if idioma == "pt" else f"not detected ✓ ({ptxt})"
        return f"detectada ✗ ({ptxt})" if idioma == "pt" else f"detected ✗ ({ptxt})"


@dataclass
class ResultadoRegressao:
    x: np.ndarray
    medias: np.ndarray
    n: np.ndarray
    ajustes: list
    melhor: AjusteModelo | None
    qm_erro: float
    gl_erro: float
    obs_x: np.ndarray | None = None
    obs_y: np.ndarray | None = None
    nota: str = ""


# ============================================================================
# Ajuste
# ============================================================================
def ajustar_modelos(x, medias, n, qm_erro, gl_erro, ss_puro, alfa=0.05, modelos=None, obs_x=None, obs_y=None):
    x = np.asarray(x, float)
    ybar = np.asarray(medias, float)
    n = np.asarray(n, float)
    k = len(x)
    n_obs = float(n.sum())
    nota = ""
    if qm_erro is None or not np.isfinite(qm_erro):
        gl_puro = n_obs - k
        qm_erro = ss_puro / gl_puro if gl_puro > 0 else np.nan
        gl_erro = gl_puro
        nota = "Erro estimado pela variação entre repetições (escala original)."
    modelos = modelos or PADRAO
    ybw = np.sum(n * ybar) / n_obs
    sq_trat = float(np.sum(n * (ybar - ybw) ** 2))
    ajustes = []
    for cod in modelos:
        md = CATALOGO[cod]
        p = len(md.params)
        if k < p:
            continue
        if md.exige_positivo and np.any(x <= 0):
            continue
        if cod == "log" and np.any(x < 0):
            continue
        if cod == "cubico" and k < 5:
            continue
        if not md.linear and k < p + 1:
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                aj = _ajustar(cod, x, ybar, n, qm_erro, gl_erro, ss_puro, sq_trat, n_obs, alfa)
            if aj is not None:
                ajustes.append(aj)
        except Exception as e:  # pragma: no cover - ajuste robusto
            continue
    # ranqueamento
    conv = [a for a in ajustes if a.convergiu and np.isfinite(a.aicc)]
    if conv:
        amin = min(a.aicc for a in conv)
        w = np.array([math.exp(-0.5 * (a.aicc - amin)) for a in conv])
        w = w / w.sum()
        for a, wi in zip(conv, w):
            a.delta_aicc = a.aicc - amin
            a.peso = float(wi)
    ajustes.sort(key=lambda a: (not a.convergiu, not a.adequado, a.aicc if np.isfinite(a.aicc) else np.inf))
    for i, a in enumerate(ajustes):
        a.rank = i + 1
    melhor = next((a for a in ajustes if a.adequado), None)
    if melhor is None and conv:
        melhor = ajustes[0]
        nota = (nota + " " if nota else "") + "Nenhum modelo atendeu a todos os critérios; indicado o de menor AICc."
    return ResultadoRegressao(x, ybar, n, ajustes, melhor, qm_erro, gl_erro, obs_x, obs_y, nota.strip())


def _ajustar(cod, x, ybar, n, qm, gl, ss_puro, sq_trat, n_obs, alfa):
    md = CATALOGO[cod]
    p = len(md.params)
    k = len(x)
    W = n
    desloc = 0.0
    if cod == "log":
        desloc = 0.0 if np.all(x > 0) else 1.0
    convergiu = True
    if md.linear:
        X = _X_linear(cod, x, desloc)
        sw = np.sqrt(W)
        theta, *_ = np.linalg.lstsq(X * sw[:, None], ybar * sw, rcond=None)
        J = X
    else:
        theta, J, convergiu = _ajustar_nl(cod, x, ybar, W)
        if theta is None:
            return None
    pred = _f(cod, x, theta, desloc)
    sq_d = float(np.sum(W * (ybar - pred) ** 2))
    gl_d = k - p
    r2 = 1 - sq_d / sq_trat if sq_trat > 0 else np.nan
    r2_aj = 1 - (1 - r2) * (k - 1) / (k - p) if k > p else None
    rmse = math.sqrt(sq_d / n_obs)
    # erro-padrão dos parâmetros
    JtWJ = J.T @ (J * W[:, None])
    try:
        cov = qm * np.linalg.inv(JtWJ)
        ep = np.sqrt(np.clip(np.diag(cov), 0, None))
    except np.linalg.LinAlgError:
        ep = np.full(p, np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        tval = theta / ep
    p_par = 2 * stats.t.sf(np.abs(tval), gl)
    if gl_d > 0 and np.isfinite(qm) and qm > 0:
        F = (sq_d / gl_d) / qm
        p_f = float(stats.f.sf(F, gl_d, gl))
    else:
        F, p_f = None, None
    rss_obs = sq_d + ss_puro
    Kp = p + 1
    if rss_obs > 0 and n_obs - Kp - 1 > 0:
        aicc = n_obs * math.log(rss_obs / n_obs) + 2 * Kp + 2 * Kp * (Kp + 1) / (n_obs - Kp - 1)
        bic = n_obs * math.log(rss_obs / n_obs) + Kp * math.log(n_obs)
    else:
        aicc = bic = np.inf
    idx_chave = [md.params.index(c) for c in md.chave]
    chave_sig = all(np.isfinite(p_par[i]) and p_par[i] < alfa for i in idx_chave)
    falta_ok = (p_f is None) or (p_f >= alfa)
    motivos = []
    if not convergiu:
        motivos.append("não convergiu")
    if not falta_ok:
        motivos.append("falta de ajuste significativa")
    if not chave_sig:
        motivos.append("parâmetro(s) de forma não significativo(s)")
    plaus, mot_p = _plausivel(cod, theta, x)
    if not plaus:
        motivos.append(mot_p)
    aj = AjusteModelo(cod, md.nome, np.asarray(theta, float), ep, p_par, sq_d, r2, r2_aj, rmse, aicc, bic, gl_d, F,
                      p_f, convergiu and falta_ok and chave_sig and plaus, convergiu, "; ".join(motivos), desloc)
    aj.pontos = pontos_notaveis(aj, x)
    try:
        aj.cov = cov
    except NameError:
        aj.cov = None
    aj.gl_erro = gl
    return aj


def _plausivel(cod, t, x):
    xmin, xmax = x.min(), x.max()
    if cod == "linear_plato":
        if not (xmin < t[2] < xmax):
            return False, "junção fora do intervalo"
    if cod == "quadratico_plato":
        if t[2] >= 0:
            return False, "sem platô (c ≥ 0)"
        x0 = -t[1] / (2 * t[2])
        if not (xmin < x0 < xmax):
            return False, "platô fora do intervalo"
    if cod == "mitscherlich" and t[2] <= 0:
        return False, "taxa ≤ 0"
    if cod == "michaelis" and t[2] <= 0:
        return False, "constante ≤ 0"
    if cod == "dois_compart" and t[1] < t[3]:
        # ordena: compartimento 1 = lábil (k maior) — reordenação é feita em pontos_notaveis
        pass
    if cod == "temkin" and t[1] <= 0:
        return False, "A ≤ 0"
    if cod == "logistico" and not (xmin - (xmax - xmin) < t[2] < xmax + (xmax - xmin)):
        return False, "inflexão fora do domínio"
    return True, ""


def _jac(cod, x, t, h=1e-6):
    J = np.zeros((len(x), len(t)))
    for j in range(len(t)):
        dt = h * max(1.0, abs(t[j]))
        tp, tm = np.array(t, float), np.array(t, float)
        tp[j] += dt
        tm[j] -= dt
        J[:, j] = (_f(cod, x, tp) - _f(cod, x, tm)) / (2 * dt)
    return J


_INF = np.inf
LIMITES = {   # (inferiores, superiores) — garantem parâmetros com sentido físico
    "langmuir": ([0, 0], [_INF, _INF]),
    "sips": ([0, 0, 0.05], [_INF, _INF, 10]),
    "freundlich": ([0, 0], [_INF, 5]),
    "primeira_ordem": ([-_INF, 0], [_INF, _INF]),
    "segunda_ordem": ([0, 0], [_INF, _INF]),
    "elovich": ([0, 0], [_INF, _INF]),
    "dois_compart": ([0, 0, 0, 0], [_INF, _INF, _INF, _INF]),
    "weibull": ([-_INF, 1e-12, 0.05], [_INF, _INF, 20]),
    "gompertz": ([-_INF, 0, 0], [_INF, _INF, _INF]),
}


def _ajustar_nl(cod, x, y, W):
    sw = np.sqrt(W)
    xr = max(x.max() - x.min(), 1e-9)
    yr = max(y.max() - y.min(), abs(y.mean()) * 0.1, 1e-9)
    starts = []
    if cod == "mitscherlich":
        for c in (0.3, 1, 3, 10):
            for s in (1, -1):
                a = y[np.argmax(x)] + s * 0.1 * yr if s > 0 else y[np.argmax(x)] - 0.1 * yr
                starts.append([a, a - y[np.argmin(x)], c / xr])
    elif cod == "linear_plato":
        best = None
        for x0 in np.linspace(x.min() + 0.05 * xr, x.max() - 0.05 * xr, 60):
            X = np.column_stack([np.ones_like(x), np.minimum(x, x0)])
            th, *_ = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)
            s = np.sum(W * (y - X @ th) ** 2)
            if best is None or s < best[0]:
                best = (s, [th[0], th[1], x0])
        starts.append(best[1])
    elif cod == "quadratico_plato":
        X = np.column_stack([np.ones_like(x), x, x ** 2])
        th, *_ = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)
        starts.append(list(th))
        for x0 in np.linspace(x.min() + 0.2 * xr, x.max() - 0.1 * xr, 6):
            # parábola com vértice em x0
            Xq = np.column_stack([np.ones_like(x), np.minimum(x, x0) * (2 * x0) - np.minimum(x, x0) ** 2])
            tq, *_ = np.linalg.lstsq(Xq * sw[:, None], y * sw, rcond=None)
            # y = a + g(2x0 x - x²) → b = 2 g x0, c = -g
            starts.append([tq[0], 2 * tq[1] * x0, -tq[1]])
    elif cod == "exponencial":
        if np.all(y > 0):
            b, la = np.polyfit(x, np.log(y), 1, w=sw)
            starts.append([math.exp(la), b])
        starts.append([y.mean(), 0.0])
    elif cod == "potencia":
        if np.all(y > 0):
            b, la = np.polyfit(np.log(x), np.log(y), 1, w=sw)
            starts.append([math.exp(la), b])
        starts.append([y.mean(), 0.1])
    elif cod == "michaelis":
        y0 = y[np.argmin(x)]
        for bm in (0.1, 0.5, 1.0):
            for s in (1, -1):
                starts.append([y0, s * 1.2 * yr, bm * xr + 1e-6])
    elif cod == "logistico":
        for c in (0.3, 0.5, 0.7):
            starts.append([y.max() * 1.05, 4 / xr, x.min() + c * xr])
            starts.append([y.max() * 1.05, -4 / xr, x.min() + c * xr])
    elif cod == "gompertz":
        for c in (1, 3, 8):
            for b in (1, 3, 10):
                starts.append([y.max() * 1.05, b, c / xr])
    elif cod == "weibull":
        for b in (0.3, 0.6, 1.0):
            for c in (0.8, 1.5, 3.0):
                starts.append([y.max() * 1.05, b * xr, c])
    elif cod in ("langmuir", "sips"):
        for k in (0.1, 1, 10, 100):
            st0 = [max(y.max(), 1e-9) * 1.2, k / max(x.max(), 1e-9)]
            starts.append(st0 + ([1.0] if cod == "sips" else []))
            if cod == "sips":
                starts.append(st0 + [0.6])
    elif cod == "freundlich":
        pos = (x > 0) & (y > 0)
        if pos.sum() >= 2:
            b, la = np.polyfit(np.log(x[pos]), np.log(y[pos]), 1)
            starts.append([math.exp(la), b])
        starts.append([max(y.max(), 1e-9) / max(x.max(), 1e-9) ** 0.5, 0.5])
    elif cod == "temkin":
        b, a = np.polyfit(np.log(x), y, 1, w=sw)
        starts.append([b, math.exp(np.clip(a / b, -50, 50)) if b != 0 else 1.0])
    elif cod in ("primeira_ordem", "segunda_ordem"):
        for k in (0.3, 1, 3, 10):
            q = max(y.max(), 1e-9) * 1.1
            starts.append([q, k / xr] if cod == "primeira_ordem" else [q, k / (xr * q)])
    elif cod == "elovich":
        for a in (0.1, 1, 10, 100):
            for b in (0.1, 1, 10):
                starts.append([a * max(y.max(), 1e-9) / xr, b / max(y.max(), 1e-9)])
    elif cod == "dois_compart":
        q = max(y.max(), 1e-9)
        for f in (0.2, 0.4):
            for kr in (10, 30):
                starts.append([f * q, kr / xr, (1 - f) * q * 1.2, 0.5 / xr])
    best = None

    limites = LIMITES.get(cod)

    def resid(t):
        return sw * (y - _f(cod, x, t))

    for s0 in starts:
        s0 = np.asarray(s0, float)
        try:
            if limites is not None:
                lo, hi = np.array(limites[0], float), np.array(limites[1], float)
                s0 = np.clip(s0, lo + 1e-12, hi - 1e-12)
                r = optimize.least_squares(resid, s0, bounds=(lo, hi), max_nfev=8000)
            else:
                r = optimize.least_squares(resid, s0, method="lm", max_nfev=5000)
        except Exception:
            try:
                r = optimize.least_squares(resid, s0, max_nfev=5000)
            except Exception:
                continue
        if not np.all(np.isfinite(r.x)):
            continue
        sse = float(np.sum(r.fun ** 2))
        if best is None or sse < best[0] - 1e-12:
            best = (sse, r)
    if best is None:
        return None, None, False
    r = best[1]
    J = _jac(cod, x, r.x)
    return r.x, J, bool(r.success)


# ============================================================================
# Pontos notáveis e equações
# ============================================================================
def pontos_notaveis(aj: AjusteModelo, x):
    t = aj.params
    xmin, xmax = float(np.min(x)), float(np.max(x))
    pts = {}
    c = aj.codigo
    if c == "quadratico" and t[2] != 0:
        xv = -t[1] / (2 * t[2])
        yv = t[0] - t[1] ** 2 / (4 * t[2])
        tipo = "máximo" if t[2] < 0 else "mínimo"
        pts[f"x no ponto de {tipo}"] = xv
        pts[f"y no ponto de {tipo}"] = yv
        pts["dentro do intervalo estudado"] = bool(xmin <= xv <= xmax)
    elif c == "linear_plato":
        pts["x na junção (início do platô)"] = t[2]
        pts["y do platô"] = t[0] + t[1] * t[2]
    elif c == "quadratico_plato" and t[2] < 0:
        x0 = -t[1] / (2 * t[2])
        pts["x na junção (início do platô)"] = x0
        pts["y do platô"] = t[0] - t[1] ** 2 / (4 * t[2])
    elif c == "mitscherlich" and t[2] > 0:
        pts["assíntota (y máximo)"] = t[0]
        pts["y em x = 0"] = t[0] - t[1]
        pts["x para 90% do máximo incremento"] = math.log(10) / t[2]
        pts["x para 95% do máximo incremento"] = math.log(20) / t[2]
    elif c == "raiz" and t[2] != 0 and t[1] * t[2] < 0:
        xv = (t[1] / (2 * t[2])) ** 2
        pts["x no ponto de " + ("máximo" if t[2] < 0 else "mínimo")] = xv
        pts["y no ponto de " + ("máximo" if t[2] < 0 else "mínimo")] = float(_f("raiz", xv, t))
    elif c == "cubico":
        raizes = np.roots([3 * t[3], 2 * t[2], t[1]])
        for rz in raizes:
            if np.isreal(rz) and xmin <= rz.real <= xmax:
                seg = 6 * t[3] * rz.real + 2 * t[2]
                pts[f"x no {'máximo' if seg < 0 else 'mínimo'} local"] = float(rz.real)
    elif c == "michaelis":
        pts["incremento assintótico (a)"] = t[1]
        pts["x para 50% do incremento (b)"] = t[2]
    elif c == "logistico":
        pts["assíntota (a)"] = t[0]
        pts["x no ponto de inflexão (c)"] = t[2]
    elif c == "gompertz" and t[1] > 0 and t[2] > 0:
        pts["assíntota (a)"] = t[0]
        pts["x no ponto de inflexão"] = math.log(t[1]) / t[2]
        pts["y no ponto de inflexão"] = t[0] / math.e
    elif c == "weibull":
        pts["assíntota (a)"] = t[0]
        pts["escala (b)"] = abs(t[1])
        pts["forma (c)"] = t[2]
        pts["x para 50% da assíntota"] = abs(t[1]) * math.log(2) ** (1 / t[2]) if t[2] > 0 else np.nan
    elif c == "langmuir" and t[1] > 0:
        pts["capacidade máxima de adsorção (Qmáx)"] = t[0]
        pts["constante de afinidade (K)"] = t[1]
        pts["x para 50% de Qmáx (1/K)"] = 1 / t[1]
    elif c == "freundlich":
        pts["Kf"] = t[0]
        pts["1/n (heterogeneidade)"] = t[1]
    elif c == "sips":
        pts["capacidade máxima de adsorção (Qmáx)"] = t[0]
        pts["K"] = t[1]
        pts["n (heterogeneidade)"] = t[2]
    elif c == "temkin":
        pts["B (relacionado ao calor de adsorção)"] = t[0]
        pts["A (constante de ligação)"] = t[1]
    elif c == "primeira_ordem" and t[1] > 0:
        pts["potencial (q₀ ou N₀)"] = t[0]
        pts["k (taxa)"] = t[1]
        pts["meia-vida (ln 2/k)"] = math.log(2) / t[1]
    elif c == "segunda_ordem" and t[1] > 0 and t[0] > 0:
        pts["qₑ (equilíbrio)"] = t[0]
        pts["taxa inicial h = k₂qₑ²"] = t[1] * t[0] ** 2
        pts["meia-vida 1/(k₂qₑ)"] = 1 / (t[1] * t[0])
    elif c == "elovich":
        pts["α (taxa inicial)"] = t[0]
        pts["β"] = t[1]
    elif c == "parabolica":
        pts["b (taxa de difusão)"] = t[1]
    elif c == "dois_compart":
        (c1, k1), (c2, k2) = sorted([(t[0], t[1]), (t[2], t[3])], key=lambda z: -z[1])
        pts["compartimento lábil (C₁)"] = c1
        pts["k lábil"] = k1
        pts["compartimento recalcitrante (C₂)"] = c2
        pts["k recalcitrante"] = k2
        pts["potencial total (C₁ + C₂)"] = c1 + c2
    return pts


_SUP = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def fmt_num(v, digitos=4, idioma="pt", sinal=False):
    """Formata com `digitos` algarismos significativos; notação ×10ⁿ quando necessário."""
    if v is None or not np.isfinite(v):
        return "—"
    av = abs(v)
    if av == 0:
        s = "0"
    elif av >= 1e5 or av < 1e-3:
        e = int(math.floor(math.log10(av)))
        m = av / 10 ** e
        s = f"{m:.{max(digitos - 1, 0)}f}×10{str(e).translate(_SUP)}"
    else:
        dec = max(digitos - 1 - int(math.floor(math.log10(av))), 0)
        s = f"{av:.{dec}f}"
        if "." in s:
            s = s.rstrip("0").rstrip(".") if dec > 0 else s
    if idioma == "pt":
        s = s.replace(".", ",")
    if v < 0:
        return ("− " if sinal else "−") + s
    return ("+ " if sinal else "") + s


def equacao(aj: AjusteModelo, idioma="pt", digitos=4):
    t = aj.params
    F = lambda v, s=True: fmt_num(v, digitos, idioma, sinal=s)
    a = fmt_num(t[0], digitos, idioma)
    c = aj.codigo
    lx = "ln(x)" if aj.desloc_log == 0 else "ln(x + 1)"
    if c == "linear":
        return f"ŷ = {a} {F(t[1])}x"
    if c == "quadratico":
        return f"ŷ = {a} {F(t[1])}x {F(t[2])}x²"
    if c == "cubico":
        return f"ŷ = {a} {F(t[1])}x {F(t[2])}x² {F(t[3])}x³"
    if c == "raiz":
        return f"ŷ = {a} {F(t[1])}√x {F(t[2])}x"
    if c == "log":
        return f"ŷ = {a} {F(t[1])}{lx}"
    if c == "mitscherlich":
        return f"ŷ = {a} {F(-t[1])}·e^(−{fmt_num(t[2], digitos, idioma)}x)"
    if c == "linear_plato":
        x0 = fmt_num(t[2], digitos, idioma)
        return f"ŷ = {a} {F(t[1])}x (x < {x0}); ŷ = {fmt_num(t[0] + t[1] * t[2], digitos, idioma)} (x ≥ {x0})"
    if c == "quadratico_plato":
        x0v = -t[1] / (2 * t[2]) if t[2] != 0 else np.nan
        x0 = fmt_num(x0v, digitos, idioma)
        pl = fmt_num(t[0] - t[1] ** 2 / (4 * t[2]) if t[2] != 0 else np.nan, digitos, idioma)
        return f"ŷ = {a} {F(t[1])}x {F(t[2])}x² (x < {x0}); ŷ = {pl} (x ≥ {x0})"
    if c == "exponencial":
        return f"ŷ = {a}·e^({fmt_num(t[1], digitos, idioma)}x)"
    if c == "potencia":
        return f"ŷ = {a}·x^{fmt_num(t[1], digitos, idioma)}"
    if c == "michaelis":
        return f"ŷ = {a} {F(t[1])}x/({fmt_num(t[2], digitos, idioma)} + x)"
    if c == "logistico":
        return f"ŷ = {a}/(1 + e^(−{fmt_num(t[1], digitos, idioma)}(x − {fmt_num(t[2], digitos, idioma)})))"
    n_ = lambda v: fmt_num(v, digitos, idioma)
    if c == "gompertz":
        return f"ŷ = {a}·exp(−{n_(t[1])}·e^(−{n_(t[2])}x))"
    if c == "weibull":
        return f"ŷ = {a}·[1 − e^(−(x/{n_(abs(t[1]))})^{n_(t[2])})]"
    if c == "langmuir":
        return f"ŷ = {a}·{n_(t[1])}x/(1 + {n_(t[1])}x)"
    if c == "freundlich":
        return f"ŷ = {a}·x^{n_(t[1])}"
    if c == "temkin":
        return f"ŷ = {a}·ln({n_(t[1])}x)"
    if c == "sips":
        return f"ŷ = {a}·({n_(t[1])}x)^{n_(t[2])}/[1 + ({n_(t[1])}x)^{n_(t[2])}]"
    if c == "primeira_ordem":
        return f"ŷ = {a}·(1 − e^(−{n_(t[1])}x))"
    if c == "segunda_ordem":
        return f"ŷ = {n_(t[0] ** 2 * t[1])}x/(1 + {n_(t[0] * t[1])}x)"
    if c == "elovich":
        return f"ŷ = {n_(1 / t[1])}·ln(1 + {n_(t[0] * t[1])}x)"
    if c == "parabolica":
        return f"ŷ = {a} {F(t[1])}√x"
    if c == "dois_compart":
        return f"ŷ = {a}(1 − e^(−{n_(t[1])}x)) + {n_(t[2])}(1 − e^(−{n_(t[3])}x))"
    return ""


# ============================================================================
# Máxima eficiência econômica
# ============================================================================
def mee(aj: AjusteModelo, preco_insumo: float, preco_produto: float, xmin: float, xmax: float, n=4001):
    """Dose de máxima eficiência econômica: maximiza receita líquida
    L(x) = preço_produto·f(x) − preço_insumo·x no intervalo estudado.
    Retorna dict com x, y, receita líquida, razão de preços e se o ótimo ficou na borda."""
    if preco_produto <= 0:
        return None
    xs = np.linspace(xmin, xmax, n)
    ys = aj.prever(xs)
    L = preco_produto * ys - preco_insumo * xs
    i = int(np.nanargmax(L))
    # refinamento local
    if 0 < i < n - 1:
        res = optimize.minimize_scalar(lambda x: -(preco_produto * float(aj.prever(np.array([x]))[0]) - preco_insumo * x),
                                       bounds=(xs[i - 1], xs[i + 1]), method="bounded")
        x_ot = float(res.x)
    else:
        x_ot = float(xs[i])
    y_ot = float(aj.prever(np.array([x_ot]))[0])
    # máxima eficiência técnica numérica (para comparação)
    j = int(np.nanargmax(ys))
    return dict(x=x_ot, y=y_ot, receita_liquida=preco_produto * y_ot - preco_insumo * x_ot,
                razao=preco_insumo / preco_produto, borda=(i == 0 or i == n - 1),
                x_met=float(xs[j]), y_met=float(ys[j]))
