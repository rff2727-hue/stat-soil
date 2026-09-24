"""
Exportação dos resultados para Excel, com tabelas no padrão de periódico
(três filetes horizontais, sem linhas verticais, sem negrito, Roboto).
"""
from __future__ import annotations

import datetime as dt
import io
import math

import numpy as np
import pandas as pd

from . import textos
from .comparacoes import METODOS, METODOS_EN
from .modelo import rotulo_transformacao
from .regressao import CATALOGO, fmt_num

FONTE = "Roboto"

T = {
    "pt": dict(fonte="Fonte de variação", gl="GL", sq="SQ", qm="QM", f="F", p="p", media="Média", ep="EP", n="n",
               letra="Letras", cv="CV (%)", media_geral="Média geral", resumo="Resumo", nivel="Nível",
               titulo="Análise estatística de experimento", ns="ns: não significativo; * p < 0,05; ** p < 0,01; *** p < 0,001"),
    "en": dict(fonte="Source of variation", gl="df", sq="SS", qm="MS", f="F", p="P", media="Mean", ep="SE", n="n",
               letra="Letters", cv="CV (%)", media_geral="Overall mean", resumo="Summary", nivel="Level",
               titulo="Statistical analysis of experiment", ns="ns: not significant; * P < 0.05; ** P < 0.01; *** P < 0.001"),
}


def _decimais(v):
    if v is None or not np.isfinite(v) or v == 0:
        return 2
    return int(min(4, max(0, 2 - math.floor(math.log10(abs(v))))))


def _fmt_str(v, dec, idioma):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "—"
    s = f"{v:,.{dec}f}"
    if idioma == "pt":
        s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return s.replace("-", "−")


