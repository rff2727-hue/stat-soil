"""
Estrutura do relatório (independente do formato): uma lista de blocos que os
geradores de Word e de HTML percorrem. Assim os dois saem com o mesmo conteúdo,
a mesma numeração de tabelas e figuras e a mesma ordem de seções.

Blocos: ("capa", titulo, subtitulo, ficha[(rótulo, valor)]) · ("h1"|"h2", texto) · ("p", texto) ·
("tabela", df, titulo, nota, indice) · ("figura", item, legenda) · ("nota", texto)
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from . import exportar, textos
from .comparacoes import METODOS, METODOS_EN

LOCAIS = ("bloco", "linha", "coluna", "repeti", "block", "row", "column", "replic")


def efeitos_testados(res, idioma="pt"):
    """Efeitos com teste F na ANOVA: lista de dict(nome, f, p, eta, local)."""
    ta = exportar._tabela_anova(res, idioma).reset_index()
    col_nome, out = ta.columns[0], []
    eta_col = [c for c in ta.columns if c.startswith("η")]
    for _, l in ta.iterrows():
        f, p = l.get("F"), l.get("p")
        if f is None or p is None or not np.isfinite(f) or not np.isfinite(p):
            continue
        nome = str(l[col_nome])
        eta = float(l[eta_col[0]]) if eta_col and pd.notna(l[eta_col[0]]) else None
        out.append(dict(nome=nome, f=float(f), p=float(p), eta=eta, local=nome.lower().startswith(LOCAIS)))
    return out


def estado_pressupostos(res):
    pr = res.pressupostos
    if pr.ok_normalidade is False or pr.ok_homogeneidade is False:
        return "alerta"
    return "ok"


def resumo_geral(resultados, idioma="pt"):
    """(colunas de efeitos, [(variável, {efeito: p}, {efeito: F}, CV em texto, estado, média)])."""
    colunas, linhas = [], []
    for r in resultados:
        efs = [e for e in efeitos_testados(r, idioma) if not e["local"]]
        for e in efs:
            if e["nome"] not in colunas:
                colunas.append(e["nome"])
        cv = " / ".join(exportar._fmt_str(v, 1, idioma) for v in r.cv.values())
        linhas.append((r.variavel, {e["nome"]: e["p"] for e in efs}, {e["nome"]: e["f"] for e in efs}, cv,
                       estado_pressupostos(r), r.media_geral))
    return colunas, linhas


def _tabela_resumo(resultados, idioma):
    pt = idioma == "pt"
    colunas, linhas = resumo_geral(resultados, idioma)
    d = {}
    for var, ps, fs, cv, est, media in linhas:
        linha = {("Média geral" if pt else "Grand mean"): exportar._fmt_str(media, exportar._decimais(media), idioma)}
        for c in colunas:
            linha[c] = (f"{exportar._fmt_str(fs[c], 2, idioma)}{textos.estrela(ps[c]) if ps[c] < 0.05 else ' ns'}"
                        if c in ps else "—")
        linha["CV (%)"] = cv
        linha["Pressupostos" if pt else "Assumptions"] = (("atendidos" if pt else "met") if est == "ok" else
                                                           ("ver seção" if pt else "see section"))
        d[var] = linha
    df = pd.DataFrame(d).T
    df.index.name = "Variável" if pt else "Variable"
    return df


def montar(resultados, opcoes, itens_fig, idioma="pt", titulo=None, incluir_figuras=True, com_ep=True, extras=None):
    pt = idioma == "pt"
    ok = [r for r in resultados if not isinstance(r, Exception)]
    if not ok:
        raise ValueError("Nenhum resultado para o relatório.")
    spec = ok[0].spec
    T, F = ("Tabela", "Figura") if pt else ("Table", "Figure")
    metodo_nome = (METODOS if pt else METODOS_EN)[opcoes.metodo]
    alfa_txt = f"{opcoes.alfa:g}".replace(".", ",") if pt else f"{opcoes.alfa:g}"
    titulo = titulo or ("Relatório de análise estatística" if pt else "Statistical analysis report")
    n_obs = len(ok[0].residuos) if getattr(ok[0], "residuos", None) is not None else None
    transf = sorted({str(r.transformacao) for r in ok if r.transformacao})
    ficha = [("Delineamento" if pt else "Design", spec.descricao(idioma)),
             ("Variáveis analisadas" if pt else "Response variables", ", ".join(r.variavel for r in ok)),
             ("Teste de médias" if pt else "Mean comparison", f"{metodo_nome} (α = {alfa_txt})")]
    if n_obs:
        ficha.append(("Observações" if pt else "Observations", str(n_obs)))
    if transf:
        ficha.append(("Transformação" if pt else "Transformation", ", ".join(transf)))
    ficha.append(("Data" if pt else "Date", dt.datetime.now().strftime("%d/%m/%Y")))
    B = [("capa", titulo, spec.descricao(idioma), ficha)]
    n_tab, n_fig, sec = 1, 1, 1

    B.append(("h1", f"{sec}. " + ("Resumo dos resultados" if pt else "Summary of results")))
    B.append(("tabela", _tabela_resumo(ok, idioma),
              f"{T} {n_tab}. " + ("Resumo da análise de variância: valor de F e significância de cada efeito."
                                  if pt else "Summary of the analysis of variance: F value and significance of each effect."),
              ("ns: não significativo; * p < 0,05; ** p < 0,01; *** p < 0,001. CV: coeficiente de variação."
               if pt else "ns: not significant; * P < 0.05; ** P < 0.01; *** P < 0.001. CV: coefficient of variation."),
              True))
    n_tab += 1
    sec += 1
    B.append(("h1", f"{sec}. " + ("Material e Métodos: análise estatística" if pt else "Statistical analysis")))
    B.append(("p", textos.metodos(spec, opcoes, ok, idioma)))
    sec += 1
    B.append(("h1", f"{sec}. " + ("Resultados por variável" if pt else "Results by variable")))
    for n_v, r in enumerate(ok, 1):
        B.append(("h2", f"{sec}.{n_v} {r.variavel}"))
        B.append(("p", textos.interpretar(r, idioma)))
        ta = exportar._tabela_anova(r, idioma, efeito=False)
        nota = "; ".join(f"{k} = {exportar._fmt_str(v, 2, idioma)}" for k, v in r.cv.items())
        nota += (". ns: não significativo; * p < 0,05; ** p < 0,01; *** p < 0,001." if pt else
                 ". ns: not significant; * P < 0.05; ** P < 0.01; *** P < 0.001.")
        B.append(("tabela", ta, f"{T} {n_tab}. " + (f"Análise de variância de {r.variavel}." if pt else
                                                    f"Analysis of variance of {r.variavel}."), nota, True))
        n_tab += 1
        for td in r.tabelas_duplas:
            med, ep, let = td["medias"], td["ep"], td["letras"]
            dec = exportar._decimais(np.nanmean(np.abs(med.to_numpy(float))))
            tab = pd.DataFrame({b: [exportar._celula_media(med.loc[a, b], ep.loc[a, b], let.loc[a, b].replace(" ", ""),
                                                           idioma, com_ep, dec) for a in med.index]
                                for b in med.columns}, index=med.index)
            tab.index.name = f"{td['linhas']} \\ {td['colunas']}"
            nota_m = (f"Médias seguidas pela mesma letra minúscula na coluna e maiúscula na linha não diferem pelo teste "
                      f"{metodo_nome} (p < {alfa_txt})." if pt else
                      f"Means followed by the same lowercase letter in the column and uppercase letter in the row do not "
                      f"differ by {metodo_nome} test (P < {alfa_txt}).")
            B.append(("tabela", tab, f"{T} {n_tab}. {r.variavel}: "
                      + (f"interação {td['linhas']} × {td['colunas']}" if pt else f"{td['linhas']} × {td['colunas']} interaction")
                      + ((" (média ± erro-padrão)." if pt else " (mean ± standard error).") if com_ep else "."),
                      nota_m, True))
            n_tab += 1
        principais = [f for f in r.fatias if not f.condicao and f.comparacao is not None]
        usados = {i for td in r.tabelas_duplas for i in td["fatores"]}
        for fa in principais:
            if fa.fator in usados:
                continue
            sig = fa.p is not None and fa.p < r.alfa
            dec = exportar._decimais(np.nanmean(np.abs(fa.medias_orig)))
            linhas = [exportar._celula_media(fa.medias_orig[i], fa.ep_dados[i],
                                             fa.comparacao.letras[i] if sig and fa.comparacao.metodo != "dunnett" else "",
                                             idioma, com_ep, dec) for i in range(len(fa.niveis))]
            tab = pd.DataFrame({r.variavel: linhas}, index=fa.niveis)
            tab.index.name = r.spec.fatores[fa.fator].rotulo
            nota_m = ((f"Médias seguidas pela mesma letra não diferem pelo teste {metodo_nome} (p < {alfa_txt})."
                       if sig else "Efeito não significativo pelo teste F.") if pt else
                      (f"Means followed by the same letter do not differ by {metodo_nome} test (P < {alfa_txt})."
                       if sig else "Not significant by the F test."))
            B.append(("tabela", tab, f"{T} {n_tab}. " + (f"Médias de {r.variavel} por {tab.index.name}." if pt else
                                                         f"Means of {r.variavel} by {tab.index.name}."), nota_m, True))
            n_tab += 1
        # regressões escolhidas
        regs = []
        for fa in r.fatias:
            if fa.regressao and fa.regressao.melhor is not None:
                m = fa.regressao.melhor
                cond = ", ".join(f"{r.spec.fatores[k].rotulo} = {v}" for k, v in fa.condicao.items())
                regs.append({("Fator" if pt else "Factor"): r.spec.fatores[fa.fator].rotulo + (f" ({cond})" if cond else ""),
                             ("Modelo" if pt else "Model"): m.nome, ("Equação" if pt else "Equation"): m.equacao(idioma),
                             "R²": exportar._fmt_str(m.r2, 3, idioma),
                             ("Falta de ajuste" if pt else "Lack of fit"): m.falta_ajuste(idioma, r.alfa)})
        if regs:
            dfr = pd.DataFrame(regs).set_index(list(regs[0])[0])
            B.append(("tabela", dfr, f"{T} {n_tab}. " + (f"Modelos de regressão ajustados para {r.variavel}." if pt else
                                                         f"Regression models fitted to {r.variavel}."),
                      ("Modelo escolhido por adequação e AICc entre os candidatos." if pt else
                       "Model chosen by adequacy and AICc among candidates."), True))
            n_tab += 1
        # pressupostos
        tp = r.pressupostos.tabela()
        tp = tp[[c for c in tp.columns if c in ("Pressuposto", "Estatística", "p", "Conclusão")]]
        tp = tp[tp["p"].notna()].copy()
        tp["Pressuposto"] = [str(n).replace("Normalidade dos resíduos (", "Normalidade: ")
                             .replace("Homogeneidade de variâncias (", "Homogeneidade: ").rstrip(")")
                             if str(n).startswith(("Normalidade dos", "Homogeneidade de")) else str(n)
                             for n in tp["Pressuposto"]]
        tp = tp.set_index("Pressuposto")
        if not pt:
            tp.index.name = "Assumption"
            tp.columns = ["Statistic", "p", "Conclusion"][:len(tp.columns)]
        B.append(("tabela", tp, f"{T} {n_tab}. " + (f"Verificação dos pressupostos da ANOVA de {r.variavel}." if pt else
                                                    f"ANOVA assumption checks for {r.variavel}."),
                  (r.pressupostos.recomendacao or ""), True))
        n_tab += 1
        if incluir_figuras:
            for it in [i for i in itens_fig if i.variavel == r.variavel and i.spec.tipo != "diagnostico"]:
                B.append(("figura", it, f"{F} {n_fig}. {r.variavel}: {it.titulo}. "
                          + ("Barras: erro-padrão da média." if pt else "Bars: standard error of the mean.")))
                n_fig += 1
    tabs_extra = (extras or {}).get("tabelas") or []
    if tabs_extra:
        sec += 1
        B.append(("h1", f"{sec}. " + ("Análises complementares" if pt else "Additional analyses")))
        for item in tabs_extra:
            B.append(("tabela", item["df"], f"{T} {n_tab}. {item.get('titulo') or ''}", item.get("nota") or "", True))
            n_tab += 1
    B.append(("nota", "Relatório gerado pela plataforma Stat-Soil com motor determinístico; revise textos e legendas "
              "antes de usar." if pt else "Generated by the Stat-Soil platform (deterministic engine); review before use."))
    return B
