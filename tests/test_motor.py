"""
Validação do motor contra implementações de referência (statsmodels/SciPy)
e fórmulas de livro-texto. Rode com:  python -m pytest -q
"""
import math
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.multicomp import pairwise_tukeyhsd

from motor import exemplos as ex
from motor import exportar, relatorio, graficos as gr
from motor.anova import Opcoes, analisar
from motor.comparacoes import letras_de_matriz, scott_knott
from motor.modelo import Especificacao, Fator

warnings.filterwarnings("ignore")
REF = Path(__file__).resolve().parent.parent / "exemplos" / "dados_ref.xlsx"


def _sq(res):
    return {l.fonte: (l.gl, l.sq) for l in res.anova}


def _ols_typ1(formula, d):
    return sm.stats.anova_lm(smf.ols(formula, d).fit(), typ=1)


def test_dic_e_tukey_vs_statsmodels():
    df, spec, resp = ex.dic()
    r = analisar(df, spec, resp[0], Opcoes(metodo="tukey"))
    a = _ols_typ1("Q('%s') ~ C(Tratamento)" % resp[0], df)
    assert math.isclose(_sq(r)["Tratamento"][1], a.loc["C(Tratamento)", "sum_sq"], rel_tol=1e-9)
    tk = pairwise_tukeyhsd(df[resp[0]], df["Tratamento"])
    tab = pd.DataFrame(tk._results_table.data[1:], columns=tk._results_table.data[0])
    nosso = {frozenset((p["g1"], p["g2"])): p["p"] for p in r.fatias[0].comparacao.pares}
    for _, l in tab.iterrows():
        assert abs(nosso[frozenset((l.group1, l.group2))] - l["p-adj"]) < 2e-3


def test_dbc_desbalanceado_tipo3():
    df, spec, resp = ex.dbc()
    df = df.drop(index=[2, 9]).reset_index(drop=True)
    r = analisar(df, spec, resp[0])
    d = df.rename(columns={resp[0]: "y"})
    m = smf.ols("y ~ C(Bloco, Sum) + C(Cultivar, Sum)", d).fit()
    a = sm.stats.anova_lm(m, typ=3)
    assert math.isclose(_sq(r)["Cultivar"][1], a.loc["C(Cultivar, Sum)", "sum_sq"], rel_tol=1e-9)
    assert math.isclose(_sq(r)["Blocos"][1], a.loc["C(Bloco, Sum)", "sum_sq"], rel_tol=1e-9)


def test_dql():
    df, spec, resp = ex.dql()
    r = analisar(df, spec, resp[0])
    a = _ols_typ1("Q('%s') ~ C(Linha) + C(Coluna) + C(Tratamento)" % resp[0], df)
    s = _sq(r)
    assert math.isclose(s["Tratamento"][1], a.loc["C(Tratamento)", "sum_sq"], rel_tol=1e-9)
    assert math.isclose(s["Linhas"][1], a.loc["C(Linha)", "sum_sq"], rel_tol=1e-9)


def test_fatorial_dbc():
    df, spec, resp = ex.fatorial()
    r = analisar(df, spec, resp[0])
    d = df.rename(columns={resp[0]: "y", "Dose P2O5 (kg/ha)": "D"})
    a = _ols_typ1("y ~ C(Bloco) + C(Fonte) * C(D)", d)
    s = _sq(r)
    assert math.isclose(s["Fonte"][1], a.loc["C(Fonte)", "sum_sq"], rel_tol=1e-9)
    assert math.isclose(s["Fonte × Dose de P₂O₅"][1], a.loc["C(Fonte):C(D)", "sum_sq"], rel_tol=1e-9)


def test_fatorial_adicional_particao():
    df, spec, resp = ex.fatorial_adicional()
    r = analisar(df, spec, resp[0])
    s = _sq(r)
    partes = sum(v[1] for k, v in s.items() if k not in ("Blocos", "Tratamentos", "Resíduo", "Total"))
    assert math.isclose(partes, s["Tratamentos"][1], rel_tol=1e-9)
    a = _ols_typ1("Q('%s') ~ C(Bloco) + C(Tratamento)" % resp[0], df)
    assert math.isclose(s["Tratamentos"][1], a.loc["C(Tratamento)", "sum_sq"], rel_tol=1e-9)


def test_subdividida_referencia_e_satterthwaite():
    df = pd.read_excel(REF)
    spec = Especificacao("DBC", "subdividida", [Fator("FONTE", "Fonte", 1), Fator("PROF", "Prof", 2)], bloco="REP")
    r = analisar(df, spec, "K mg/dm²")
    d = df.rename(columns={"K mg/dm²": "y"})
    a = _ols_typ1("y ~ C(REP) + C(FONTE) + C(REP):C(FONTE) + C(PROF) + C(FONTE):C(PROF)", d)
    s = _sq(r)
    assert math.isclose(s["Erro (a)"][1], a.loc["C(REP):C(FONTE)", "sum_sq"], rel_tol=1e-9)
    assert math.isclose(s["Erro (b)"][1], a.loc["Residual", "sum_sq"], rel_tol=1e-9)
    # erro combinado para Fonte dentro de Prof (Banzatto & Kronka)
    qa, ga = s["Erro (a)"][1] / 28, 28
    qb, gb = s["Erro (b)"][1] / 32, 32
    comb = (qa + qb) / 2
    gls = (qa + qb) ** 2 / (qa ** 2 / ga + qb ** 2 / gb)
    fa = [f for f in r.fatias if f.fator == 0][0]
    assert math.isclose(fa.qm_erro, comb, rel_tol=1e-9)
    assert math.isclose(fa.gl, gls, rel_tol=1e-9)
    dms = stats.studentized_range.ppf(0.95, 8, gls) * math.sqrt(comb / 5)
    assert math.isclose(fa.comparacao.dms, dms, rel_tol=1e-6)