class Planilha:
    """Escreve tabelas em estilo 'booktabs' numa aba do xlsxwriter."""

    def __init__(self, wb, nome, idioma="pt", larguras=None):
        self.wb, self.idioma = wb, idioma
        self.ws = wb.add_worksheet(nome[:31])
        self.ws.hide_gridlines(2)
        self.ws.set_column(0, 0, 34)
        self.ws.set_column(1, 30, 13)
        if larguras:
            for c, w in larguras.items():
                self.ws.set_column(c, c, w)
        self.lin = 0
        self._cache = {}

    def f(self, **kw):
        base = dict(font_name=FONTE, font_size=10, valign="vcenter")
        base.update(kw)
        chave = tuple(sorted(base.items()))
        if chave not in self._cache:
            self._cache[chave] = self.wb.add_format(base)
        return self._cache[chave]

    def titulo(self, texto, tamanho=13):
        self.ws.write(self.lin, 0, texto, self.f(font_size=tamanho, font_color="#5B3A29"))
        self.lin += 1

    def texto(self, texto, cor="#1A1A1A", tamanho=10, italico=False, quebra=False, largura_cols=8):
        if quebra:
            self.ws.merge_range(self.lin, 0, self.lin, largura_cols, texto,
                                self.f(text_wrap=True, valign="top", font_size=tamanho, font_color=cor, italic=italico))
            linhas = max(1, int(len(texto) / (largura_cols * 16)) + 1)
            self.ws.set_row(self.lin, 14 * linhas)
        else:
            self.ws.write(self.lin, 0, texto, self.f(font_size=tamanho, font_color=cor, italic=italico))
        self.lin += 1

    def pular(self, n=1):
        self.lin += n

    def tabela(self, df: pd.DataFrame, legenda=None, nota=None, formatos=None, indice=True, recuo_col=None):
        """formatos: dict coluna -> 'int' | 'dec:N' | 'p' | 'txt' | 'auto'"""
        formatos = formatos or {}
        if legenda:
            self.ws.write(self.lin, 0, legenda, self.f(font_color="#1A1A1A", italic=False))
            self.lin += 1
        cols = ([df.index.name or ""] if indice else []) + [str(c) for c in df.columns]
        topo = self.lin
        for j, c in enumerate(cols):
            self.ws.write(topo, j, c, self.f(top=2, bottom=1, align="left" if j == 0 else "center",
                                             font_color="#1A1A1A"))
        self.lin += 1
        n = len(df)
        for i, (idx, row) in enumerate(df.iterrows()):
            ult = i == n - 1
            j0 = 0
            if indice:
                self.ws.write(self.lin, 0, str(idx), self.f(bottom=2 if ult else 0, align="left"))
                j0 = 1
            for j, c in enumerate(df.columns):
                v = row[c]
                fm = formatos.get(c, "auto")
                kw = dict(bottom=2 if ult else 0, align="center")
                if j == 0 and not indice:
                    kw["align"] = "left"
                self._celula(self.lin, j0 + j, v, fm, kw)
            self.lin += 1
        if nota:
            self.ws.write(self.lin, 0, nota, self.f(font_size=9, font_color="#6B6B6B", italic=False))
            self.lin += 1
        self.lin += 1
        return topo

    def _celula(self, r, c, v, fm, kw):
        if isinstance(v, tuple) and len(v) == 3 and v[0] == "sup":
            base, sup = v[1], v[2]
            if not sup:
                self.ws.write(r, c, base, self.f(**kw))
            else:
                self.ws.write_rich_string(r, c, self.f(), base, self.f(font_script=1), sup, self.f(**kw))
            return
        if v is None or (isinstance(v, float) and not np.isfinite(v)) or (isinstance(v, str) and v == ""):
            self.ws.write_blank(r, c, None, self.f(**kw))
            return
        if isinstance(v, (bool, np.bool_)):
            self.ws.write(r, c, "sim" if v else "não", self.f(**kw))
            return
        if isinstance(v, str) or fm == "txt":
            if kw.get("align") == "center" and isinstance(v, str) and len(v) > 18:
                kw = dict(kw, align="left")
            self.ws.write(r, c, str(v), self.f(**kw))
            return
        v = float(v)
        if fm == "int":
            self.ws.write_number(r, c, v, self.f(num_format="0", **kw))
        elif fm == "p":
            if v < 0.0001:
                self.ws.write(r, c, "< 0,0001" if self.idioma == "pt" else "< 0.0001", self.f(**kw))
            else:
                self.ws.write_number(r, c, v, self.f(num_format="0.0000", **kw))
        elif fm.startswith("dec:"):
            d = int(fm.split(":")[1])
            self.ws.write_number(r, c, v, self.f(num_format="#,##0" + ("." + "0" * d if d else ""), **kw))
        else:
            d = _decimais(v)
            self.ws.write_number(r, c, v, self.f(num_format="#,##0" + ("." + "0" * d if d else ""), **kw))


# ============================================================================
def _tabela_anova(res, idioma):
    t = T[idioma]
    linhas = []
    for l in res.anova:
        linhas.append({t["fonte"]: ("   " * l.nivel) + l.fonte, t["gl"]: l.gl, t["sq"]: l.sq, t["qm"]: l.qm,
                       t["f"]: l.f, t["p"]: l.p, " ": textos.estrela(l.p) if l.p is not None else ""})
    df = pd.DataFrame(linhas).set_index(t["fonte"])
    return df


def _resumo_qm(resultados, idioma):
    t = T[idioma]
    base = resultados[0]
    fontes = [(l.fonte, l.nivel, l.gl) for l in base.anova if l.tipo != "total"]
    tab = pd.DataFrame(index=[("   " * nv) + f for f, nv, _ in fontes])
    tab.index.name = t["fonte"]
    tab[t["gl"]] = [gl for _, _, gl in fontes]
    for r in resultados:
        mapa = {l.fonte: l for l in r.anova}
        col = []
        for f, _, _ in fontes:
            l = mapa.get(f)
            if l is None or l.qm is None:
                col.append("")
                continue
            col.append(("sup", _fmt_str(l.qm, _decimais(l.qm), idioma), textos.estrela(l.p) if l.p is not None else ""))
        tab[r.variavel] = col
    for k in base.cv:
        tab.loc[k] = [""] + [_fmt_str(r.cv.get(k, np.nan), 2, idioma) for r in resultados]
    tab.loc[t["media_geral"]] = [""] + [_fmt_str(r.media_geral, _decimais(r.media_geral), idioma) for r in resultados]
    return tab


