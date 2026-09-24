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
    "linear": ModeloDef("linear", "Linear", "Linear", ["a", "b"], ["b"], True, familia="polinomial"),
    "quadratico": ModeloDef("quadratico", "Quadrático", "Quadratic", ["a", "b", "c"], ["c"], True, familia="polinomial"),
    "cubico": ModeloDef("cubico", "Cúbico", "Cubic", ["a", "b", "c", "d"], ["d"], True, familia="polinomial"),
    "raiz": ModeloDef("raiz", "Raiz quadrada", "Square-root", ["a", "b", "c"], ["b", "c"], True),
    "log": ModeloDef("log", "Logarítmico", "Logarithmic", ["a", "b"], ["b"], True),
    "mitscherlich": ModeloDef("mitscherlich", "Exponencial assintótico (Mitscherlich)", "Asymptotic exponential (Mitscherlich)",
                              ["a", "b", "c"], ["b", "c"], False),
    "linear_plato": ModeloDef("linear_plato", "Linear-platô", "Linear-plateau", ["a", "b", "x₀"], ["b"], False),
    "quadratico_plato": ModeloDef("quadratico_plato", "Quadrático-platô", "Quadratic-plateau", ["a", "b", "c"], ["c"], False),
    "exponencial": ModeloDef("exponencial", "Exponencial", "Exponential", ["a", "b"], ["b"], False),
    "potencia": ModeloDef("potencia", "Potência", "Power", ["a", "b"], ["b"], False, exige_positivo=True),
    "michaelis": ModeloDef("michaelis", "Hiperbólico (Michaelis-Menten)", "Hyperbolic (Michaelis-Menten)",
                           ["y₀", "a", "b"], ["a"], False),
    "logistico": ModeloDef("logistico", "Logístico (3P)", "Logistic (3P)", ["a", "b", "c"], ["b"], False),
}

PADRAO = ["linear", "quadratico", "cubico", "raiz", "log", "mitscherlich", "linear_plato", "quadratico_plato",
          "exponencial", "potencia", "michaelis", "logistico"]


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

    def prever(self, x):
        return _f(self.codigo, x, self.params, self.desloc_log)

    def equacao(self, idioma="pt", digitos=4):
        return equacao(self, idioma, digitos)


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
    best = None

    def resid(t):
        return sw * (y - _f(cod, x, t))

    for s0 in starts:
        try:
            r = optimize.least_squares(resid, np.asarray(s0, float), method="lm", max_nfev=5000)
        except Exception:
            try:
                r = optimize.least_squares(resid, np.asarray(s0, float), max_nfev=5000)
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
    return ""
