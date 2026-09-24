"""
Textos automáticos: parágrafo de Material e Métodos e interpretação dos
resultados. Tudo é gerado de forma determinística a partir dos resultados —
nenhum número é inventado; o texto é um rascunho para o autor revisar.
"""
from __future__ import annotations

import numpy as np

from .comparacoes import METODOS, METODOS_EN
from .modelo import rotulo_transformacao
from .regressao import CATALOGO, fmt_num


def _p(p, idioma="pt"):
    if p is None or not np.isfinite(p):
        return "—"
    if p < 0.001:
        return "p < 0,001" if idioma == "pt" else "P < 0.001"
    s = f"{p:.3f}"
    return ("p = " + s.replace(".", ",")) if idioma == "pt" else f"P = {s}"


def _n(v, idioma="pt", dig=3):
    return fmt_num(v, dig, idioma)


def estrela(p):
    if p is None or not np.isfinite(p):
        return ""
    return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"


def _lista(itens, idioma="pt"):
    itens = [str(i) for i in itens]
    if len(itens) <= 1:
        return "".join(itens)
    conj = " e " if idioma == "pt" else " and "
    return ", ".join(itens[:-1]) + conj + itens[-1]


# ============================================================================
# Material e Métodos
# ============================================================================
def metodos(spec, opcoes, resultados, idioma="pt"):
    fat = spec.fatores
    alfa = opcoes.alfa
    pt = idioma == "pt"
    a_txt = f"{alfa:g}".replace(".", ",") if pt else f"{alfa:g}"
    qual = [f.rotulo for f in fat if not f.quantitativo]
    quant = [f.rotulo for f in fat if f.quantitativo]
    partes = []
    if pt:
        base = {"DIC": "inteiramente casualizado", "DBC": "em blocos casualizados", "DQL": "em quadrado latino"}[spec.base]
        est = spec.estrutura
        if est == "simples":
            d = f"Os dados foram submetidos à análise de variância (ANOVA) segundo o delineamento {base}, tendo {fat[0].rotulo} como fonte de variação."
        elif est == "fatorial":
            niv = " × ".join(f"{f.rotulo}" for f in fat)
            d = f"Os dados foram submetidos à análise de variância (ANOVA) segundo o delineamento {base}, em esquema fatorial ({niv})."
        elif est == "fatorial_adicional":
            niv = " × ".join(f.rotulo for f in fat)
            d = (f"Os dados foram submetidos à análise de variância (ANOVA) segundo o delineamento {base}, em esquema fatorial "
                 f"({niv}) com tratamento(s) adicional(is); a soma de quadrados de tratamentos foi decomposta nos efeitos do "
                 f"fatorial, no contraste fatorial vs. adicional(is) e na comparação entre adicionais.")
        elif est in ("subdividida", "subsubdividida"):
            n1 = _lista([f.rotulo for f in fat if f.estrato == 1])
            n2 = _lista([f.rotulo for f in fat if f.estrato == 2])
            d = (f"Os dados foram submetidos à análise de variância (ANOVA) segundo o delineamento {base}, em esquema de "
                 f"parcelas {'sub-' if est == 'subsubdividida' else ''}subdivididas, com {n1} nas parcelas e {n2} nas subparcelas")
            if est == "subsubdividida":
                d += f" e {_lista([f.rotulo for f in fat if f.estrato == 3])} nas sub-subparcelas"
            d += "; cada fator foi testado contra o resíduo do seu estrato."
        else:
            d = (f"Os dados foram submetidos à análise de variância (ANOVA) segundo o delineamento em blocos casualizados, "
                 f"em faixas, com {fat[0].rotulo} nas faixas horizontais e {fat[1].rotulo} nas faixas verticais.")
        partes.append(d)
        partes.append("A normalidade dos resíduos foi verificada pelo teste de Shapiro-Wilk e a homogeneidade das "
                      "variâncias pelos testes de Bartlett e de Levene (Brown-Forsythe)"
                      + ("; a aditividade do modelo foi avaliada pelo teste de não aditividade de Tukey." if spec.base == "DBC" and not spec.multiestrato else "."))
        if opcoes.transformacao:
            partes.append(f"Para atender aos pressupostos, os dados foram transformados ({rotulo_transformacao(opcoes.transformacao)}); "
                          "as médias são apresentadas na escala original.")
        if qual:
            m = METODOS[opcoes.metodo]
            frase_m = {"tukey": "pelo teste de Tukey", "scott_knott": "pelo teste de Scott-Knott",
                       "lsd": "pelo teste t (LSD de Fisher)", "duncan": "pelo teste de Duncan", "snk": "pelo teste de Student-Newman-Keuls",
                       "bonferroni": "pelo teste t com correção de Bonferroni",
                       "dunnett": "com o controle pelo teste de Dunnett"}[opcoes.metodo]
            partes.append(f"Quando o teste F foi significativo (p < {a_txt}), as médias de {_lista(qual)} foram comparadas "
                          f"{frase_m} (p < {a_txt}).")
        if quant:
            partes.append(f"Para {_lista(quant)}, fator(es) quantitativo(s), ajustaram-se modelos de regressão (polinomiais e não "
                          "lineares) às médias, testados com o quadrado médio do erro experimental; o modelo foi escolhido pela "
                          "significância dos parâmetros, pela falta de ajuste não significativa e pelo menor critério de "
                          "informação de Akaike corrigido (AICc).")
        if len(fat) > 1:
            s = "Interações significativas foram desdobradas, estudando-se cada fator dentro dos níveis do(s) outro(s)"
            if spec.multiestrato:
                s += ("; nos desdobramentos que envolvem mais de um estrato de erro utilizou-se o erro combinado, com graus "
                      "de liberdade aproximados pelo método de Satterthwaite")
            partes.append(s + ".")
        partes.append("As análises foram realizadas em Python (NumPy, SciPy e statsmodels).")
    else:
        base = {"DIC": "a completely randomized design", "DBC": "a randomized complete block design",
                "DQL": "a Latin square design"}[spec.base]
        est = spec.estrutura
        if est == "simples":
            d = f"Data were subjected to analysis of variance (ANOVA) according to {base}, with {fat[0].rotulo} as the source of variation."
        elif est == "fatorial":
            d = f"Data were subjected to ANOVA according to {base} in a factorial arrangement ({' × '.join(f.rotulo for f in fat)})."
        elif est == "fatorial_adicional":
            d = (f"Data were subjected to ANOVA according to {base} in a factorial arrangement ({' × '.join(f.rotulo for f in fat)}) "
                 "plus additional treatment(s); the treatment sum of squares was partitioned into factorial effects, the "
                 "factorial vs. additional contrast and the comparison among additional treatments.")
        elif est in ("subdividida", "subsubdividida"):
            d = (f"Data were subjected to ANOVA according to {base} in a {'split-split' if est == 'subsubdividida' else 'split'}-plot "
                 f"arrangement, with {_lista([f.rotulo for f in fat if f.estrato == 1], 'en')} in the main plots and "
                 f"{_lista([f.rotulo for f in fat if f.estrato == 2], 'en')} in the subplots")
            if est == "subsubdividida":
                d += f" and {_lista([f.rotulo for f in fat if f.estrato == 3], 'en')} in the sub-subplots"
            d += "; each factor was tested against the error term of its stratum."
        else:
            d = (f"Data were subjected to ANOVA according to a strip-plot design in randomized complete blocks, with "
                 f"{fat[0].rotulo} in horizontal strips and {fat[1].rotulo} in vertical strips.")
        partes.append(d)
        partes.append("Normality of residuals was checked with the Shapiro-Wilk test and homogeneity of variances with "
                      "Bartlett's and Levene's (Brown-Forsythe) tests"
                      + ("; additivity was assessed with Tukey's one-degree-of-freedom test." if spec.base == "DBC" and not spec.multiestrato else "."))
        if opcoes.transformacao:
            partes.append(f"Data were transformed ({rotulo_transformacao(opcoes.transformacao)}) to meet the assumptions; "
                          "means are shown on the original scale.")
        if qual:
            partes.append(f"When the F test was significant (P < {a_txt}), means of {_lista(qual, 'en')} were compared using "
                          f"{METODOS_EN[opcoes.metodo]} test (P < {a_txt}).")
        if quant:
            partes.append(f"For the quantitative factor(s) ({_lista(quant, 'en')}), polynomial and nonlinear regression models "
                          "were fitted to the means and tested against the experimental error mean square; the model was "
                          "selected based on parameter significance, non-significant lack of fit and the lowest corrected "
                          "Akaike information criterion (AICc).")
        if len(fat) > 1:
            s = "Significant interactions were partitioned by analysing each factor within the levels of the other(s)"
            if spec.multiestrato:
                s += ("; slices spanning more than one error stratum used the combined error with Satterthwaite's "
                      "approximate degrees of freedom")
            partes.append(s + ".")
        partes.append("Analyses were performed in Python (NumPy, SciPy and statsmodels).")
    return " ".join(partes)