def _celula_media(m, ep, letra, idioma, com_ep=True, dec=None):
    dec = _decimais(m) if dec is None else dec
    s = _fmt_str(m, dec, idioma)
    if com_ep and ep is not None and np.isfinite(ep):
        s += " ± " + _fmt_str(ep, dec, idioma)
    if letra:
        s += " " + letra
    return s


def _tabela_medias_publicacao(resultados, fator_idx, idioma, com_ep=True):
    """Linhas = níveis do fator; colunas = variáveis (quando o efeito não depende de interação)."""
    spec = resultados[0].spec
    niveis = resultados[0].dados.niveis[fator_idx]
    tab = pd.DataFrame(index=niveis)
    tab.index.name = spec.fatores[fator_idx].rotulo
    notas = set()
    for r in resultados:
        fa = [f for f in r.fatias if f.fator == fator_idx and not f.condicao]
        if not fa:
            tab[r.variavel] = ["†"] * len(niveis)
            notas.add("†")
            continue
        fa = fa[0]
        sig = fa.p is not None and fa.p < r.alfa
        dec = _decimais(np.nanmean(np.abs(fa.medias_orig)))
        col = []
        for i, nv in enumerate(fa.niveis):
            L = fa.comparacao.letras[i] if (fa.comparacao and sig and fa.comparacao.metodo != "dunnett") else ""
            if fa.comparacao and fa.comparacao.metodo == "dunnett" and sig:
                L = {"*": "*", "ns": ""}.get(fa.comparacao.letras[i], "")
            col.append(_celula_media(fa.medias_orig[i], fa.ep_dados[i], L, idioma, com_ep, dec))
        nome = r.variavel + ("" if sig else " (ns)")
        tab[nome] = col
    return tab, notas


