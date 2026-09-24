"""
Verificação dos pressupostos da ANOVA.

* Normalidade dos resíduos: Shapiro-Wilk (principal) e Anderson-Darling.
* Homogeneidade de variâncias entre tratamentos: Bartlett e Levene
  (Brown-Forsythe, centrado na mediana), sobre os resíduos por tratamento.
* Aditividade bloco × tratamento (DBC): teste de 1 GL de Tukey.
* Valores discrepantes: resíduos studentizados |r| > 3.
* Box-Cox: λ de máxima verossimilhança no modelo completo, quando y > 0.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class Teste:
    nome: str
    estatistica: float | None
    p: float | None
    conclusao: str
    ok: bool | None
    nota: str = ""


@dataclass
class ResultadoPressupostos:
    testes: list
    outliers: pd.DataFrame
    boxcox: dict | None
    ok_normalidade: bool | None
    ok_homogeneidade: bool | None
    recomendacao: str = ""
    extras: dict = field(default_factory=dict)

    def tabela(self):
        return pd.DataFrame([dict(Pressuposto=t.nome, Estatística=t.estatistica, p=t.p, Conclusão=t.conclusao,
                                  Nota=t.nota) for t in self.testes])


def avaliar(res, ajust, rstd, grupos, d, spec, qm_res, gl_res, y_orig=None, X_modelo=None, transformacao=None,
            alfa=0.05) -> ResultadoPressupostos:
    testes = []
    r = np.asarray(res, float)
    n = len(r)
    # --- normalidade
    ok_n = None
    if 3 <= n <= 5000 and np.std(r) > 0:
        W, p = stats.shapiro(r)
        ok_n = p >= alfa
        testes.append(Teste("Normalidade dos resíduos (Shapiro-Wilk)", float(W), float(p),
                            "Normal" if ok_n else "Não normal", ok_n))
        try:
            from statsmodels.stats.diagnostic import normal_ad
            A2, pa = normal_ad(r)
            testes.append(Teste("Normalidade dos resíduos (Anderson-Darling)", float(A2), float(pa),
                                "Normal" if pa >= alfa else "Não normal", pa >= alfa, "complementar"))
        except Exception:
            pass
    # assimetria e curtose (informativo)
    if n > 7:
        testes.append(Teste("Assimetria dos resíduos", float(stats.skew(r)), None,
                            "—", None, "0 = simétrico"))
        testes.append(Teste("Curtose (excesso) dos resíduos", float(stats.kurtosis(r)), None, "—", None,
                            "0 = normal"))

    # --- homogeneidade
    ok_h = None
    grupos = np.asarray(grupos)
    amostras = [r[grupos == g] for g in pd.unique(grupos)]
    amostras = [a for a in amostras if len(a) >= 2]
    if len(amostras) >= 2 and all(np.var(a) > 0 for a in amostras):
        B, pb = stats.bartlett(*amostras)
        L, pl = stats.levene(*amostras, center="median")
        ok_h = pb >= alfa
        testes.append(Teste("Homogeneidade de variâncias (Bartlett)", float(B), float(pb),
                            "Homogêneas" if pb >= alfa else "Heterogêneas", pb >= alfa))
        testes.append(Teste("Homogeneidade de variâncias (Levene/Brown-Forsythe)", float(L), float(pl),
                            "Homogêneas" if pl >= alfa else "Heterogêneas", pl >= alfa,
                            "robusto a não normalidade"))
        vmax, vmin = max(np.var(a, ddof=1) for a in amostras), min(np.var(a, ddof=1) for a in amostras)
        testes.append(Teste("Razão entre maior e menor variância", float(vmax / vmin) if vmin > 0 else None, None,
                            "Aceitável" if vmin > 0 and vmax / vmin < 4 else "Elevada", None, "regra prática < 4"))
    elif len(amostras) < 2:
        testes.append(Teste("Homogeneidade de variâncias", None, None, "Sem repetições suficientes", None))

    # --- aditividade (Tukey) para DBC de um estrato
    if spec.base == "DBC" and not spec.multiestrato and "BL" in d:
        try:
            F, p = _tukey_aditividade(d, ajust)
            testes.append(Teste("Aditividade bloco × tratamento (Tukey, 1 GL)", F, p,
                                "Aditivo" if p >= alfa else "Não aditivo", p >= alfa))
        except Exception:
            pass

    # --- independência (Durbin-Watson na ordem da planilha, informativo)
    if n > 3:
        dw = float(np.sum(np.diff(r) ** 2) / np.sum(r ** 2)) if np.sum(r ** 2) > 0 else None
        if dw is not None:
            testes.append(Teste("Independência (Durbin-Watson, ordem da planilha)", dw, None,
                                "Sem indício" if 1.5 <= dw <= 2.5 else "Possível autocorrelação", None,
                                "≈2 indica independência; só faz sentido se a ordem das linhas for espacial/temporal"))

    # --- outliers
    rs = np.asarray(rstd, float)
    idx = np.where(np.abs(rs) > 3)[0]
    out = pd.DataFrame({"Linha na planilha": d["_linha"].to_numpy()[idx], "Tratamento": d["CEL"].to_numpy()[idx],
                        "Valor": d["y_orig"].to_numpy()[idx], "Resíduo studentizado": rs[idx]})
    if len(idx):
        testes.append(Teste("Valores discrepantes (|resíduo studentizado| > 3)", float(len(idx)), None,
                            f"{len(idx)} observação(ões)", False, "verifique digitação/coleta antes de excluir"))
    else:
        testes.append(Teste("Valores discrepantes (|resíduo studentizado| > 3)", 0.0, None, "Nenhum", True))

    # --- Box-Cox
    bc = None
    if y_orig is not None and X_modelo is not None and np.all(y_orig > 0) and transformacao is None:
        bc = boxcox_perfil(y_orig, X_modelo)

    rec = ""
    if ok_n is False or ok_h is False:
        partes = []
        if ok_n is False:
            partes.append("normalidade")
        if ok_h is False:
            partes.append("homogeneidade de variâncias")
        rec = f"Pressuposto(s) violado(s): {' e '.join(partes)}. "
        if bc and bc.get("sugestao"):
            rec += f"Sugestão: {bc['sugestao']}. "
        rec += "Considere também verificar valores discrepantes ou usar teste não paramétrico."
    return ResultadoPressupostos(testes, out, bc, ok_n, ok_h, rec)


def _tukey_aditividade(d, ajust):
    """Teste de não aditividade de Tukey (1 GL)."""
    y = d["y"].to_numpy(float)
    bl = d["BL"].to_numpy()
    tr = d["CEL"].to_numpy()
    df = pd.DataFrame({"y": y, "bl": bl, "tr": tr})
    mu = y.mean()
    eb = df.groupby("bl")["y"].transform("mean").to_numpy() - mu
    et = df.groupby("tr")["y"].transform("mean").to_numpy() - mu
    Xb = pd.get_dummies(df["bl"], drop_first=True).to_numpy(float)
    Xt = pd.get_dummies(df["tr"], drop_first=True).to_numpy(float)
    X = np.column_stack([np.ones(len(y)), Xb, Xt])
    z = eb * et
    b0 = np.linalg.lstsq(X, y, rcond=None)[0]
    rss0 = np.sum((y - X @ b0) ** 2)
    X1 = np.column_stack([X, z])
    b1 = np.linalg.lstsq(X1, y, rcond=None)[0]
    rss1 = np.sum((y - X1 @ b1) ** 2)
    gl1 = len(y) - np.linalg.matrix_rank(X1)
    F = (rss0 - rss1) / (rss1 / gl1)
    return float(F), float(stats.f.sf(F, 1, gl1))


def boxcox_perfil(y, X, lambdas=None):
    y = np.asarray(y, float)
    lambdas = np.linspace(-2, 2, 81) if lambdas is None else lambdas
    gm = np.exp(np.mean(np.log(y)))
    U, s, _ = np.linalg.svd(X, full_matrices=False)
    U = U[:, s > s.max() * 1e-10]
    n = len(y)
    ll = []
    for lam in lambdas:
        z = gm * np.log(y) if abs(lam) < 1e-9 else (y ** lam - 1) / (lam * gm ** (lam - 1))
        e = z - U @ (U.T @ z)
        ll.append(-n / 2 * np.log(np.sum(e ** 2) / n))
    ll = np.array(ll)
    i = int(np.argmax(ll))
    lam_hat = float(lambdas[i])
    corte = ll[i] - stats.chi2.ppf(0.95, 1) / 2
    ic = lambdas[ll >= corte]
    ic = (float(ic.min()), float(ic.max()))
    sugestao = None
    candidatos = [(1.0, None, "sem transformação"), (0.5, "sqrt", "√y"), (0.0, "log", "log(y)"),
                  (-0.5, "boxcox:-0.5", "1/√y"), (-1.0, "inv", "1/y"), (2.0, "boxcox:2", "y²")]
    dentro = [c for c in candidatos if ic[0] <= c[0] <= ic[1]]
    if dentro:
        melhor = min(dentro, key=lambda c: abs(c[0] - lam_hat))
        if melhor[1] is None:
            sugestao = None
            codigo = None
        else:
            sugestao = f"transformação {melhor[2]} (Box-Cox λ̂ = {lam_hat:.2f}; IC95% {ic[0]:.2f} a {ic[1]:.2f})"
            codigo = melhor[1]
    else:
        sugestao = f"transformação Box-Cox com λ = {lam_hat:.2f} (IC95% {ic[0]:.2f} a {ic[1]:.2f})"
        codigo = f"boxcox:{round(lam_hat, 2)}"
    return dict(lambda_hat=lam_hat, ic95=ic, lambdas=lambdas, loglik=ll, sugestao=sugestao, codigo=codigo)
