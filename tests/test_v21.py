"""
Validação das análises da v2.1: tamanhos de efeito, alternativas robustas,
contrastes, modelo misto (parcelas perdidas), análise conjunta, MEE,
agrupamento, trilha, planejamento, projeto e relatório Word.
"""
import io
import warnings
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats

from motor import exemplos as ex
from motor import exportar, multivariada as mv, planejamento, projeto, relatorio, relatorio_docx, robusto
from motor import tema as tm
from motor.anova import Opcoes, analisar, contrastes
from motor.conjunta import analise_conjunta
from motor.modelo import Especificacao, Fator
from motor.regressao import mee

warnings.filterwarnings("ignore")
REF = Path(__file__).resolve().parent.parent / "exemplos" / "dados_ref.xlsx"


def test_tamanhos_de_efeito():
    df, spec, resp = ex.dic()
    r = analisar(df, spec, resp[0])
    efe = [l for l in r.anova if l.tipo == "efeito"][0]
    err = [l for l in r.anova if l.tipo == "erro"][0]
    assert np.isclose(efe.eta2p, efe.sq / (efe.sq + err.sq))
    N = len(r.dados.d)
    om = (efe.sq - efe.gl * err.qm) / (efe.sq + (N - efe.gl) * err.qm)
    assert np.isclose(efe.omega2p, max(om, 0))


def test_alternativas_robustas_vs_referencias():
    from statsmodels.stats.oneway import anova_oneway
    df, spec, resp = ex.dbc()
    r = analisar(df, spec, resp[0])
    alts = {a.teste: a for a in robusto.alternativas(r)}
    d = r.dados.d
    y, g = d["y_orig"].to_numpy(float), d["CEL"].astype(str).to_numpy()
    w = anova_oneway(y, g, use_var="unequal")
    assert np.isclose(alts["ANOVA de Welch"].estatistica, w.statistic, rtol=1e-6)
    assert np.isclose(alts["ANOVA de Welch"].p, w.pvalue, rtol=1e-5)
    H, pk = stats.kruskal(*[y[g == k] for k in dict.fromkeys(g)])
    assert np.isclose(alts["Kruskal-Wallis"].estatistica, H, rtol=1e-8)
    wide = d.pivot_table(index="BL", columns="CEL", values="y_orig")
    chi, pf = stats.friedmanchisquare(*[wide[c].to_numpy() for c in wide.columns])
    assert np.isclose(alts["Friedman"].estatistica, chi, rtol=1e-8)


def test_contrastes_ortogonais_somam_sq_tratamentos():
    df, spec, resp = ex.dic()
    r = analisar(df, spec, resp[0])
    niveis = list(r.dados.celulas)
    t = len(niveis)
    defs = []
    for j in range(1, t):                       # Helmert
        c = {niveis[i]: (1.0 if i < j else (-float(j) if i == j else 0.0)) for i in range(t)}
        defs.append((f"C{j}", c))
    tab, orto = contrastes(r, defs)
    assert all(o[2] for o in orto)
    sq_trat = [l for l in r.anova if l.tipo == "efeito"][0].sq
    assert np.isclose(tab["SQ"].sum(), sq_trat, rtol=1e-8)
    # contraste simples = teste t de duas médias com o QM do resíduo
    e = [l for l in r.anova if l.tipo == "erro"][0]
    tab2, _ = contrastes(r, [("A-B", {niveis[0]: 1, niveis[1]: -1})])
    n = r.dados.d.groupby("CEL").size().iloc[0]
    ep = np.sqrt(2 * e.qm / n)
    assert np.isclose(tab2["EP"].iloc[0], ep, rtol=1e-8)


def test_modelo_misto_com_parcela_perdida():
    df = pd.read_excel(REF)
    spec = Especificacao("DBC", "subdividida", [Fator("FONTE", "Fonte", 1), Fator("PROF", "Camada", 2)], bloco="REP")
    cheio = analisar(df, spec, "K mg/dm²")
    r = analisar(df.drop(index=[5]), spec, "K mg/dm²")
    assert r.dados.incompleto
    f_cheio = {l.fonte: l.f for l in cheio.anova if l.tipo == "efeito"}
    for l in r.anova:
        if l.tipo == "efeito":
            assert np.isfinite(l.f) and 0.6 < l.f / f_cheio[l.fonte] < 1.6


def test_analise_conjunta_vs_statsmodels():
    df, spec, resp = ex.dbc()
    rng = np.random.default_rng(3)
    partes = []
    for k, fat in enumerate([1.0, 1.2, 0.9]):
        d = df.copy()
        d["Local"] = f"L{k}"
        d[resp[0]] = d[resp[0]] * fat + rng.normal(0, 30, len(d))
        partes.append(d)
    dl = pd.concat(partes, ignore_index=True)
    rc = analise_conjunta(dl, spec, resp[0], "Local")
    m = dl.rename(columns={resp[0]: "y", spec.bloco: "B", spec.fatores[0].coluna: "T"})
    m["B"] = m["B"].astype(str)
    ols = smf.ols("y ~ C(Local) + C(Local):C(B) + C(T) + C(T):C(Local)", m).fit()
    a = sm.stats.anova_lm(ols, typ=1)
    tab = rc.anova.set_index("Fonte de variação")
    rotulo_t = spec.fatores[0].rotulo
    assert np.isclose(tab.loc[rotulo_t, "F"], a.loc["C(T)", "F"], rtol=1e-6)
    qm_b = a.loc["C(Local):C(B)", "sum_sq"] / a.loc["C(Local):C(B)", "df"]
    f_amb = a.loc["C(Local)", "sum_sq"] / a.loc["C(Local)", "df"] / qm_b
    assert np.isclose(tab.loc["Local", "F"], f_amb, rtol=1e-6)
    qmr = rc.individuais["QM resíduo"]
    assert np.isclose(rc.hartley, qmr.max() / qmr.min())


