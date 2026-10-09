"""
Seções de interface das análises complementares (v2.1): alternativas robustas,
exclusão de discrepantes, contrastes, MEE, análise conjunta, agrupamento,
análise de trilha e planejamento de experimentos.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from motor import exportar, multivariada as mv, planejamento, robusto
from motor.anova import contrastes, niveis_contraste
from motor.conjunta import analise_conjunta
from motor.regressao import mee
from ui_comum import catalogo, nova_versao, ss, tabela_ui

br = lambda v, d=2: exportar._fmt_str(v, d, "pt")


def guardar_tabela(chave, aba, titulo, df, nota=""):
    """Registra uma tabela para sair também no Excel e no relatório Word."""
    ss.tabelas_extra[chave] = dict(aba=aba, titulo=titulo, df=df, nota=nota)


def leitura(rotulo, valor, sub=""):
    """Mostrador numérico no estilo do painel (sem mostradores analógicos)."""
    st.html(f"<div class='leitura'><div class='leitura-rot'>{rotulo}</div>"
            f"<div class='leitura-val'>{valor}</div><div class='leitura-sub'>{sub}</div></div>")


# ============================================================================
# Pressupostos: alternativas robustas e exclusão de discrepantes
# ============================================================================
def secao_robusto(res, nome_base, chave):
    pr = res.pressupostos
    violado = (pr.ok_normalidade is not None and not pr.ok_normalidade) or \
              (pr.ok_homogeneidade is not None and not pr.ok_homogeneidade)
    with st.expander("Alternativas robustas e não paramétricas" + ("  ·  recomendadas" if violado else ""),
                     expanded=violado):
        st.caption("Welch + Games-Howell (variâncias desiguais), Kruskal-Wallis + Dunn e Friedman + Conover "
                   "(postos). As combinações de tratamentos são tratadas como um único fator; p ajustados por Holm."
                   + (" Em parcelas subdivididas/faixas essas alternativas ignoram a estrutura de parcelas: use-as como "
                      "verificação de robustez das conclusões, não como análise principal." if res.spec.multiestrato
                      else ""))
        try:
            alts = robusto.alternativas(res)
        except Exception as e:
            st.error(f"Não foi possível calcular: {e}")
            return
        if not alts:
            st.info("Sem alternativa aplicável a este delineamento.")
            return
        resumo = pd.DataFrame([{"Teste": a.teste, "Estatística": a.estatistica, "GL": a.gl, "p": a.p,
                                "Pós-teste": a.posthoc} for a in alts])
        tabela_ui(resumo, f"alternativas_{nome_base}", f"Alternativas à ANOVA — {res.variavel}", "", f"alt_{chave}")
        nomes = [f"{a.teste} · {a.posthoc}" for a in alts]
        esc = st.segmented_control("Ver detalhes", nomes, key=f"alt_sel_{chave}")
        if esc:
            a = alts[nomes.index(esc)]
            c1, c2 = st.columns([2, 3])
            with c1:
                tabela_ui(a.tabela, f"{a.teste}_{nome_base}".replace(" ", "_"), f"{a.teste} — {res.variavel}",
                          a.nota + " Letras iguais: sem diferença pelo pós-teste.", f"alt_t_{chave}_{a.teste}")
            with c2:
                tabela_ui(a.pares, f"{a.posthoc}_{nome_base}".replace(" ", "_"), f"{a.posthoc} — {res.variavel}",
                          "p ajustados pelo método de Holm.", f"alt_p_{chave}_{a.teste}")


def secao_exclusao(res, sel, dados_grupo, ao_reanalisar):
    pr = res.pressupostos
    atuais = sorted(ss.excluir.get(sel, set()))
    with st.expander("Excluir observações e reanalisar" + (f"  ·  {len(atuais)} excluída(s)" if atuais else ""),
                     expanded=bool(atuais)):
        sinal = sorted(int(x) for x in pr.outliers["Linha na planilha"]) if len(pr.outliers) else []
        st.caption("Escolha pelo número da linha na planilha (cabeçalho = linha 1). "
                   + (f"Sinalizadas como discrepantes: {', '.join(map(str, sinal))}. " if sinal else "")
                   + "Confira a digitação antes de excluir e informe a exclusão no artigo.")
        todas = sorted(set(int(i) + 2 for i in dados_grupo.index) | set(atuais))
        esc = st.multiselect("Linhas a excluir", todas, default=atuais, key=f"exc_{sel}",
                             placeholder="ex.: " + (str(sinal[0]) if sinal else "linha"))
        c1, c2, _ = st.columns([2, 2, 3])
        if c1.button("Reanalisar sem estas linhas", type="primary", key=f"exc_b_{sel}", disabled=set(esc) == set(atuais)):
            ss.excluir[sel] = set(esc)
            ao_reanalisar()
            st.rerun()
        if atuais and c2.button("Restaurar todas", key=f"exc_r_{sel}"):
            ss.excluir.pop(sel, None)
            ao_reanalisar()
            st.rerun()
        if atuais and res.spec.multiestrato:
            st.caption("Com parcelas faltantes em parcelas subdivididas, a análise passa a usar modelo misto (REML).")


# ============================================================================
# Contrastes
# ============================================================================
def _helmert(n):
    out = []
    for j in range(1, n):
        c = [0.0] * n
        for i in range(j):
            c[i] = 1.0
        c[j] = -float(j)
        out.append(c)
    return out


def secao_contrastes(res, sel, nome_base, chave):
    spec = res.spec
    st.caption("Contrastes definidos por você (ex.: testemunha vs. demais, fonte A vs. fonte B). Cada linha é um "
               "contraste; os coeficientes devem somar zero. Estimativa, IC 95% e teste F com o erro adequado ao "
               "estrato (Satterthwaite quando necessário).")
    alvos = ["celulas"] + [str(i) for i in range(len(spec.fatores))]
    c1, c2 = st.columns([2, 3])
    alvo = c1.selectbox("Contrastes entre", alvos, key=f"ctr_alvo_{chave}",
                        format_func=lambda a: "Tratamentos (todas as combinações)" if a == "celulas"
                        else f"Níveis de {spec.fatores[int(a)].rotulo}")
    niveis = niveis_contraste(res, alvo)
    nomes = [" / ".join(map(str, n)) if isinstance(n, tuple) else str(n) for n in niveis]
    k_base = f"ctr_base_{chave}_{alvo}"
    if k_base not in ss:
        ss[k_base] = pd.DataFrame([["C1"] + [0.0] * len(nomes)], columns=["Contraste"] + nomes)
    with c2:
        b1, b2, b3 = st.columns(3)
        if b1.button("Primeiro vs. demais", key=f"ctr_p_{chave}", width="stretch",
                     help="Ex.: testemunha (primeiro nível) contra a média dos demais"):
            n = len(nomes)
            ss[k_base] = pd.DataFrame([["1º vs. demais"] + [float(n - 1)] + [-1.0] * (n - 1)],
                                      columns=["Contraste"] + nomes)
            ss[f"ctr_v_{chave}"] = ss.get(f"ctr_v_{chave}", 0) + 1
        if b2.button("Helmert (ortogonais)", key=f"ctr_h_{chave}", width="stretch"):
            ss[k_base] = pd.DataFrame([[f"C{j + 1}"] + c for j, c in enumerate(_helmert(len(nomes)))],
                                      columns=["Contraste"] + nomes)
            ss[f"ctr_v_{chave}"] = ss.get(f"ctr_v_{chave}", 0) + 1
        if b3.button("Limpar", key=f"ctr_l_{chave}", width="stretch"):
            ss[k_base] = pd.DataFrame([["C1"] + [0.0] * len(nomes)], columns=["Contraste"] + nomes)
            ss[f"ctr_v_{chave}"] = ss.get(f"ctr_v_{chave}", 0) + 1
    ed = st.data_editor(ss[k_base], num_rows="dynamic", hide_index=True, width="stretch",
                        key=f"ctr_ed_{chave}_{alvo}_{ss.get(f'ctr_v_{chave}', 0)}",
                        column_config={n: st.column_config.NumberColumn(n, step=0.5, format="%g") for n in nomes})
    if st.button("Calcular contrastes", type="primary", key=f"ctr_go_{chave}"):
        defs = []
        for _, row in ed.iterrows():
            nome = str(row.get("Contraste") or "").strip() or f"C{len(defs) + 1}"
            coefs = {niveis[i]: float(row[n]) if pd.notna(row[n]) else 0.0 for i, n in enumerate(nomes)}
            if any(coefs.values()):
                defs.append((nome, coefs))
        if not defs:
            st.warning("Preencha ao menos um contraste.")
            return
        try:
            tab, orto = contrastes(res, defs, alvo)
        except Exception as e:
            st.error(f"Não foi possível calcular: {e}")
            return
        ss[f"ctr_res_{chave}"] = (tab, orto, alvo)
    if ss.get(f"ctr_res_{chave}"):
        tab, orto, alvo_r = ss[f"ctr_res_{chave}"]
        if len(tab):
            nao_zero = tab[np.abs(tab["Soma dos coef."]) > 1e-9]["Contraste"].tolist()
            nota = "Estimativas na escala original." if not res.transformacao else \
                "Estimativas na escala transformada."
            if orto:
                ok = all(o[2] for o in orto)
                nota += (" Contrastes mutuamente ortogonais." if ok else " Atenção: há contrastes não ortogonais ("
                         + "; ".join(f"{a} × {b}" for a, b, o in orto if not o) + ").")
            tabela_ui(tab, f"contrastes_{nome_base}", f"Contrastes — {res.variavel}", nota, f"ctr_t_{chave}")
            st.caption(nota)
            if nao_zero:
                st.warning("Coeficientes que não somam zero em: " + ", ".join(nao_zero)
                           + ". Nesse caso o teste não é um contraste (compara combinações com zero).")
            guardar_tabela(("contrastes", sel), "Contrastes", f"Contrastes — {res.variavel}"
                           + (f" ({sel[0]})" if sel[0] else ""), tab.set_index("Contraste"), nota)


# ============================================================================
# Regressão: máxima eficiência econômica
# ============================================================================
def secao_mee(res, fa, aj, sel, chave):
    f = res.spec.fatores[fa.fator]
    x = pd.to_numeric(pd.Series(fa.niveis).astype(str).str.replace(",", "."), errors="coerce").to_numpy(float)
    if not np.isfinite(x).all():
        return
    with st.expander("Máxima eficiência econômica (MEE)"):
        st.caption("Dose que maximiza a receita líquida: preço do produto × resposta − preço do insumo × dose, "
                   "dentro do intervalo estudado. Use preços na mesma moeda e unidades coerentes com os eixos.")
        un_x = f.unidade or "unidade de x"
        c1, c2 = st.columns(2)
        ss.setdefault(f"mee_pi_{chave}", 1.0)
        ss.setdefault(f"mee_pp_{chave}", 1.0)
        pi = c1.number_input(f"Preço do insumo (por {un_x})", min_value=0.0, step=0.1, format="%.4f",
                             key=f"mee_pi_{chave}")
        pp = c2.number_input("Preço do produto (por unidade de y)", min_value=0.0, step=0.1, format="%.4f",
                             key=f"mee_pp_{chave}")
        if pp <= 0:
            st.info("Informe o preço do produto.")
            return
        r = mee(aj, pi, pp, float(np.nanmin(x)), float(np.nanmax(x)))
        if r is None:
            return
        dx, dy = exportar._decimais(r["x"]), exportar._decimais(r["y"])
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            leitura("Dose MEE", br(r["x"], dx), un_x)
        with k2:
            leitura("Resposta na MEE", br(r["y"], dy), "")
        with k3:
            leitura("Máx. técnica", br(r["x_met"], dx), f"y = {br(r['y_met'], dy)}")
        with k4:
            leitura("Razão de preços", br(r["razao"], 4), "insumo ÷ produto")
        if r["borda"]:
            st.warning("O ótimo econômico ficou no limite do intervalo estudado: não extrapole além das doses testadas.")
        chave_t = ("mee", sel, chave)
        incluir = st.toggle("Incluir no Excel e no relatório", value=chave_t in ss.tabelas_extra, key=f"mee_inc_{chave}")
        if incluir:
            tab = pd.DataFrame([{"Modelo": aj.nome, "Preço do insumo": pi, "Preço do produto": pp, "Dose MEE": r["x"],
                                 "Resposta na MEE": r["y"], "Receita líquida": r["receita_liquida"],
                                 "Dose de máxima técnica": r["x_met"]}]).set_index("Modelo")
            guardar_tabela(chave_t, "MEE", f"Máxima eficiência econômica — {res.variavel} ({f.rotulo})"
                           + (f" — {sel[0]}" if sel[0] else ""), tab,
                           "Receita líquida = preço do produto × resposta − preço do insumo × dose.")
        else:
            ss.tabelas_extra.pop(chave_t, None)


# ============================================================================
# Análise conjunta
# ============================================================================
def secao_conjunta(df, spec, variavel, coluna_amb, opcoes, chave):
    if spec.multiestrato or spec.estrutura == "fatorial_adicional" or spec.base == "DQL":
        st.info("A análise conjunta está disponível para DIC e DBC com um fator ou fatorial.")
        return
    st.caption(f"Reúne os experimentos de cada {coluna_amb} num modelo único (blocos dentro de ambientes). "
               "Primeiro verifica a homogeneidade dos resíduos (razão de Hartley < 7).")
    c1, c2 = st.columns([3, 2])
    aleat = c1.toggle("Ambientes aleatórios (tratamentos testados contra a interação com ambientes)", value=False,
                      key=f"cj_al_{chave}")
    if c2.button("Executar análise conjunta", type="primary", key=f"cj_go_{chave}", width="stretch"):
        try:
            ss[f"cj_res_{chave}"] = analise_conjunta(df, spec, variavel, coluna_amb, opcoes, aleat, coluna_amb)
        except Exception as e:
            st.error(f"Não foi possível executar: {e}")
            return
    rc = ss.get(f"cj_res_{chave}")
    if rc is None:
        return
    k1, k2, k3 = st.columns(3)
    with k1:
        leitura("Razão de Hartley", br(rc.hartley, 2), "homogêneo (< 7)" if rc.homogeneo else "heterogêneo (≥ 7)")
    with k2:
        leitura("Ambientes", str(len(rc.individuais)), coluna_amb)
    with k3:
        leitura("CV conjunto (%)", br(list(rc.resultado.cv.values())[0], 2), "")
    (st.success if rc.homogeneo else st.warning)(rc.nota)
    tabela_ui(rc.individuais, f"conjunta_individuais_{variavel}", f"Análises individuais — {variavel}", "",
              f"cj_i_{chave}")
    tabela_ui(rc.anova, f"conjunta_anova_{variavel}", f"Análise conjunta — {variavel}", rc.nota, f"cj_a_{chave}")
    guardar_tabela(("conjunta_ind", variavel), "Análise conjunta", f"Análises individuais — {variavel}",
                   rc.individuais.set_index("Ambiente"))
    guardar_tabela(("conjunta", variavel), "Análise conjunta", f"Análise conjunta — {variavel}",
                   rc.anova.set_index("Fonte de variação"), rc.nota)
    r = rc.resultado
    for td in r.tabelas_duplas:
        med, ep, let = td["medias"], td["ep"], td["letras"]
        dec = exportar._decimais(np.nanmean(np.abs(med.to_numpy(float))))
        tab = pd.DataFrame({b: [exportar._celula_media(med.loc[a, b], ep.loc[a, b], let.loc[a, b].replace(" ", ""),
                                                       "pt", True, dec) for a in med.index] for b in med.columns},
                           index=med.index)
        tab.index.name = f"{td['linhas']} \\ {td['colunas']}"
        tabela_ui(tab.reset_index(), f"conjunta_interacao_{variavel}", f"{variavel}: {td['linhas']} × {td['colunas']}",
                  "Minúsculas na coluna e maiúsculas na linha.", f"cj_td_{chave}_{td['linhas']}")
    for fa in [f for f in r.fatias if not f.condicao and f.comparacao is not None]:
        sig = fa.p is not None and fa.p < r.alfa
        d = pd.DataFrame({r.spec.fatores[fa.fator].rotulo: fa.niveis, "Média": fa.medias_orig, "EP": fa.ep_dados,
                          "Letras": fa.comparacao.letras if sig else [""] * len(fa.niveis)})
        tabela_ui(d, f"conjunta_medias_{variavel}_{fa.fator}", f"Médias de {variavel} na análise conjunta",
                  "" if sig else "Efeito não significativo.", f"cj_m_{chave}_{fa.fator}")


# ============================================================================
# Multivariada: agrupamento e trilha
# ============================================================================
def secao_agrupamento(df, numericas, cat_cols, padrao, mostrar_figuras, idioma="pt"):
    st.caption("Agrupa tratamentos pela semelhança das médias padronizadas (distância euclidiana). O número de "
               "grupos é definido pelo critério de Mojena; a correlação cofenética mede a fidelidade do dendrograma.")
    vs = st.multiselect("Variáveis", numericas, default=[v for v in padrao if v in numericas], key="ag_vars")
    c1, c2, c3 = st.columns(3)
    fatores = [f.coluna for f in ((ss.config_exec or {}).get("spec").fatores if ss.config_exec else [])]
    COMB = "(tratamentos da análise)"
    opcoes = ([COMB] if fatores else []) + [c for c in cat_cols if df[c].nunique() >= 3]
    grupo = c1.selectbox("Tratamentos (linhas do dendrograma)", opcoes, key="ag_grupo",
                         help="Padrão: combinações dos fatores definidos na análise.") if opcoes else None
    metodo = c2.selectbox("Método de ligação", ["average", "ward", "complete", "single"], key="ag_met",
                          format_func=lambda m: {"average": "UPGMA", "ward": "Ward", "complete": "Ligação completa",
                                                 "single": "Vizinho mais próximo"}[m])
    k = c3.slider("Constante de Mojena (k)", 1.0, 3.5, 1.25, 0.05, key="ag_k",
                  help="1,25 (Milligan & Cooper) é o mais usado; valores maiores formam menos grupos.")
    if st.button("Agrupar", type="primary", key="ag_go", disabled=not (grupo and len(vs) >= 2)):
        d = df
        col = grupo
        if grupo == COMB:
            d = df.copy()
            col = "_TRATAMENTO"
            d[col] = d[fatores].astype(str).agg(" / ".join, axis=1)
        if d[col].nunique() < 3:
            st.warning("São necessários ao menos 3 tratamentos para o agrupamento.")
        else:
            try:
                ss.extras["agrupamento"] = mv.agrupamento(d, vs, col, metodo, k)
                nova_versao()
            except Exception as e:
                st.error(f"Não foi possível agrupar: {e}")
    a = ss.extras.get("agrupamento")
    if a is None:
        return
    n_g = len(set(int(x) for x in a.grupos))
    k1, k2, k3 = st.columns(3)
    with k1:
        leitura("Grupos (Mojena)", str(n_g), a.metodo)
    with k2:
        leitura("Correlação cofenética", br(a.cofenetica, 3), "boa ≥ 0,7")
    with k3:
        leitura("Altura de corte", br(a.corte, 3) if a.corte else "—", "")
    mostrar_figuras([catalogo(idioma)["multi::dendrograma"]], "dend")
    tg = pd.DataFrame({"Tratamento": a.rotulos, "Grupo": [int(g) for g in a.grupos]}).sort_values(["Grupo"])
    c1, c2 = st.columns([1, 2])
    with c1:
        tabela_ui(tg, "agrupamento_grupos", f"Grupos formados ({a.metodo}, Mojena)",
                  f"Correlação cofenética = {br(a.cofenetica, 3)}.", "ag_g")
    with c2:
        dist = a.distancias.rename_axis(index=None, columns=None).reset_index().rename(columns={"index": "Tratamento"})
        tabela_ui(dist, "agrupamento_distancias", "Distâncias euclidianas (médias padronizadas)", "", "ag_d")
    guardar_tabela("agrupamento", "Agrupamento", f"Grupos formados ({a.metodo}, critério de Mojena)",
                   tg.set_index("Tratamento"), f"Correlação cofenética = {br(a.cofenetica, 3)}.")


def secao_trilha(df, numericas, cat_cols):
    st.caption("Desdobra a correlação de cada variável explicativa com a principal em efeito direto e efeitos "
               "indiretos (via as demais). Verifique a multicolinearidade: número de condição < 100 e VIF < 10.")
    c1, c2 = st.columns([1, 2])
    dep = c1.selectbox("Variável principal (dependente)", numericas, key="tr_dep")
    exp_ = c2.multiselect("Variáveis explicativas", [c for c in numericas if c != dep], key="tr_exp")
    c3, c4 = st.columns(2)
    fatores = [f.coluna for f in (ss.config_exec["spec"].fatores if ss.config_exec else [])]
    COMB = "(tratamentos da análise)"
    med = c3.selectbox("Usar médias por", ["(observações)"] + ([COMB] if fatores else [])
                       + [c for c in cat_cols if df[c].nunique() >= 3], key="tr_med")
    kc = c4.slider("Constante de crista (k)", 0.0, 0.5, 0.0, 0.01, key="tr_k",
                   help="Use > 0 apenas com multicolinearidade forte (análise de trilha em crista).")
    if st.button("Calcular trilha", type="primary", key="tr_go", disabled=len(exp_) < 2):
        try:
            d, col = df, (None if med == "(observações)" else med)
            if med == COMB:
                d = df.copy()
                col = "_TRATAMENTO"
                d[col] = d[fatores].astype(str).agg(" / ".join, axis=1)
            ss.extras["trilha"] = mv.trilha(d, dep, exp_, col, kc)
        except Exception as e:
            st.error(f"Não foi possível calcular: {e}")
    t = ss.extras.get("trilha")
    if t is None:
        return
    k1, k2, k3 = st.columns(3)
    with k1:
        leitura("R²", br(t.r2, 3), "coef. de determinação")
    with k2:
        leitura("Efeito residual", br(t.residual, 3), "√(1 − R²)")
    with k3:
        leitura("Nº de condição", br(t.numero_condicao, 1), "< 100: fraca colinearidade")
    ef = t.efeitos.copy()
    ef.insert(len(ef.columns) - 1, "VIF", t.vif)
    ef = ef.reset_index().rename(columns={"index": "Variável"})
    tabela_ui(ef, "trilha", f"Análise de trilha — {t.dependente}", t.nota, "tr_t")
    st.caption(t.nota)
    guardar_tabela("trilha", "Trilha", f"Análise de trilha — {t.dependente}", ef.set_index("Variável"), t.nota)


# ============================================================================
# Planejamento
# ============================================================================
def aba_planejamento():
    st.markdown("#### Quantas repetições usar?")
    st.caption("A partir do CV esperado (de experimentos anteriores ou da análise atual), calcula o poder do teste F "
               "para detectar uma diferença entre duas médias e a DMS de Tukey esperada, para cada número de repetições.")
    cvs = []
    for r in ss.resultados.values():
        if not isinstance(r, Exception):
            cvs.append(list(r.cv.values())[0])
    cv_pad = float(np.round(np.nanmedian(cvs), 1)) if cvs else 10.0
    c1, c2, c3 = st.columns(3)
    t = c1.number_input("Número de tratamentos", 2, 200, 6, key="pl_t")
    cv = c2.number_input("CV esperado (%)", 0.5, 100.0, cv_pad, 0.5, key="pl_cv",
                         help="Sugestão: mediana dos CVs das variáveis analisadas." if cvs else None)
    dif = c3.number_input("Diferença a detectar (% da média)", 1.0, 200.0, 20.0, 1.0, key="pl_dif")
    c4, c5, c6 = st.columns(3)
    ss.setdefault("pl_del", "DBC")
    deline = c4.segmented_control("Delineamento", ["DIC", "DBC"], key="pl_del")
    alfa = c5.select_slider("α", [0.01, 0.05, 0.10], value=0.05, key="pl_alfa")
    poder = c6.select_slider("Poder desejado", [0.70, 0.80, 0.90, 0.95], value=0.80, key="pl_poder",
                             format_func=lambda v: f"{int(v * 100)}%")
    r, tab = planejamento.repeticoes_necessarias(int(t), cv, dif, alfa, poder, deline or "DBC")
    k1, k2, k3 = st.columns(3)
    with k1:
        leitura("Repetições necessárias", str(r) if r else "> 60", f"para poder de {int(poder * 100)}%")
    linha4 = tab[tab["Repetições"] == 4]
    with k2:
        leitura("Poder com 4 repetições", br(float(linha4["Poder (%)"].iloc[0]), 1) + "%" if len(linha4) else "—", "")
    with k3:
        alvo = tab[tab["Repetições"] == (r or 4)]
        leitura("DMS de Tukey esperada", br(float(alvo["DMS Tukey (% da média)"].iloc[0]), 1) + "%" if len(alvo) else "—",
                f"da média, com {r or 4} repetições")
    vis = tab[tab["Repetições"] <= max(12, (r or 0) + 4)]
    c1, c2 = st.columns([3, 2])
    with c1:
        st.line_chart(vis.set_index("Repetições")[["Poder (%)"]], height=280, color="#F2A33A",
                      x_label="Repetições", y_label="Poder do teste F (%)")
    with c2:
        tabela_ui(vis, "planejamento_repeticoes", "Poder do teste F e DMS esperada por número de repetições",
                  f"t = {int(t)}; CV = {br(cv, 1)}%; diferença = {br(dif, 0)}% da média; α = {br(alfa, 2)}.", "pl")
    st.caption("Poder calculado pela F não central na configuração menos favorável (duas médias diferindo pela "
               "diferença informada e as demais no centro). Valores orientativos para o planejamento.")