def test_subsubdividida_e_faixas():
    df, spec, resp = ex.subsubdividida()
    r = analisar(df, spec, resp[0])
    d = df.rename(columns={resp[0]: "y", "Dose N (kg/ha)": "N"})
    a = _ols_typ1("y ~ C(Bloco)+C(Cobertura)+C(Bloco):C(Cobertura)+C(N)+C(Cobertura):C(N)+"
                  "C(Bloco):C(Cobertura):C(N)+C(Safra)+C(Cobertura):C(Safra)+C(N):C(Safra)+C(Cobertura):C(N):C(Safra)", d)
    s = _sq(r)
    assert math.isclose(s["Erro (b)"][1], a.loc["C(Bloco):C(Cobertura):C(N)", "sum_sq"], rel_tol=1e-9)
    assert math.isclose(s["Erro (c)"][1], a.loc["Residual", "sum_sq"], rel_tol=1e-9)
    df, spec, resp = ex.faixas()
    r = analisar(df, spec, resp[0])
    d = df.rename(columns={resp[0]: "y", "Calcário (t/ha)": "Dc"})
    a = _ols_typ1("y ~ C(Bloco)+C(Preparo)+C(Bloco):C(Preparo)+C(Dc)+C(Bloco):C(Dc)+C(Preparo):C(Dc)", d)
    s = _sq(r)
    assert math.isclose(s["Erro (a)"][1], a.loc["C(Bloco):C(Preparo)", "sum_sq"], rel_tol=1e-9)
    assert math.isclose(s["Erro (b)"][1], a.loc["C(Bloco):C(Dc)", "sum_sq"], rel_tol=1e-9)
    assert math.isclose(s["Erro (c)"][1], a.loc["Residual", "sum_sq"], rel_tol=1e-9)


def test_dunnett_vs_scipy():
    df, spec, resp = ex.dic()
    r = analisar(df, spec, resp[0], Opcoes(metodo="dunnett", controle="Controle"))
    g = {t: df.loc[df.Tratamento == t, resp[0]].to_numpy() for t in df.Tratamento.unique()}
    outros = [t for t in g if t != "Controle"]
    ref = stats.dunnett(*[g[t] for t in outros], control=g["Controle"])
    nosso = {p["g1"]: p["p"] for p in r.fatias[0].comparacao.pares}
    for t, p in zip(outros, ref.pvalue):
        assert abs(nosso[t] - p) < 2e-3


def test_letras():
    m = np.array([10, 9.5, 7, 6.8, 3])
    sig = np.zeros((5, 5), bool)
    for i, j in [(0, 2), (0, 3), (0, 4), (1, 3), (1, 4), (2, 4), (3, 4)]:
        sig[i, j] = sig[j, i] = True
    assert letras_de_matriz(m, sig) == ["a", "ab", "bc", "c", "d"]


def test_scott_knott_separa_grupos_obvios():
    m = np.array([10.0, 10.1, 9.9, 5.0, 5.1, 4.9])
    v = np.full((6, 6), 2 * 0.05 / 4)
    r = scott_knott(list("ABCDEF"), m, v, 20)
    assert r.letras == ["a", "a", "a", "b", "b", "b"]


def test_regressao_recupera_quadratica():
    x = np.array([0, 50, 100, 150, 200.0])
    y = 2 + 0.03 * x - 0.0001 * x ** 2
    from motor.regressao import ajustar_modelos
    r = ajustar_modelos(x, y, np.full(5, 4), 1e-4, 12, 1e-3)
    q = [a for a in r.ajustes if a.codigo == "quadratico"][0]
    assert np.allclose(q.params, [2, 0.03, -0.0001], atol=1e-8)
    assert math.isclose(q.pontos["x no ponto de máximo"], 150, rel_tol=1e-6)


def test_saidas_excel_e_figuras():
    df, spec, resp = ex.fatorial()
    rs = [analisar(df, spec, v) for v in resp]
    b = exportar.gerar_excel(rs, Opcoes(), "pt", dados_brutos=df)
    assert len(b) > 5000
    figs = relatorio.figuras_para(rs[0], gr.ConfigGrafico(), None)
    assert figs
    arq = gr.exportar(figs[0][2], gr.ConfigGrafico(), ("png", "svg"))
    assert arq["png"][:4] == b"\x89PNG" and b"<svg" in arq["svg"][:500]