# ============================================================================
# Interpretação por variável
# ============================================================================
def interpretar(res, idioma="pt"):
    pt = idioma == "pt"
    spec = res.spec
    alfa = res.alfa
    v = res.variavel
    frases = []
    efeitos = [l for l in res.anova if l.termo and isinstance(l.termo[0], int)]
    sig = [l for l in efeitos if l.p is not None and l.p < alfa]
    # termo de maior ordem significativo
    if not sig:
        if pt:
            frases.append(f"Nenhuma fonte de variação afetou significativamente {v} (p ≥ {alfa:g}".replace(".", ",") + ").")
        else:
            frases.append(f"No source of variation significantly affected {v} (P ≥ {alfa:g}).")
    else:
        ordem = max(len(l.termo) for l in sig)
        top = [l for l in sig if len(l.termo) == ordem]
        for l in top:
            if len(l.termo) > 1:
                frases.append((f"{v} foi influenciado pela interação {l.fonte} (F = {_n(l.f, idioma)}; {_p(l.p, idioma)})."
                               if pt else f"{v} was affected by the {l.fonte} interaction (F = {_n(l.f, idioma)}; {_p(l.p, idioma)})."))
            else:
                frases.append((f"{v} variou em função de {l.fonte} (F = {_n(l.f, idioma)}; {_p(l.p, idioma)})."
                               if pt else f"{v} varied with {l.fonte} (F = {_n(l.f, idioma)}; {_p(l.p, idioma)})."))
        outros = [l for l in sig if len(l.termo) < ordem and not any(set(l.termo) < set(t.termo) for t in top)]
        for l in outros:
            frases.append((f"Houve também efeito de {l.fonte} (F = {_n(l.f, idioma)}; {_p(l.p, idioma)})."
                           if pt else f"There was also an effect of {l.fonte} (F = {_n(l.f, idioma)}; {_p(l.p, idioma)})."))
    # médias
    for fa in res.fatias:
        f = spec.fatores[fa.fator]
        if fa.p is None or fa.p >= alfa:
            continue
        cond = ", ".join(f"{spec.fatores[k].rotulo} {nv}" for k, nv in fa.condicao.items())
        cond = ", ".join(f"{spec.fatores[k].rotulo} = {nv}" for k, nv in fa.condicao.items())
        pref = (f"Para {cond}, " if pt else f"For {cond}, ") if cond else ""
        if fa.regressao is not None and fa.regressao.melhor is not None:
            m = fa.regressao.melhor
            eq = m.equacao(idioma)
            txt = (f"{pref}a resposta a {f.rotulo} foi descrita pelo modelo {m.nome.lower()} ({eq}; R² = {_n(m.r2, idioma)})"
                   if pt else f"{pref}the response to {f.rotulo} was described by the {CATALOGO[m.codigo].nome_en.lower()} model ({eq}; R² = {_n(m.r2, idioma)})")
            pts = m.pontos
            extra = []
            for chave, val in pts.items():
                if isinstance(val, bool):
                    continue
                if chave.startswith("x"):
                    extra.append(f"{chave} = {_n(val, idioma)}")
            if extra and pt:
                txt += "; " + "; ".join(extra[:2])
            frases.append(txt + ".")
        elif fa.comparacao is not None and fa.comparacao.metodo != "dunnett":
            c = fa.comparacao
            med = fa.medias_orig
            topo = [fa.niveis[i] for i, L in enumerate(c.letras) if "a" in L]
            imax = int(np.nanargmax(med))
            imin = int(np.nanargmin(med))
            if pt:
                s = (f"{pref}a maior média de {v} ocorreu em {fa.niveis[imax]} ({_n(med[imax], idioma)}) e a menor em "
                     f"{fa.niveis[imin]} ({_n(med[imin], idioma)})")
                if len(topo) > 1:
                    s += f"; não diferiram do maior valor: {_lista([t for t in topo if t != fa.niveis[imax]])}"
            else:
                s = (f"{pref}the highest mean of {v} was observed for {fa.niveis[imax]} ({_n(med[imax], idioma)}) and "
                     f"the lowest for {fa.niveis[imin]} ({_n(med[imin], idioma)})")
                if len(topo) > 1:
                    s += f"; not different from the highest: {_lista([t for t in topo if t != fa.niveis[imax]], 'en')}"
            frases.append(s + ".")
    # contrastes do fatorial + adicional
    for l in res.anova:
        if l.tipo == "contraste" and l.p is not None:
            if pt:
                frases.append(f"O contraste {l.fonte.lower()} foi {'significativo' if l.p < alfa else 'não significativo'} "
                              f"({_p(l.p, idioma)}).")
            else:
                frases.append(f"The {l.fonte.lower()} contrast was {'significant' if l.p < alfa else 'not significant'} "
                              f"({_p(l.p, idioma)}).")
    # pressupostos
    pr = res.pressupostos
    cv = "; ".join(f"{k} = {_n(val, idioma)}" for k, val in res.cv.items())
    if pt:
        s = f"Coeficiente(s) de variação: {cv}."
        if pr.ok_normalidade is False or pr.ok_homogeneidade is False:
            s += " Atenção: " + pr.recomendacao
        frases.append(s)
    else:
        cv = cv.replace("CV", "CV").replace(",", ".")
        s = f"Coefficient(s) of variation: {cv}."
        if pr.ok_normalidade is False or pr.ok_homogeneidade is False:
            s += " Caution: ANOVA assumptions were not fully met (see assumptions sheet)."
        frases.append(s)
    frases = [f[:1].upper() + f[1:] for f in frases if f]
    return " ".join(frases)