def gerar_excel(resultados, opcoes, idioma="pt", extras=None, dados_brutos=None, com_ep=True) -> bytes:
    import xlsxwriter
    extras = extras or {}
    t = T[idioma]
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True, "nan_inf_to_errors": True})
    wb.set_properties({"title": t["titulo"], "comments": "Gerado pela plataforma de análise de experimentos"})
    ok = [r for r in resultados if not isinstance(r, Exception)]
    if not ok:
        wb.close()
        return buf.getvalue()
    spec = ok[0].spec
    metodo_nome = (METODOS if idioma == "pt" else METODOS_EN)[opcoes.metodo]

    # ---------------------------------------------------------------- Resumo
    P = Planilha(wb, t["resumo"], idioma)
    P.titulo(t["titulo"], 14)
    P.texto(spec.descricao(idioma), cor="#6B6B6B")
    info = [("Data" if idioma == "pt" else "Date", dt.datetime.now().strftime("%d/%m/%Y %H:%M")),
            ("Nível de significância" if idioma == "pt" else "Significance level",
             f"{opcoes.alfa:g}".replace(".", "," if idioma == "pt" else ".")),
            ("Teste de médias" if idioma == "pt" else "Mean comparison", metodo_nome),
            ("Transformação" if idioma == "pt" else "Transformation", rotulo_transformacao(opcoes.transformacao)),
            ("Variáveis analisadas" if idioma == "pt" else "Response variables", str(len(ok)))]
    for k, v in info:
        P.ws.write(P.lin, 0, k, P.f(font_color="#6B6B6B"))
        P.ws.write(P.lin, 1, v, P.f())
        P.lin += 1
    P.pular()
    leg = ("Tabela 1. Resumo da análise de variância (quadrados médios)" if idioma == "pt"
           else "Table 1. Summary of the analysis of variance (mean squares)")
    P.tabela(_resumo_qm(ok, idioma), legenda=leg, nota=t["ns"], formatos={t["gl"]: "int"})
    # tabelas de médias por fator
    k = 2
    for i, f in enumerate(spec.fatores):
        tab, notas = _tabela_medias_publicacao(ok, i, idioma, com_ep)
        if idioma == "pt":
            leg = f"Tabela {k}. Médias{' ± erro-padrão' if com_ep else ''} por {f.rotulo}"
            nota = (f"Médias seguidas pela mesma letra na coluna não diferem pelo teste {metodo_nome} (p < "
                    f"{opcoes.alfa:g}".replace(".", ",") + "). ns: efeito não significativo.")
            if notas:
                nota += " †: interação significativa — ver desdobramento na aba Médias."
            if f.quantitativo:
                nota += " Fator quantitativo: ver ajuste de regressão."
        else:
            leg = f"Table {k}. Means{' ± standard error' if com_ep else ''} by {f.rotulo}"
            nota = (f"Means followed by the same letter within a column do not differ by {metodo_nome} test "
                    f"(P < {opcoes.alfa:g}). ns: not significant.")
            if notas:
                nota += " †: significant interaction — see partitioned means."
        P.tabela(tab, legenda=leg, nota=nota)
        k += 1
    if spec.estrutura == "fatorial_adicional":
        for r in ok:
            ex = r.extras.get("todos_tratamentos")
            if not ex:
                continue
            c = ex["comparacao"]
            d = pd.DataFrame({t["media"]: ex["medias_orig"], t["ep"]: ex["ep"], t["letra"]: c.letras,
                              **{f"Dunnett vs. {dn.controle}": dn.letras for dn in r.extras["dunnett_adicionais"]}},
                             index=r.dados.celulas)
            d.index.name = "Tratamento" if idioma == "pt" else "Treatment"
            P.tabela(d, legenda=(f"Tabela {k}. {r.variavel}: todos os tratamentos" if idioma == "pt"
                                 else f"Table {k}. {r.variavel}: all treatments"),
                     nota=("* difere do controle (Dunnett); ns: não difere." if idioma == "pt"
                           else "* differs from control (Dunnett); ns: does not differ."))
            k += 1
    P.ws.set_column(1, 40, 18)

    # ---------------------------------------------------------------- ANOVA
    A = Planilha(wb, "ANOVA", idioma)
    for r in ok:
        A.titulo(r.variavel, 12)
        for aviso in r.avisos:
            A.texto("• " + aviso, cor="#A6461E", tamanho=9)
        A.tabela(_tabela_anova(r, idioma), legenda="Análise de variância" if idioma == "pt" else "Analysis of variance",
                 formatos={t["gl"]: "int", t["p"]: "p"},
                 nota="; ".join(f"{k_} = {_fmt_str(v_, 2, idioma)}" for k_, v_ in r.cv.items())
                      + f"; R² = {_fmt_str(r.r2, 3, idioma)}")
        if r.desdobramento:
            d = pd.DataFrame(r.desdobramento).set_index("Fonte")
            d[" "] = [textos.estrela(p) for p in d["p"]]
            d.index.name = t["fonte"]
            A.tabela(d, legenda="Desdobramento da interação" if idioma == "pt" else "Partitioning of the interaction",
                     formatos={"p": "p", "GL": "int", "GL erro": "dec:1"})
        for fa in r.fatias:
            if fa.polinomial:
                cond = ", ".join(f"{r.spec.fatores[k_].rotulo} = {v_}" for k_, v_ in fa.condicao.items())
                d = pd.DataFrame(fa.polinomial).set_index("Fonte")
                d[" "] = [textos.estrela(p) for p in d["p"]]
                d.index.name = t["fonte"]
                A.tabela(d, legenda=(f"Regressão polinomial — {r.spec.fatores[fa.fator].rotulo}" + (f" ({cond})" if cond else "")),
                         formatos={"p": "p", "GL": "int"})
        A.pular()

    # ---------------------------------------------------------------- Médias
    M = Planilha(wb, "Médias" if idioma == "pt" else "Means", idioma)
    for r in ok:
        M.titulo(r.variavel, 12)
        for fa in r.fatias:
            f = r.spec.fatores[fa.fator]
            cond = ", ".join(f"{r.spec.fatores[k_].rotulo} = {v_}" for k_, v_ in fa.condicao.items())
            sig = fa.p is not None and fa.p < r.alfa
            d = pd.DataFrame({t["media"]: fa.medias_orig, t["ep"]: fa.ep_dados, "DP": fa.dp_dados, t["n"]: fa.n},
                             index=fa.niveis)
            if fa.comparacao is not None:
                d[t["letra"] if fa.comparacao.metodo != "dunnett" else "Dunnett"] = fa.comparacao.letras
            d.index.name = f.rotulo
            nota = f"F = {_fmt_str(fa.f, 2, idioma)}; {textos._p(fa.p, idioma)}; GL erro = {_fmt_str(fa.gl, 1, idioma)}"
            if fa.comparacao is not None and fa.comparacao.dms:
                nota += f"; DMS = {_fmt_str(fa.comparacao.dms, _decimais(fa.comparacao.dms), idioma)}"
            if not sig:
                nota += " (ns)"
            M.tabela(d, legenda=f"{f.rotulo}" + (f" — {cond}" if cond else ""), nota=nota, formatos={t["n"]: "int"})
        for td in r.tabelas_duplas:
            med, ep, let = td["medias"], td["ep"], td["letras"]
            dec = _decimais(np.nanmean(np.abs(med.to_numpy(float))))
            tab = pd.DataFrame(index=med.index, columns=med.columns, dtype=object)
            for a in med.index:
                for b in med.columns:
                    tab.loc[a, b] = _celula_media(med.loc[a, b], ep.loc[a, b], let.loc[a, b].replace(" ", ""), idioma,
                                                  com_ep, dec)
            tab.index.name = f"{td['linhas']} \\ {td['colunas']}"
            nota = ("Médias seguidas pela mesma letra minúscula na coluna e maiúscula na linha não diferem pelo teste "
                    f"{metodo_nome} (p < {opcoes.alfa:g})".replace(".", ",") + "." if idioma == "pt" else
                    f"Means followed by the same lowercase letter in the column and uppercase letter in the row do not "
                    f"differ by {metodo_nome} test (P < {opcoes.alfa:g}).")
            M.tabela(tab, legenda=(f"Interação {td['linhas']} × {td['colunas']}" if idioma == "pt"
                                   else f"{td['linhas']} × {td['colunas']} interaction"), nota=nota)
        M.pular()

    # ---------------------------------------------------------------- Regressão
    tem_reg = any(fa.regressao for r in ok for fa in r.fatias)
    if tem_reg:
        R = Planilha(wb, "Regressão" if idioma == "pt" else "Regression", idioma, larguras={1: 46})
        for r in ok:
            for fa in r.fatias:
                if not fa.regressao:
                    continue
                f = r.spec.fatores[fa.fator]
                cond = ", ".join(f"{r.spec.fatores[k_].rotulo} = {v_}" for k_, v_ in fa.condicao.items())
                R.titulo(f"{r.variavel} — {f.rotulo}" + (f" ({cond})" if cond else ""), 12)
                sig = fa.p is not None and fa.p < r.alfa
                if not sig:
                    R.texto(("Efeito do fator não significativo pelo teste F; os ajustes abaixo são apenas descritivos."
                             if idioma == "pt" else "Factor effect not significant by the F test; fits are descriptive only."),
                            cor="#A6461E", tamanho=9)
                linhas = []
                for a in fa.regressao.ajustes:
                    par = "; ".join(f"{nm} = {fmt_num(v_, 4, idioma)} ± {fmt_num(e_, 3, idioma)}{textos.estrela(p_) if np.isfinite(p_) else ''}"
                                    for nm, v_, e_, p_ in zip(CATALOGO[a.codigo].params, a.params, a.ep, a.p_params))
                    pts = "; ".join(f"{k_}: {fmt_num(v_, 4, idioma)}" for k_, v_ in a.pontos.items()
                                    if not isinstance(v_, bool))
                    linhas.append({"Posição": a.rank, "Modelo": a.nome if idioma == "pt" else CATALOGO[a.codigo].nome_en,
                                   "Equação": a.equacao(idioma), "R²": a.r2, "R² aj.": a.r2_aj, "AICc": a.aicc,
                                   "ΔAICc": a.delta_aicc, "Peso de Akaike": a.peso, "p falta de ajuste": a.p_falta,
                                   "Adequado": a.adequado, "Observação": a.motivo, "Parâmetros (± EP)": par,
                                   "Pontos notáveis": pts})
                d = pd.DataFrame(linhas).set_index("Posição")
                R.tabela(d, formatos={"R²": "dec:4", "R² aj.": "dec:4", "AICc": "dec:2", "ΔAICc": "dec:2",
                                      "Peso de Akaike": "dec:3", "p falta de ajuste": "p"},
                         nota=(("Modelo indicado: " + fa.regressao.melhor.nome) if fa.regressao.melhor else "")
                              + (". " + fa.regressao.nota if fa.regressao.nota else ""))
        R.ws.set_column(2, 2, 52)
        R.ws.set_column(11, 12, 60)

    # ---------------------------------------------------------------- Pressupostos
    S = Planilha(wb, "Pressupostos" if idioma == "pt" else "Assumptions", idioma, larguras={0: 52, 4: 60})
    for r in ok:
        S.titulo(r.variavel, 12)
        d = r.pressupostos.tabela().set_index("Pressuposto")
        S.tabela(d, formatos={"p": "p", "Estatística": "dec:4"})
        if len(r.pressupostos.outliers):
            S.tabela(r.pressupostos.outliers.set_index("Linha na planilha"),
                     legenda="Possíveis valores discrepantes" if idioma == "pt" else "Potential outliers",
                     formatos={"Resíduo studentizado": "dec:2"})
        if r.pressupostos.recomendacao:
            S.texto(r.pressupostos.recomendacao, cor="#A6461E", quebra=True, largura_cols=4)
        S.pular()

    # ---------------------------------------------------------------- Descritiva
    D = Planilha(wb, "Descritiva" if idioma == "pt" else "Descriptive", idioma)
    for r in ok:
        D.titulo(r.variavel, 12)
        D.tabela(r.descritiva, formatos={"n": "int", "CV (%)": "dec:1"})

    # ---------------------------------------------------------------- Extras
    if extras.get("correlacao") is not None:
        c = extras["correlacao"]
        C = Planilha(wb, "Correlações" if idioma == "pt" else "Correlations", idioma)
        C.titulo(f"Correlação de {c.metodo} ({c.base})" if idioma == "pt" else f"{c.metodo} correlation ({c.base})", 12)
        C.tabela(c.tabela(idioma), nota=t["ns"].replace("ns: não significativo; ", "").replace("ns: not significant; ", ""))
        rr = pd.DataFrame(c.R, index=c.nomes, columns=c.nomes)
        C.tabela(rr, legenda="Coeficientes" if idioma == "pt" else "Coefficients",
                 formatos={n: "dec:3" for n in c.nomes})
        pp = pd.DataFrame(c.P, index=c.nomes, columns=c.nomes)
        C.tabela(pp, legenda="Valores de p" if idioma == "pt" else "P values", formatos={n: "p" for n in c.nomes})
    if extras.get("pca") is not None:
        p = extras["pca"]
        Q = Planilha(wb, "PCA", idioma)
        Q.titulo(f"Análise de componentes principais ({p.base})" if idioma == "pt" else f"Principal component analysis ({p.base})", 12)
        Q.tabela(p.tabela_autovalores().set_index("Componente"),
                 formatos={"Autovalor": "dec:3", "Variância explicada (%)": "dec:2", "Acumulada (%)": "dec:2"})
        Q.tabela(p.tabela_cargas(), legenda="Correlação entre variáveis e componentes (cargas)" if idioma == "pt"
                 else "Variable–component correlations (loadings)", formatos={c_: "dec:3" for c_ in p.tabela_cargas().columns})
        ncp = min(4, p.escores.shape[1])
        esc = pd.DataFrame(p.escores[:, :ncp], columns=[f"CP{i + 1}" for i in range(ncp)])
        esc.insert(0, "Grupo", p.grupos)
        esc.index = p.rotulos_linhas
        esc.index.name = "Linha/Tratamento"
        Q.tabela(esc, legenda="Escores" if idioma == "pt" else "Scores", formatos={c_: "dec:3" for c_ in esc.columns[1:]})

    # ---------------------------------------------------------------- Textos
    X = Planilha(wb, "Texto" if idioma == "pt" else "Text", idioma)
    X.ws.set_column(0, 0, 120)
    X.titulo("Material e Métodos (rascunho)" if idioma == "pt" else "Materials and Methods (draft)", 12)
    X.ws.write(X.lin, 0, textos.metodos(spec, opcoes, ok, idioma), X.f(text_wrap=True, valign="top"))
    X.ws.set_row(X.lin, 150)
    X.lin += 2
    X.titulo("Resultados (rascunho)" if idioma == "pt" else "Results (draft)", 12)
    for r in ok:
        X.ws.write(X.lin, 0, r.variavel, X.f(font_color="#5B3A29"))
        X.lin += 1
        txt = textos.interpretar(r, idioma)
        X.ws.write(X.lin, 0, txt, X.f(text_wrap=True, valign="top"))
        X.ws.set_row(X.lin, 15 * (len(txt) // 140 + 1))
        X.lin += 2
    X.texto(("Texto gerado automaticamente a partir dos resultados; revise antes de usar." if idioma == "pt"
             else "Automatically generated from the results; review before use."), cor="#6B6B6B", tamanho=9)

    # ---------------------------------------------------------------- Dados
    if dados_brutos is not None:
        ws = wb.add_worksheet("Dados" if idioma == "pt" else "Data")
        hdr = wb.add_format(dict(font_name=FONTE, font_size=10, bottom=1, top=2))
        cel = wb.add_format(dict(font_name=FONTE, font_size=10))
        for j, c in enumerate(dados_brutos.columns):
            ws.write(0, j, str(c), hdr)
            ws.set_column(j, j, max(10, min(28, len(str(c)) + 2)))
        for i, row in enumerate(dados_brutos.itertuples(index=False), start=1):
            for j, v in enumerate(row):
                if isinstance(v, (int, float, np.integer, np.floating)) and not (isinstance(v, float) and np.isnan(v)):
                    ws.write_number(i, j, float(v), cel)
                elif v is None or (isinstance(v, float) and np.isnan(v)):
                    ws.write_blank(i, j, None, cel)
                else:
                    ws.write(i, j, str(v), cel)
        ws.freeze_panes(1, 0)

    # erros
    erros = extras.get("erros") or {}
    if erros:
        E = Planilha(wb, "Erros", idioma)
        E.titulo("Variáveis não analisadas" if idioma == "pt" else "Variables not analysed", 12)
        for var, msg in erros.items():
            E.texto(f"{var}: {msg}", cor="#A6461E")
    wb.close()
    return buf.getvalue()