def test_mee_quadratico_analitico():
    from motor.regressao import ajustar_modelos
    x = np.array([0, 40, 80, 120, 160.])
    b0, b1, b2 = 2000.0, 25.0, -0.08
    y = b0 + b1 * x + b2 * x ** 2
    r = ajustar_modelos(x, y, np.full(5, 4), 1e-6, 20, 1e-9, modelos=["quadratico"])
    aj = [a for a in r.ajustes if a.codigo == "quadratico"][0]
    pi, pp = 6.0, 1.5
    out = mee(aj, pi, pp, 0, 160)
    assert np.isclose(out["x"], (pi / pp - b1) / (2 * b2), atol=1e-3)
    assert np.isclose(out["x_met"], -b1 / (2 * b2), atol=0.05)


def test_agrupamento_e_trilha():
    rng = np.random.default_rng(0)
    trat = [f"T{i}" for i in range(6)]
    centro = {t: (0 if i < 3 else 10) for i, t in enumerate(trat)}
    linhas = [{"Trat": t, "A": centro[t] + rng.normal(0, .3), "B": centro[t] * 2 + rng.normal(0, .3),
               "C": rng.normal(5, 1)} for t in trat for _ in range(4)]
    d = pd.DataFrame(linhas)
    a = mv.agrupamento(d, ["A", "B"], "Trat")
    g = dict(zip(a.rotulos, a.grupos))
    assert len(set(g.values())) == 2 and g["T0"] == g["T1"] == g["T2"] != g["T3"]
    assert a.cofenetica > 0.9
    # trilha: efeitos diretos = coeficientes de regressão padronizados
    n = 80
    x1, x2 = rng.normal(size=n), rng.normal(size=n)
    x3 = 0.5 * x1 + rng.normal(size=n)
    yv = 1.0 * x1 + 0.5 * x2 - 0.3 * x3 + rng.normal(size=n)
    dt = pd.DataFrame({"y": yv, "x1": x1, "x2": x2, "x3": x3})
    t = mv.trilha(dt, "y", ["x1", "x2", "x3"])
    z = (dt - dt.mean()) / dt.std(ddof=1)
    beta = sm.OLS(z["y"], z[["x1", "x2", "x3"]]).fit().params
    assert np.allclose(t.efeitos["Efeito direto"], beta, atol=1e-10)
    soma = t.efeitos.drop(columns=["Total (r)"]).sum(axis=1, skipna=True)
    assert np.allclose(soma, t.efeitos["Total (r)"])        # direto + indiretos = correlação


def test_planejamento_poder():
    tab = planejamento.poder_repeticoes(5, 10, 20, 0.05, "DBC", r_max=15)
    assert tab["Poder (%)"].is_monotonic_increasing and tab["Poder (%)"].iloc[-1] > 99
    assert tab["DMS Tukey (% da média)"].is_monotonic_decreasing
    r, _ = planejamento.repeticoes_necessarias(5, 10, 20, 0.05, 0.8)
    assert 2 <= r <= 10


def test_projeto_exato_e_relatorio_com_extras():
    df = pd.read_excel(REF)
    spec = Especificacao("DBC", "subdividida", [Fator("FONTE", "Fonte", 1), Fator("PROF", "Camada", 2)], bloco="REP")
    op = Opcoes()
    pj = projeto.salvar(df, "dados_ref.xlsx", dict(spec=spec, opcoes=op, separar=None, respostas=["pH CaCl2"]),
                        dict(excluir={(None, "pH CaCl2"): {5, 9}}, modelo_escolhido={}))
    df2, nome, cfg, est = projeto.carregar(pj)
    assert df.equals(df2) and cfg["spec"] == spec and est["excluir"] == {(None, "pH CaCl2"): {5, 9}}
    r = analisar(df, spec, "pH CaCl2")
    extra = [dict(aba="Contrastes", titulo="Contrastes — pH", nota="",
                  df=pd.DataFrame({"Estimativa": [1.0], "p": [0.04]}, index=pd.Index(["C1"], name="Contraste")))]
    xl = exportar.gerar_excel([r], op, extras={"tabelas": extra})
    import openpyxl
    nomes = openpyxl.load_workbook(io.BytesIO(xl)).sheetnames
    assert "Alternativas" in nomes and "Contrastes" in nomes
    itens = relatorio.specs_para(r, "pH")
    dc = relatorio_docx.gerar_relatorio([r], op, itens, lambda it: tm.resolver(), extras={"tabelas": extra})
    with zipfile.ZipFile(io.BytesIO(dc)) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    assert "Análises complementares" in xml and "Contrastes — pH" in xml
