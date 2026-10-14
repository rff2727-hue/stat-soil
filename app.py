"""
Stat-Soil — plataforma de análise estatística de experimentos agronômicos.
Python + motor determinístico + Streamlit; entrada e saída em Excel.
"""
from __future__ import annotations

import io
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from motor import __version__
from motor import exportar, multivariada as mv, projeto, relatorio, relatorio_docx, templates, textos, tema as tm
from motor.anova import Opcoes, analisar
from motor.comparacoes import METODOS
from motor.exemplos import exemplo_para
from motor.modelo import (BASES, ESTRUTURAS, ErroDelineamento, Especificacao, Fator, TRANSFORMACOES,
                          rotulo_transformacao, sugerir_colunas)
from motor.regressao import CATALOGO, FAMILIAS, modelos_da_familia
import estilo
import ui_analises as ua
import ui_estudio
from ui_comum import (botoes_figura, catalogo, fmt_tabela, iniciar_estado, nova_versao, previa, rotulo_item, ss,
                      tabela_ui, tema_base)

RAIZ = Path(__file__).resolve().parent
st.set_page_config(page_title="Stat-Soil", page_icon=str(RAIZ / "assets" / "icone.png")
                   if (RAIZ / "assets" / "icone.png").exists() else None, layout="wide")

# ============================================================================
# Identidade visual
# ============================================================================
estilo.aplicar()
iniciar_estado()
_topo = st.container()


def titulo_secao(n, texto):
    estilo.secao(texto)


# ============================================================================
# Barra lateral
# ============================================================================
def abrir_projeto():
    """Callback do envio de projeto: restaura dados, delineamento, opções e estilos."""
    arq = ss.get("w_projeto")
    if arq is None:
        return
    try:
        df, nome, config, estado = projeto.carregar(arq.getvalue())
    except Exception as e:
        ss._erro_projeto = f"Não foi possível abrir o projeto: {e}"
        return
    ss.df, ss.nome_arquivo = df, nome
    for k, v in estado.items():
        if v is not None:
            ss[k] = v
    ss.tema_preset = estado.get("tema_preset") or ss.tema_preset
    sp, op = config["spec"], config["opcoes"]
    limpar_mapeamento()
    # widgets da barra lateral
    ss.base, ss.estrutura = sp.base, sp.estrutura
    ss.w_alfa, ss.w_metodo, ss.w_transf = op.alfa, op.metodo, op.transformacao or "nenhuma"
    ss.w_comp_q, ss.w_alfa_int = op.comparar_quantitativos, op.alfa_interacao or op.alfa
    if op.modelos_regressao:
        ss.w_familias = sorted({CATALOGO[m].familia for m in op.modelos_regressao if m in CATALOGO}) or ["dose"]
        ss.w_modelos = [m for m in op.modelos_regressao if m in CATALOGO]
        ss._familias_ant = modelos_da_familia(ss.w_familias)
    # widgets do mapeamento de colunas
    if sp.bloco:
        ss[K("w_bloco")] = sp.bloco
    if sp.linha:
        ss[K("w_lin")], ss[K("w_col")] = sp.linha, sp.coluna
    if sp.tratamento:
        ss[K("w_trat")] = sp.tratamento
    cols = [f.coluna for f in sp.fatores]
    if sp.estrutura == "simples":
        ss[K("w_f1")] = cols[0]
    elif sp.estrutura in ("fatorial", "fatorial_adicional"):
        ss[K("w_fat")] = cols
    elif sp.estrutura == "faixas":
        ss[K("w_fa")], ss[K("w_fb")] = cols[0], cols[1]
    else:
        for n in (1, 2, 3):
            ss[K(f"w_nivel{n}")] = [f.coluna for f in sp.fatores if f.estrato == n]
    for f in sp.fatores:
        ss[K(f"rot_{f.coluna}")], ss[K(f"q_{f.coluna}")] = f.rotulo, f.quantitativo
        if f.quantitativo:
            ss[K(f"un_{f.coluna}")] = f.unidade or ""
    ss[K("w_resp")] = list(config["respostas"])
    ss[K("w_separar")] = config.get("separar") or "(nenhuma)"
    ss._executar_projeto = config
    ss.aba = "Resultados"


with st.sidebar:
    estilo.logo_lateral()
    estilo.dymo("Delineamento")
    base = st.radio("Casualização", list(BASES), index=1, format_func=lambda b: BASES[b], key="base")
    estruturas_validas = [e for e in ESTRUTURAS if not (base == "DQL" and e in ("subdividida", "subsubdividida", "faixas"))
                          and not (base == "DIC" and e == "faixas")]
    estrutura = st.selectbox("Estrutura dos tratamentos", estruturas_validas, format_func=lambda e: ESTRUTURAS[e],
                             key="estrutura")
    estilo.dymo("Análise")
    ss.setdefault("w_alfa", 0.05)
    alfa = st.select_slider("Nível de significância (α)", [0.01, 0.05, 0.10], key="w_alfa")
    metodo = st.selectbox("Teste de médias", list(METODOS), format_func=lambda m: METODOS[m], key="w_metodo")
    ss.setdefault("w_transf", "nenhuma")
    transf = st.selectbox("Transformação (todas as variáveis)", ["nenhuma"] + [t for t in TRANSFORMACOES if t],
                          format_func=lambda t: TRANSFORMACOES[None if t == "nenhuma" else t], key="w_transf",
                          help="Também é possível aplicar a transformação sugerida pelo Box-Cox em cada variável, "
                               "na aba Pressupostos.")
    transf = None if transf == "nenhuma" else transf
    ss.setdefault("w_familias", ["dose"])
    familias = st.multiselect("Famílias de modelos de regressão", list(FAMILIAS), key="w_familias",
                              format_func=lambda f: FAMILIAS[f],
                              help="Isotermas: x = concentração de equilíbrio. Cinéticas: x = tempo de incubação.")
    with st.expander("Opções avançadas"):
        comparar_q = st.toggle("Aplicar também teste de médias a fatores quantitativos", key="w_comp_q")
        ss.setdefault("w_alfa_int", alfa)
        alfa_int = st.select_slider("α para desdobrar interações", [0.01, 0.05, 0.10], key="w_alfa_int")
        candidatos = modelos_da_familia(familias) or modelos_da_familia(["dose"])
        if ss.get("_familias_ant") != candidatos or "w_modelos" not in ss:
            ss.w_modelos = candidatos
            ss._familias_ant = candidatos
        modelos = st.multiselect("Modelos candidatos", candidatos, key="w_modelos",
                                 format_func=lambda c: CATALOGO[c].nome)
        ss.setdefault("w_com_ep", True)
        com_ep = st.toggle("Tabelas com média ± erro-padrão", key="w_com_ep")
        ss.perfil_auto = st.toggle("Gráfico em perfil para fatores de camada/profundidade", value=ss.get("perfil_auto", True))
    estilo.dymo("Saídas")
    idioma = st.radio("Idioma", ["pt", "en"], horizontal=True, format_func=lambda s: {"pt": "Português", "en": "English"}[s])
    presets = list(tm.PRESETS)
    novo_p = st.selectbox("Tema das figuras", presets, index=presets.index(ss.tema_preset),
                          help="Ajuste fino de cada figura e painéis na aba Estúdio de figuras.")
    if novo_p != ss.tema_preset:
        ss.tema_preset = novo_p
    estilo.dymo("Projeto", laranja=True)
    st.file_uploader("Abrir projeto (.estatexp)", type=["estatexp"], key="w_projeto", on_change=abrir_projeto,
                     help="Reabre dados, delineamento, opções, modelos escolhidos, exclusões e estilos das figuras. "
                          "Salve o projeto na aba Downloads.")
    if ss.get("_erro_projeto"):
        st.error(ss.pop("_erro_projeto"))
    st.caption(f"Motor v{__version__} · resultados determinísticos")

opcoes_base = dict(alfa=alfa, metodo=metodo, transformacao=transf, comparar_quantitativos=comparar_q,
                   alfa_interacao=alfa_int, modelos_regressao=modelos or None)

ABAS = ["Dados e modelo", "Resultados", "Estúdio de figuras", "Multivariada", "Planejamento", "Downloads", "Guia"]
aba_dados, aba_res, aba_est, aba_multi, aba_plan, aba_down, aba_guia = st.tabs(ABAS, key="aba", on_change="rerun")


def K(nome):
    """Chave dos widgets de mapeamento, renovada a cada novo conjunto de dados (o navegador guarda o valor
    antigo dos widgets; trocar a chave garante que as sugestões da nova planilha sejam usadas)."""
    return f"{nome}__d{ss.get('dados_v', 0)}"


def limpar_mapeamento():
    ss.dados_v = ss.get("dados_v", 0) + 1


def ir_para_estudio(fig_id):
    ss.estudio_fig = fig_id
    ss.est_sel_fig = fig_id
    ss.aba = "Estúdio de figuras"
    ss.est_modo = "Figura"


# ============================================================================
# Utilidades
# ============================================================================
def esquema_html(df_ex: pd.DataFrame, pap: dict, n=8):
    cab = "".join(f'<th style="background:{templates.CORES[pap.get(c, "resp")][0]}">{c}</th>' for c in df_ex.columns)
    linhas = ""
    for _, row in df_ex.head(n).iterrows():
        linhas += "<tr>" + "".join(f"<td>{'' if (v == '' or pd.isna(v)) else v}</td>" for v in row) + "</tr>"
    linhas += "<tr>" + "".join("<td>⋮</td>" for _ in df_ex.columns) + "</tr>"
    leg = "".join(f'<span class="papel" style="background:{templates.CORES[p][0]}">{templates.CORES[p][1]}</span>'
                  for p in sorted(set(pap.values()), key=list(templates.CORES).index))
    return f'<table class="esquema"><tr>{cab}</tr>{linhas}</table>{leg}'


@st.cache_data(show_spinner=False)
def ler_planilha(conteudo: bytes, nome: str, aba=None):
    if nome.lower().endswith((".csv", ".txt")):
        txt = conteudo.decode("utf-8-sig", errors="replace")
        sep = ";" if txt.count(";") > txt.count(",") else ","
        return pd.read_csv(io.StringIO(txt), sep=sep, decimal="," if sep == ";" else "."), None
    xl = pd.ExcelFile(io.BytesIO(conteudo))
    aba = aba or xl.sheet_names[0]
    df = xl.parse(aba)
    df = df.dropna(how="all").dropna(axis=1, how="all")
    df.columns = [str(c).strip() for c in df.columns]
    return df, xl.sheet_names


def chave_fatia(fa):
    return (fa.fator, tuple(sorted(fa.condicao.items())))


def spec_da_interface(df):
    """Monta a especificação a partir dos widgets (aba Dados)."""
    colunas = list(df.columns)
    sug = sugerir_colunas(df)
    fatores = []
    c1, c2 = st.columns(2)
    bloco = linha = coluna = trat = None
    with c1:
        if base == "DBC" or estrutura in ("subdividida", "subsubdividida", "faixas"):
            rot = "Coluna de blocos" if base == "DBC" else "Coluna de repetições"
            idx = colunas.index(sug["bloco"]) if sug["bloco"] in colunas else 0
            bloco = st.selectbox(rot, colunas, index=idx, key=K("w_bloco"))
        if base == "DQL":
            linha = st.selectbox("Coluna de linhas", colunas,
                                 index=colunas.index(sug["linha"]) if sug["linha"] in colunas else 0, key=K("w_lin"))
            coluna = st.selectbox("Coluna de colunas", colunas,
                                  index=colunas.index(sug["coluna"]) if sug["coluna"] in colunas else 0, key=K("w_col"))
        if estrutura == "fatorial_adicional":
            trat = st.selectbox("Coluna com o nome de cada tratamento", colunas, key=K("w_trat"),
                                index=colunas.index(sug["tratamento"]) if sug["tratamento"] in colunas else 0,
                                help="Nos tratamentos adicionais, as colunas dos fatores devem estar vazias.")
    usados = {bloco, linha, coluna, trat}
    cand = [c for c in colunas if c not in usados]
    sug_f = [c for c in sug["fatores"] if c in cand]
    with c2:
        if estrutura == "simples":
            f1 = st.selectbox("Fator (tratamentos)", cand, index=cand.index(sug_f[0]) if sug_f else 0, key=K("w_f1"))
            escolha = [(f1, 1)]
        elif estrutura in ("fatorial", "fatorial_adicional"):
            fs = st.multiselect("Fatores do fatorial (2 a 4)", cand, default=sug_f[:2], key=K("w_fat"), max_selections=4)
            escolha = [(c, 1) for c in fs]
        elif estrutura == "faixas":
            fa = st.selectbox("Fator nas faixas horizontais", cand, key=K("w_fa"))
            fb = st.selectbox("Fator nas faixas verticais", [c for c in cand if c != fa], key=K("w_fb"))
            escolha = [(fa, 1), (fb, 2)]
        else:
            niveis = 3 if estrutura == "subsubdividida" else 2
            nomes = {1: "Fator(es) na parcela", 2: "Fator(es) na subparcela", 3: "Fator(es) na sub-subparcela"}
            escolha = []
            restante = list(cand)
            for n in range(1, niveis + 1):
                pad = [c for c in sug_f if c in restante][:1]
                fs = st.multiselect(nomes[n], restante, default=pad, key=K(f"w_nivel{n}"))
                escolha += [(c, n) for c in fs]
                restante = [c for c in restante if c not in fs]
    if escolha:
        st.markdown("**Rótulos e natureza dos fatores**")
        for col, n in escolha:
            if not col:
                continue
            k1, k2, k3 = st.columns([3, 2, 2])
            valores = df[col].dropna()
            numerico = pd.to_numeric(valores.astype(str).str.replace(",", "."), errors="coerce").notna().all()
            n_niv = valores.nunique()
            sug_q = bool(numerico and n_niv >= 3 and not relatorio.parece_camada(col))
            rot = k1.text_input(f"Rótulo de '{col}'", value=str(col), key=K(f"rot_{col}"))
            q = k2.toggle("Quantitativo (regressão)", value=sug_q, key=K(f"q_{col}"), disabled=not numerico,
                          help="Doses, épocas, idades, concentrações… Habilita o ajuste de modelos de regressão.")
            un = k3.text_input("Unidade (eixo x)", value="", key=K(f"un_{col}"), placeholder="ex.: kg ha⁻¹") if q else ""
            fatores.append(Fator(col, rot, n, q, un))
    return Especificacao(base=base, estrutura=estrutura, fatores=fatores, bloco=bloco, linha=linha, coluna=coluna,
                         tratamento=trat), [c for c in colunas if c not in usados | {c for c, _ in escolha}]


def filtrar_excluidas(d, chave):
    exc = ss.excluir.get(chave)
    return d[~(d.index + 2).isin(exc)] if exc else d


def escolher_modelo(sel, chave, wkey):
    ss.modelo_escolhido.setdefault(sel, {})[chave] = ss[wkey]
    nova_versao()


def reanalisar(sel, transformacao=None, manter_transf=False):
    ce = ss.config_exec
    d = filtrar_excluidas(dict(ce["grupos"])[sel[0]], sel)
    if manter_transf:
        transformacao = ss.transf_var.get(sel[1], opcoes_base["transformacao"])
    try:
        ss.resultados[sel] = analisar(d, ce["spec"], sel[1], Opcoes(**{**opcoes_base, "transformacao": transformacao}))
    except Exception as e:
        ss.resultados[sel] = e
    nova_versao()


def executar(df, spec, respostas, separar, op_base, barra=None):
    """Roda a análise de todas as variáveis (e grupos), aplicando transformações e exclusões guardadas."""
    grupos = [(None, df)]
    if separar and separar != "(nenhuma)":
        grupos = [(f"{separar} = {g}", d) for g, d in df.groupby(separar, sort=False)]
    resultados = {}
    tot = len(grupos) * len(respostas)
    i = 0
    for nome_g, d in grupos:
        for v in respostas:
            t_ = ss.transf_var.get(v, op_base["transformacao"])
            op = Opcoes(**{**op_base, "transformacao": t_})
            try:
                resultados[(nome_g, v)] = analisar(filtrar_excluidas(d, (nome_g, v)), spec, v, op)
            except ErroDelineamento as e:
                resultados[(nome_g, v)] = e
            except Exception as e:  # erro inesperado: registra para diagnóstico
                e.detalhe = traceback.format_exc()
                resultados[(nome_g, v)] = e
            i += 1
            if barra is not None:
                barra.progress(i / tot, text=f"Analisando {v}…")
    ss.resultados = resultados
    ss.config_exec = dict(spec=spec, opcoes=Opcoes(**op_base), separar=separar, grupos=grupos, respostas=respostas)
    ss.tabelas_extra = {k: v for k, v in ss.tabelas_extra.items()
                        if k in ("agrupamento", "trilha")}   # análises ligadas aos resultados são refeitas
    nova_versao()
    return resultados


# Projeto aberto pela barra lateral: executa com a configuração salva
if ss.get("_executar_projeto"):
    cfg = ss.pop("_executar_projeto")
    try:
        executar(ss.df, cfg["spec"], cfg["respostas"], cfg.get("separar"),
                 {**opcoes_base, **{k: v for k, v in vars(cfg["opcoes"]).items() if k in opcoes_base}})
        st.toast("Projeto aberto e análises refeitas.")
    except Exception as e:
        st.error(f"Projeto aberto, mas a análise falhou: {e}")


# ============================================================================
# Aba: Dados e modelo
# ============================================================================
if aba_dados.open:
    with aba_dados:
        tpl_bytes, tpl_df, tpl_pap = templates.gerar_template(base, estrutura)
        with st.expander("Como organizar a planilha — modelo para este delineamento", expanded=ss.df is None):
            st.markdown(f"**{BASES[base]} — {ESTRUTURAS[estrutura].lower()}.** Formato longo: **uma linha por unidade "
                        "experimental** (parcela, vaso ou subparcela), uma coluna para cada fator, uma para "
                        "bloco/repetição e uma para cada variável-resposta.")
            st.html(esquema_html(tpl_df, tpl_pap))
            gerais, esp = templates.instrucoes(base, estrutura)
            cA, cB = st.columns(2)
            cA.markdown("**Regras gerais**\n\n" + "\n".join(f"- {g}" for g in gerais[:5]))
            cB.markdown("**Neste delineamento**\n\n" + "\n".join(f"- {g}" for g in esp + gerais[5:]))
            b1, b2, _ = st.columns([3, 2, 3])
            b1.download_button("Baixar modelo em Excel", tpl_bytes, file_name=f"modelo_{base}_{estrutura}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
            if b2.button("Carregar este exemplo"):
                df_ex, spec_ex, resp_ex = exemplo_para(base, estrutura)
                ss.df, ss.nome_arquivo = df_ex, f"exemplo_{base}_{estrutura}.xlsx"
                ss.resultados, ss.excluir, ss.tabelas_extra, ss.extras = {}, {}, {}, {}
                limpar_mapeamento()
                nova_versao()
                st.rerun()

        up = st.file_uploader("Planilha de dados (.xlsx, .xls ou .csv)", type=["xlsx", "xls", "csv", "txt"])
        if up is not None:
            conteudo = up.getvalue()
            _, abas = ler_planilha(conteudo, up.name)
            aba = st.selectbox("Aba", abas) if abas and len(abas) > 1 else None
            df_novo, _ = ler_planilha(conteudo, up.name, aba)
            marca = f"{up.file_id}:{aba}"
            if ss.get("_upload_marca") != marca:
                ss._upload_marca = marca
                ss.df, ss.nome_arquivo, ss.resultados = df_novo, f"{up.name}:{aba}", {}
                ss.excluir, ss.tabelas_extra, ss.extras = {}, {}, {}
                limpar_mapeamento()
                nova_versao()
        df = ss.df
        if df is None:
            estilo.vazio("Nenhuma planilha carregada",
                         "Envie sua planilha acima ou abra “Como organizar a planilha” e carregue o exemplo do "
                         "delineamento escolhido na barra lateral.")
        else:
            st.caption(f"{str(ss.nome_arquivo).replace(':None', '')} — {len(df)} linhas × {df.shape[1]} colunas")
            st.dataframe(df.head(200), height=230, hide_index=True)
            st.markdown("#### Mapeamento das colunas")
            try:
                spec, livres = spec_da_interface(df)
            except Exception as e:
                st.error(f"Não foi possível montar o delineamento: {e}")
                spec, livres = None, []
            sug = sugerir_colunas(df)
            num_livres = [c for c in livres if pd.to_numeric(df[c], errors="coerce").notna().mean() > 0.5]
            padrao_resp = [c for c in sug["respostas"] if c in num_livres] or num_livres[:1]
            respostas = st.multiselect("Variáveis-resposta", num_livres, default=padrao_resp, key=K("w_resp"))
            cS1, cS2 = st.columns([1, 1])
            sep_opts = ["(nenhuma)"] + [c for c in livres if c not in respostas and df[c].nunique() <= 20]
            if ss.get(K("w_separar")) not in sep_opts:
                ss[K("w_separar")] = "(nenhuma)"
            separar = cS1.selectbox("Analisar separadamente por", sep_opts, key=K("w_separar"),
                                    help="Ex.: rodar a análise para cada camada, local ou safra separadamente. "
                                         "Com locais ou safras, a análise conjunta fica disponível em Resultados.")
            rodar = cS2.button("▶ Executar análise", type="primary", width="stretch",
                               disabled=spec is None or not respostas)
            if rodar and spec is not None:
                try:
                    spec.validar(df)
                except ErroDelineamento as e:
                    st.error(str(e))
                    st.stop()
                barra = st.progress(0.0, text="Analisando…")
                resultados = executar(df, spec, respostas, separar, opcoes_base, barra)
                barra.empty()
                n_ok = sum(not isinstance(r, Exception) for r in resultados.values())
                st.success(f"{n_ok} de {len(resultados)} análise(s) concluída(s). Veja a aba Resultados.")
                for (g, v), r in resultados.items():
                    if isinstance(r, Exception):
                        st.error(f"{v}{' — ' + g if g else ''}: {r}")


# ============================================================================
# Aba: Resultados
# ============================================================================
def mostrar_figuras(itens, chave, colunas=2):
    """Figuras em grade de cartões: legenda no estilo de periódico, prévia e uma fileira de ações."""
    for i in range(0, len(itens), colunas):
        cols = st.columns(colunas, gap="large")
        for k, (c, it) in enumerate(zip(cols, itens[i:i + colunas])):
            with c:
                estilo.legenda_figura(i + k + 1, it.titulo)
                try:
                    st.image(previa(it, idioma=idioma), width="stretch")
                except Exception as e:
                    st.error(f"Erro ao desenhar: {e}")
                b1, b2, b3 = st.columns([1.35, 1, 0.9])
                b1.button("Editar no Estúdio", key=f"ed_{chave}_{it.id}", on_click=ir_para_estudio, args=(it.id,),
                          type="primary", width="stretch")
                with b2:
                    ui_estudio.ajuste_rapido(it, idioma, chave)
                with b3:
                    with st.popover("Baixar", width="stretch"):
                        botoes_figura(it, idioma, chave, formatos=("png", "tiff", "svg", "pdf", "eps"), horizontal=False)


if aba_res.open:
    with aba_res:
        if not ss.resultados:
            estilo.vazio("Ainda não há resultados",
                         "Na aba Dados e modelo, confira o mapeamento das colunas e pressione Executar análise.")
        else:
            chaves = list(ss.resultados)
            rotulo_ch = lambda k: k[1] + (f"  ·  {k[0]}" if k[0] else "")
            i_sel = st.selectbox("Variável", list(range(len(chaves))), format_func=lambda i: rotulo_ch(chaves[i]))
            sel = chaves[i_sel]
            res = ss.resultados[sel]
            nome_base = relatorio._slug(sel[1]) + (f"_{relatorio._slug(sel[0])}" if sel[0] else "")
            if isinstance(res, Exception):
                st.error(str(res))
                if hasattr(res, "detalhe"):
                    with st.expander("Detalhes técnicos"):
                        st.code(res.detalhe)
            else:
                spec = res.spec
                m1, m2, m3, m4 = st.columns(4)
                un_y = ss.rotulos_y.get(sel[1], "")
                with m1:
                    estilo.mostrador("Média geral", exportar._fmt_str(res.media_geral, exportar._decimais(res.media_geral), "pt"),
                               sel[1])
                cvs = list(res.cv.items())
                with m2:
                    estilo.mostrador(cvs[0][0].replace(" [escala transformada]", "").replace(" (%)", ""),
                               exportar._fmt_str(cvs[0][1], 1, "pt") + "%",
                               "escala transformada" if res.transformacao else "coef. de variação")
                with m3:
                    if len(cvs) > 1:
                        estilo.mostrador(cvs[1][0].replace(" [escala transformada]", "").replace(" (%)", ""),
                                   exportar._fmt_str(cvs[1][1], 1, "pt") + "%", "coef. de variação")
                    else:
                        estilo.mostrador("R² do modelo", exportar._fmt_str(res.r2, 3, "pt"), "ajuste da ANOVA")
                pr = res.pressupostos
                testes_ok = [t.ok for t in pr.testes if t.ok is not None]
                n_ok = sum(bool(t) for t in testes_ok)
                with m4:
                    tudo = n_ok == len(testes_ok)
                    estilo.mostrador("Pressupostos", f"{n_ok}/{len(testes_ok)}",
                                     "testes atendidos" if tudo else "veja a aba Pressupostos", led="ok" if tudo else "alerta")
                if ss.excluir.get(sel):
                    st.info(f"Análise sem as linhas {', '.join(map(str, sorted(ss.excluir[sel])))} da planilha "
                            "(exclusão feita na aba Pressupostos).")
                if getattr(res.dados, "incompleto", False):
                    st.info("Parcelas faltantes em parcelas subdivididas: análise por modelo misto (REML), com testes F "
                            "de Wald e GL por contenção. Nas linhas de erro da ANOVA aparecem os componentes de "
                            "variância de cada estrato, no lugar do QM.")
                for a in res.avisos:
                    st.warning(a)
                if res.transformacao:
                    st.info(f"Transformação aplicada: {rotulo_transformacao(res.transformacao)}")

                ce = ss.config_exec or {}
                sep_col = ce.get("separar") if ce.get("separar") not in (None, "(nenhuma)") else None
                nomes_sub = ["ANOVA", "Médias e gráficos", "Regressão", "Pressupostos", "Contrastes", "Texto"]
                if sep_col:
                    nomes_sub.insert(5, "Análise conjunta")
                subs = st.tabs(nomes_sub)
                t_anova, t_med, t_reg, t_pres, t_ctr = subs[:5]
                t_txt = subs[-1]
                t_cj = subs[5] if sep_col else None
                nota_sig = f"ns: p ≥ {str(alfa).replace('.', ',')}; * p < 0,05; ** p < 0,01; *** p < 0,001"
                with t_anova:
                    titulo_secao(1, "Análise de variância")
                    ta = exportar._tabela_anova(res, "pt").reset_index()
                    nota_cv = "; ".join(f"{k} = {exportar._fmt_str(v, 2, 'pt')}" for k, v in res.cv.items()) \
                              + f"; R² = {exportar._fmt_str(res.r2, 3, 'pt')}. {nota_sig}"
                    tabela_ui(ta, f"anova_{nome_base}", f"Análise de variância — {sel[1]}", nota_cv, f"an_{i_sel}")
                    st.caption(nota_cv + ". η²p e ω²p: tamanho de efeito parcial (proporção da variação explicada pelo "
                               "efeito, descontado o erro do seu estrato; ω²p é menos enviesado).")
                    if res.desdobramento:
                        st.markdown("**Desdobramento da interação**")
                        d = pd.DataFrame(res.desdobramento)
                        d[" "] = [textos.estrela(p) for p in d["p"]]
                        tabela_ui(d, f"desdobramento_{nome_base}", f"Desdobramento da interação — {sel[1]}", nota_sig,
                                  f"de_{i_sel}")
                        if spec.multiestrato:
                            st.caption("Desdobramentos que combinam estratos usam erro combinado com GL de Satterthwaite.")
                    for j, fa in enumerate(res.fatias):
                        if fa.polinomial:
                            cond = ", ".join(f"{spec.fatores[k].rotulo} = {v}" for k, v in fa.condicao.items())
                            tit = f"Decomposição polinomial — {spec.fatores[fa.fator].rotulo}" + (f" ({cond})" if cond else "")
                            st.markdown(f"**{tit}**")
                            d = pd.DataFrame(fa.polinomial)
                            d[" "] = [textos.estrela(p) for p in d["p"]]
                            tabela_ui(d, f"polinomial_{nome_base}_{j}", tit, nota_sig, f"po_{i_sel}_{j}")

                with t_med:
                    cfg_col, _ = st.columns([2, 3])
                    rot_atual = ss.rotulos_y.get(sel[1], sel[1])
                    novo_rot = cfg_col.text_input("Rótulo do eixo Y (todas as figuras desta variável)", value=rot_atual,
                                                  key=f"roty_{sel}", help="Use sobrescritos Unicode: ⁻¹ ⁻² ⁻³ ² ³ ⁺")
                    if novo_rot != rot_atual:
                        ss.rotulos_y[sel[1]] = novo_rot
                    nota_letras = (f"Médias seguidas pela mesma letra não diferem pelo teste {METODOS[metodo]} "
                                   f"(p < {str(alfa).replace('.', ',')}).")
                    for j, fa in enumerate(res.fatias):
                        cond = ", ".join(f"{spec.fatores[k].rotulo} = {v}" for k, v in fa.condicao.items())
                        sig = fa.p is not None and fa.p < res.alfa
                        tit = f"{spec.fatores[fa.fator].rotulo}" + (f" — {cond}" if cond else "")
                        with st.expander(f"Médias: {tit}  ·  F = {exportar._fmt_str(fa.f, 2, 'pt')}; "
                                         f"{textos._p(fa.p)} {'' if sig else '(ns)'}", expanded=False):
                            d = pd.DataFrame({spec.fatores[fa.fator].rotulo: fa.niveis, "Média": fa.medias_orig,
                                              "EP": fa.ep_dados, "n": fa.n})
                            if getattr(fa, "ic_inf", None) is not None:
                                d["IC 95% inf."], d["IC 95% sup."] = fa.ic_inf, fa.ic_sup
                            if fa.comparacao is not None:
                                d["Letras" if fa.comparacao.metodo != "dunnett" else "Dunnett"] = (
                                    fa.comparacao.letras if sig else [""] * len(fa.niveis))
                            extra = ""
                            if fa.comparacao is not None and fa.comparacao.dms:
                                extra = (f" DMS = {exportar._fmt_str(fa.comparacao.dms, exportar._decimais(fa.comparacao.dms), 'pt')};"
                                         f" GL do erro = {exportar._fmt_str(fa.gl, 1, 'pt')}.")
                            tabela_ui(d, f"medias_{nome_base}_{j}", f"Médias de {sel[1]} — {tit}",
                                      (nota_letras if sig else "Efeito não significativo pelo teste F.") + extra,
                                      f"me_{i_sel}_{j}")
                            if extra:
                                st.caption(extra.strip())
                            if fa.comparacao is not None and fa.comparacao.pares and \
                                    st.toggle("Diferenças par a par com IC", key=f"pp_{sel}_{j}"):
                                pp = pd.DataFrame([{"Nível 1": q["g1"], "Nível 2": q["g2"], "Diferença": q["dif"],
                                                    "EP": q.get("ep_dif"), "IC inf.": q.get("ic_inf"),
                                                    "IC sup.": q.get("ic_sup"), "p": q.get("p"),
                                                    "Significativa": "sim" if q.get("sig") else "não"}
                                                   for q in fa.comparacao.pares])
                                if pp["p"].isna().all():
                                    pp = pp.drop(columns="p")
                                simult = fa.comparacao.metodo in ("tukey", "bonferroni", "dunnett")
                                tabela_ui(pp, f"pares_{nome_base}_{j}", f"Diferenças entre médias — {tit}",
                                          ("Intervalos simultâneos" if simult else "Intervalos individuais")
                                          + f" de {int(round(100 * (1 - res.alfa)))}% ({METODOS[fa.comparacao.metodo]}).",
                                          f"pp_{i_sel}_{j}")
                    for j, td in enumerate(res.tabelas_duplas):
                        st.markdown(f"**Interação {td['linhas']} × {td['colunas']}** — minúsculas comparam "
                                    f"{td['linhas']} na coluna; maiúsculas comparam {td['colunas']} na linha")
                        med, ep, let = td["medias"], td["ep"], td["letras"]
                        dec = exportar._decimais(np.nanmean(np.abs(med.to_numpy(float))))
                        tab = pd.DataFrame({b: [exportar._celula_media(med.loc[a, b], ep.loc[a, b],
                                                                       let.loc[a, b].replace(" ", ""), "pt", com_ep, dec)
                                                for a in med.index] for b in med.columns}, index=med.index)
                        tab.index.name = f"{td['linhas']} \\ {td['colunas']}"
                        tabela_ui(tab.reset_index(), f"interacao_{nome_base}_{j}",
                                  f"{sel[1]}: interação {td['linhas']} × {td['colunas']}",
                                  "Médias seguidas pela mesma letra minúscula na coluna e maiúscula na linha não diferem "
                                  f"pelo teste {METODOS[metodo]} (p < {str(alfa).replace('.', ',')}).", f"in_{i_sel}_{j}")
                    titulo_secao(2, "Gráficos")
                    st.caption("Tema atual: " + ss.tema_preset + (" + ajustes globais" if ss.tema_global else "")
                               + ". Clique em “Editar no Estúdio” para personalizar cada figura.")
                    cat = catalogo(idioma)
                    itens = [it for it in cat.values() if it.variavel == sel[1] and it.grupo == sel[0]
                             and it.spec.tipo != "diagnostico"]
                    mostrar_figuras(itens, f"res_{i_sel}")

                with t_reg:
                    tem = [fa for fa in res.fatias if fa.regressao]
                    if not tem:
                        st.info("Nenhum fator quantitativo com 3 ou mais níveis. Marque o fator como quantitativo na aba Dados.")
                    for j, fa in enumerate(tem):
                        cond = ", ".join(f"{spec.fatores[k].rotulo} = {v}" for k, v in fa.condicao.items())
                        st.markdown(f"**{spec.fatores[fa.fator].rotulo}**" + (f" — {cond}" if cond else ""))
                        if fa.p is not None and fa.p >= res.alfa:
                            st.caption("Efeito não significativo pelo teste F: a resposta é representada pela média; "
                                       "os ajustes são apenas descritivos.")
                        linhas = []
                        for a in fa.regressao.ajustes:
                            linhas.append({"Posição": a.rank, "Modelo": a.nome, "Equação": a.equacao("pt"), "R²": a.r2,
                                           "AICc": a.aicc, "ΔAICc": a.delta_aicc, "Peso": a.peso,
                                           "Falta de ajuste": a.falta_ajuste("pt", res.alfa),
                                           "Adequado": "sim" if a.adequado else "não", "Observação": a.motivo})
                        d = pd.DataFrame(linhas)
                        tabela_ui(d, f"regressao_{nome_base}_{j}", f"Modelos ajustados — {sel[1]}",
                                  "Falta de ajuste não detectada (p alto) indica que o modelo descreve bem as médias. "
                                  "Modelos ordenados por adequação e AICc.", f"rg_{i_sel}_{j}",
                                  column_config={"Falta de ajuste": st.column_config.TextColumn(
                                      help="Teste F de falta de ajuste: compara o desvio das médias em relação à curva "
                                           "com o erro experimental. 'Não detectada ✓' (p alto) = bom ajuste.")})
                        opcoes_m = [a.codigo for a in fa.regressao.ajustes if a.convergiu]
                        atual = ss.modelo_escolhido.get(sel, {}).get(chave_fatia(fa))
                        padrao = fa.regressao.melhor.codigo if fa.regressao.melhor else (opcoes_m[0] if opcoes_m else None)
                        if opcoes_m:
                            k_mod = f"mod_{sel}_{chave_fatia(fa)}"
                            vigente = atual if atual in opcoes_m else (padrao if padrao in opcoes_m else opcoes_m[0])
                            if ss.get(k_mod) != vigente:     # sincroniza com escolhas feitas no Estúdio
                                ss[k_mod] = vigente
                            esc = st.selectbox("Modelo usado nos gráficos, no texto, no Excel e no relatório", opcoes_m,
                                               format_func=lambda c: CATALOGO[c].nome, key=k_mod,
                                               on_change=escolher_modelo, args=(sel, chave_fatia(fa), k_mod),
                                               help="Também pode ser trocado em “Ajuste rápido”, ao lado do gráfico, "
                                                    "e no Estúdio (aba Regressão).")
                            m = [a for a in fa.regressao.ajustes if a.codigo == esc][0]
                            pts = {k: v for k, v in m.pontos.items() if not isinstance(v, bool)}
                            if pts:
                                st.caption(" · ".join(f"{k}: {exportar._fmt_str(v, exportar._decimais(v), 'pt')}"
                                                      for k, v in pts.items()))
                            if CATALOGO[m.codigo].familia in ("dose", "crescimento"):
                                ua.secao_mee(res, fa, m, sel, f"{i_sel}_{j}")
                        if fa.regressao.nota:
                            st.caption(fa.regressao.nota)

                with t_pres:
                    tb = pr.tabela()
                    tb["Situação"] = ["✓" if t.ok else ("✗" if t.ok is False else "") for t in pr.testes]
                    tabela_ui(tb, f"pressupostos_{nome_base}", f"Pressupostos da ANOVA — {sel[1]}", "", f"pr_{i_sel}")
                    if len(pr.outliers):
                        st.markdown("**Possíveis valores discrepantes** (confira a digitação antes de excluir)")
                        tabela_ui(pr.outliers, f"discrepantes_{nome_base}", "Possíveis valores discrepantes", "",
                                  f"ou_{i_sel}")
                    if pr.recomendacao:
                        st.warning(pr.recomendacao)
                    if pr.boxcox and pr.boxcox.get("codigo"):
                        cbx1, cbx2 = st.columns([3, 1])
                        cbx1.caption(f"Box-Cox: λ̂ = {pr.boxcox['lambda_hat']:.2f} "
                                     f"(IC 95%: {pr.boxcox['ic95'][0]:.2f} a {pr.boxcox['ic95'][1]:.2f})".replace(".", ","))
                        if cbx2.button("Aplicar sugestão e reanalisar", key=f"bc_{sel}"):
                            ss.transf_var[sel[1]] = pr.boxcox["codigo"]
                            reanalisar(sel, pr.boxcox["codigo"])
                            st.rerun()
                    if res.transformacao and st.button("Remover transformação desta variável", key=f"rt_{sel}"):
                        ss.transf_var.pop(sel[1], None)
                        reanalisar(sel, None)
                        st.rerun()
                    ua.secao_exclusao(res, sel, dict(ss.config_exec["grupos"])[sel[0]],
                                      lambda: reanalisar(sel, manter_transf=True))
                    ua.secao_robusto(res, nome_base, f"{i_sel}")
                    cat = catalogo(idioma)
                    diag = [it for it in cat.values() if it.variavel == sel[1] and it.grupo == sel[0]
                            and it.spec.tipo == "diagnostico"]
                    for it in diag:
                        st.image(previa(it, idioma=idioma), width="stretch")
                        c1, c2 = st.columns([1, 3])
                        c1.button("Editar no Estúdio", key=f"ed_diag_{it.id}", on_click=ir_para_estudio, args=(it.id,))
                        with c2:
                            botoes_figura(it, idioma, "diag")

                with t_ctr:
                    ua.secao_contrastes(res, sel, nome_base, f"{i_sel}")

                if t_cj is not None:
                    with t_cj:
                        df_all = pd.concat([filtrar_excluidas(dg, (g, sel[1])) for g, dg in ss.config_exec["grupos"]])
                        ua.secao_conjunta(df_all, spec, sel[1], sep_col,
                                          Opcoes(**{**opcoes_base, "transformacao": ss.transf_var.get(sel[1], transf)}),
                                          f"{sel[1]}")

                with t_txt:
                    st.markdown("**Resultados (rascunho)**")
                    st.text_area("Interpretação", textos.interpretar(res, idioma), height=220,
                                 key=f"txt_{sel}_{idioma}", label_visibility="collapsed")
                    st.markdown("**Material e Métodos (rascunho)**")
                    st.text_area("Métodos", textos.metodos(spec, Opcoes(**opcoes_base), [res], idioma), height=200,
                                 key=f"met_{sel}_{idioma}", label_visibility="collapsed")
                    st.caption("Texto gerado deterministicamente a partir dos resultados — revise antes de usar.")


# ============================================================================
# Aba: Estúdio de figuras
# ============================================================================
if aba_est.open:
    with aba_est:
        ui_estudio.render(idioma)


# ============================================================================
# Aba: Multivariada
# ============================================================================
if aba_multi.open:
    with aba_multi:
        if ss.df is None:
            estilo.vazio("Sem dados", "Carregue uma planilha na aba Dados e modelo para calcular correlações, PCA, "
                         "agrupamento e trilha.")
        else:
            df = ss.df
            numericas = [c for c in df.columns if pd.to_numeric(df[c], errors="coerce").notna().mean() > 0.8
                         and df[c].nunique() > 5]
            padrao = (ss.config_exec or {}).get("respostas") or numericas[:6]
            cat_todas = [c for c in df.columns if df[c].nunique() <= 60 and c not in numericas]
            m_cor, m_ag, m_tr = st.tabs(["Correlações e PCA", "Agrupamento", "Análise de trilha"])
            with m_cor:
                vs = st.multiselect("Variáveis", numericas, default=[v for v in padrao if v in numericas])
                c1, c2, c3 = st.columns(3)
                met = c1.radio("Correlação", ["pearson", "spearman"], horizontal=True,
                               format_func=lambda s: {"pearson": "Pearson", "spearman": "Spearman"}[s])
                cat_cols = [c for c in df.columns if df[c].nunique() <= 30 and c not in vs]
                grupo = c2.selectbox("Agrupar por (tratamento)", ["(nenhum)"] + cat_cols)
                usar_med = c3.toggle("Usar médias dos tratamentos", value=False, disabled=grupo == "(nenhum)")
                filtro_col = st.selectbox("Filtrar (opcional)", ["(nenhum)"] + [c for c in cat_cols if c != grupo])
                dsel = df
                if filtro_col != "(nenhum)":
                    nv = st.selectbox("Nível", list(dict.fromkeys(df[filtro_col].astype(str))))
                    dsel = df[df[filtro_col].astype(str) == nv]
                if len(vs) >= 2 and st.button("Calcular correlações e PCA", type="primary"):
                    g = None if grupo == "(nenhum)" else grupo
                    ss.extras["correlacao"] = mv.correlacoes(dsel, vs, met, agrupar_por=g if usar_med else None)
                    if len(vs) >= 3:
                        ss.extras["pca"] = mv.pca(dsel, vs, grupo=g, usar_medias=usar_med)
                        ss.extras["pca_grupo"] = g
                    nova_versao()
                cat = catalogo(idioma)
                if ss.extras.get("correlacao") is not None:
                    cor = ss.extras["correlacao"]
                    titulo_secao(1, f"Correlação de {cor.metodo} ({cor.base})")
                    mostrar_figuras([cat["multi::correlacao"]], "cor")
                    tc = cor.tabela("pt").reset_index().rename(columns={"index": "Variável"})
                    tabela_ui(tc, "correlacoes", f"Correlação de {cor.metodo} ({cor.base})",
                              "* p < 0,05; ** p < 0,01; *** p < 0,001", "cor")
                if ss.extras.get("pca") is not None:
                    p = ss.extras["pca"]
                    titulo_secao(2, f"Componentes principais ({p.base})")
                    mostrar_figuras([cat["multi::pca"]], "pca")
                    c1, c2 = st.columns(2)
                    with c1:
                        tabela_ui(p.tabela_autovalores(), "pca_autovalores", "Autovalores e variância explicada", "",
                                  "pca_a")
                    with c2:
                        tabela_ui(p.tabela_cargas().reset_index().rename(columns={"index": "Variável"}), "pca_cargas",
                                  "Correlação entre variáveis e componentes", "", "pca_c")
            with m_ag:
                ua.secao_agrupamento(df, numericas, cat_todas, padrao, mostrar_figuras, idioma)
            with m_tr:
                ua.secao_trilha(df, numericas, cat_todas)


# ============================================================================
# Aba: Planejamento
# ============================================================================
if aba_plan.open:
    with aba_plan:
        ua.aba_planejamento()


# ============================================================================
# Aba: Downloads
# ============================================================================
if aba_down.open:
    with aba_down:
        if not ss.resultados:
            estilo.vazio("Nada para baixar ainda", "Execute a análise para gerar a planilha, o relatório, as figuras e o "
                         "arquivo de projeto.")
        else:
            ce = ss.config_exec
            grupos_nomes = list(dict.fromkeys(k[0] for k in ss.resultados))
            extras_tab = list(ss.tabelas_extra.values())
            titulo_secao(1, "Planilha de resultados (Excel)")
            st.caption("ANOVA com tamanhos de efeito, médias com letras, desdobramentos, regressões ranqueadas, "
                       "pressupostos e alternativas robustas, descritiva, correlações/PCA, contrastes, MEE, análise "
                       "conjunta, agrupamento e trilha (quando calculados) e rascunho de Métodos e Resultados.")
            cols_dl = st.columns(3)
            for n_g, g in enumerate(grupos_nomes):
                res_g = [r for (gg, v), r in ss.resultados.items() if gg == g and not isinstance(r, Exception)]
                erros = {v: str(r) for (gg, v), r in ss.resultados.items() if gg == g and isinstance(r, Exception)}
                if not res_g:
                    continue
                dados_g = dict(ce["grupos"])[g]
                nome = "resultados" + (f"_{relatorio._slug(g)}" if g else "") + ".xlsx"
                cols_dl[n_g % len(cols_dl)].download_button(
                    f"Excel{' — ' + g if g else ''}",
                    data=(lambda r=res_g, e=erros, dg=dados_g, ex=dict(ss.extras), op=ce["opcoes"]: exportar.gerar_excel(
                        r, op, idioma, extras={**ex, "erros": e, "tabelas": extras_tab},
                        dados_brutos=dg, com_ep=com_ep)),
                    file_name=nome, type="primary", width="stretch",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"xl_{g}")

            titulo_secao(2, "Relatório completo (Word)")
            st.caption("Material e Métodos, interpretação de cada variável, ANOVA e médias no padrão de periódico "
                       "(filetes 1,0/0,5 pt), figuras com legenda numerada e as análises complementares calculadas.")
            r1, r2, r3 = st.columns([3, 2, 2])
            tit_rel = r1.text_input("Título do relatório", value="Relatório de análise estatística", key="rel_tit")
            incl_fig = r2.toggle("Incluir figuras", value=True, key="rel_fig")
            fonte_rel = r3.selectbox("Fonte do documento", ["Roboto", "Arial", "Calibri", "Times New Roman"],
                                     key="rel_fonte")
            from ui_comum import tema_figura
            cols_rel = st.columns(3)
            for n_g, g in enumerate(grupos_nomes):
                res_g = [r for (gg, v), r in ss.resultados.items() if gg == g and not isinstance(r, Exception)]
                if not res_g:
                    continue
                cat = catalogo(idioma)
                itens_g = [it for it in cat.values() if it.grupo == g and it.variavel != "Multivariada"]
                temas_g = {it.id: tema_figura(it.id, it.spec.tipo) for it in itens_g}
                nome = "relatorio" + (f"_{relatorio._slug(g)}" if g else "") + ".docx"
                cols_rel[n_g % len(cols_rel)].download_button(
                    f"Word{' — ' + g if g else ''}",
                    data=(lambda r=res_g, it=itens_g, gg=g, tg=temas_g, op=ce["opcoes"]: relatorio_docx.gerar_relatorio(
                        r, op, it, lambda x: tg[x.id], idioma, fonte_rel,
                        tit_rel + (f" — {gg}" if gg else ""), incl_fig, com_ep, extras={"tabelas": extras_tab})),
                    file_name=nome, type="primary", width="stretch",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"doc_{g}")

            titulo_secao(3, "Pacote de figuras")
            st.caption("Cada figura sai com o tema global e os ajustes feitos no Estúdio.")
            formatos = st.multiselect("Formatos", ["png", "tiff", "svg", "pdf", "eps"], default=["png", "svg"],
                                      help="PNG e TIFF na resolução do tema (TIFF com LZW, RGB ou CMYK); SVG e EPS com "
                                           "texto editável ou em contornos; PDF vetorial com fontes embutidas.")
            incl_diag = st.toggle("Incluir gráficos de diagnóstico dos resíduos", value=False)
            if st.button("Gerar pacote (.zip)", key="gerar_zip"):
                from ui_comum import tema_figura
                import zipfile
                from motor import figuras as fg
                cat = catalogo(idioma)
                buf = io.BytesIO()
                barra = st.progress(0.0, text="Gerando figuras…")
                itens = [it for it in cat.values() if incl_diag or it.spec.tipo != "diagnostico"]
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                    for n_, it in enumerate(itens):
                        t = tema_figura(it.id, it.spec.tipo)
                        pasta = relatorio._slug(it.grupo) + "/" if it.grupo else ""
                        for fmt in formatos:
                            z.writestr(f"{pasta}{fmt}/{it.nome}.{fmt}", fg.gerar_arquivo(it.spec, t, fmt, idioma))
                        barra.progress((n_ + 1) / max(len(itens), 1), text=f"{it.titulo}")
                    z.writestr("tema_global.json", tm.para_json({**tm.PRESETS.get(ss.tema_preset, {}), **ss.tema_global}))
                barra.empty()
                ss.zip_figs = buf.getvalue()
            if ss.get("zip_figs"):
                st.download_button("Baixar figuras (.zip)", ss.zip_figs, file_name="figuras.zip", mime="application/zip")

            titulo_secao(4, "Projeto")
            st.caption("Um único arquivo com os dados, o delineamento, as opções, os modelos escolhidos, as exclusões e "
                       "todos os estilos de figura. Reabra pela barra lateral (Projeto) para continuar de onde parou.")
            nome_proj = relatorio._slug(str(ss.nome_arquivo or "projeto").split(":")[0].rsplit(".", 1)[0]) or "projeto"

            # valores capturados agora: o download roda fora da sessão (sem acesso ao session_state)
            cfg_p = dict(spec=ce["spec"], opcoes=ce["opcoes"], separar=ce.get("separar"), respostas=ce["respostas"])
            est_p = {k: ss.get(k) for k in ("transf_var", "modelo_escolhido", "rotulos_y", "tema_preset",
                                            "tema_global", "ajustes", "painel_cfg", "painel_tema", "excluir")}

            def _bytes_projeto(df_=ss.df, nome_=ss.nome_arquivo, cfg_=cfg_p, est_=est_p):
                return projeto.salvar(df_, nome_, cfg_, est_)
            st.download_button("Salvar projeto (.estatexp)", data=_bytes_projeto, file_name=f"{nome_proj}.estatexp",
                               mime="application/zip", type="primary", key="dl_proj")


# ============================================================================
# Aba: Guia
# ============================================================================
if aba_guia.open:
    with aba_guia:
        st.markdown("""
#### Delineamentos suportados
| Estrutura | DIC | DBC | DQL |
|---|---|---|---|
| Um fator | ✓ | ✓ | ✓ |
| Fatorial (2 a 4 fatores) | ✓ | ✓ | ✓ |
| Fatorial + tratamento(s) adicional(is) | ✓ | ✓ | ✓ |
| Parcelas subdivididas (tempo ou espaço), com fatorial na parcela ou subparcela | ✓ | ✓ | — |
| Parcelas sub-subdivididas | ✓ | ✓ | — |
| Faixas (strip-plot) | — | ✓ | — |

#### O que o motor faz
- **ANOVA** com somas de quadrados exatas; médias ajustadas e SQ tipo III em delineamentos de um estrato (aceita
  parcelas perdidas); cada efeito testado contra o erro do seu estrato em parcelas subdivididas e faixas.
- **Pressupostos**: Shapiro-Wilk, Anderson-Darling, Bartlett, Levene/Brown-Forsythe, não aditividade de Tukey,
  resíduos studentizados e Box-Cox.
- **Testes de médias**: Tukey (Tukey-Kramer), Scott-Knott, LSD, Duncan, SNK, Bonferroni e Dunnett, com desdobramento
  automático das interações (erro combinado e GL de Satterthwaite quando cruza estratos).
- **Regressão** (fatores quantitativos), em quatro famílias:
  - *Resposta a doses*: linear, quadrático, cúbico, raiz, logarítmico, Mitscherlich, linear-platô, quadrático-platô,
    exponencial, potência e Michaelis-Menten;
  - *Crescimento e acúmulo*: logístico, Gompertz e Weibull;
  - *Isotermas de adsorção*: Langmuir (com capacidade máxima de adsorção), Freundlich, Temkin e Sips;
  - *Cinéticas*: primeira ordem (Stanford & Smith / pseudo-1ª ordem, com meia-vida), pseudo-segunda ordem, Elovich,
    difusão parabólica e dois compartimentos.

  Os modelos são ranqueados por adequação e AICc. A coluna **Falta de ajuste** mostra o veredito do teste F:
  “não detectada ✓” (p alto) indica que a curva descreve bem as médias.

#### Estúdio de figuras
Cada figura pode ser ajustada em detalhe, com prévia ao vivo no tamanho exato em mm:
- **Ajuste rápido** (ao lado de cada gráfico em Resultados e na barra do Estúdio): tipo de gráfico, valores
  individuais ligados ou desligados, barra de erro, letras, paleta, largura e — nas regressões — o **modelo ajustado**
  de cada curva e a faixa de confiança/predição.
- **Tipos de gráfico de médias**: pontos, barras, box, meia-caixa + dados, violino, meio-violino + dados, raincloud,
  beeswarm e linhas (gráfico de interação). Rótulos com o valor das médias, contorno automático, hachuras com
  espessura ajustável.
- **Eixos**: escalas linear, log10, log2, ln e raiz quadrada; divisão por 10ⁿ com “(×10ⁿ)” no título; separador de
  milhar; direção e comprimento das marcas; eixos destacados; eixo quebrado; linha da média geral.
- **Texto formatado** em títulos, nomes e anotações: `kg ha^-1` → kg ha⁻¹, `P_{2}O_{5}` → P₂O₅,
  `*Crotalaria juncea*` → itálico, `\\alpha` → α, `\\deg` → °.
- **Anotações**: colchetes de significância, linhas de referência, faixas sombreadas (ex.: teor adequado), setas,
  retângulos, elipses e textos livres.
- **Regressão**: faixa de confiança (curva média) ou de predição (nova observação), em 90, 95 ou 99%.
- **Desfazer** cada alteração, **buscar opção** pelo nome e **copiar e colar formato** entre figuras escolhendo as
  partes (fontes, eixos, séries…), como no OriginPro.
- **Painel**: grade de até 4 × 4 com rótulos a/b/c, mesma escala de Y em todos os painéis e números internos ocultos.
- **Exportação**: PNG e TIFF (LZW, RGB ou CMYK) na resolução escolhida; SVG e EPS com texto editável ou em
  contornos; PDF vetorial com fontes embutidas.
- **Tema global**: o padrão de todas as figuras, que pode ser salvo e recarregado como arquivo .json.

#### Aparência
A plataforma tem dois temas — painel grafite (escuro) e bancada bege (claro) — escolhidos no menu ⋮ → *Settings* →
*Theme*. As figuras são sempre geradas em fundo branco, prontas para publicação.

#### Análises complementares (v2.1)
- **Tamanhos de efeito** na ANOVA: η²p e ω²p (ω²p é menos enviesado em amostras pequenas).
- **Intervalos de confiança** das médias e das diferenças par a par (simultâneos para Tukey, Bonferroni e Dunnett).
- **Pressupostos violados?** Na aba Pressupostos: ANOVA de Welch + Games-Howell (variâncias desiguais),
  Kruskal-Wallis + Dunn e Friedman + Conover (postos), com p ajustados por Holm; e exclusão de observações pelo
  número da linha da planilha, com reanálise imediata.
- **Contrastes** definidos por você (testemunha vs. demais, Helmert…), com estimativa, IC 95%, F e verificação de
  ortogonalidade, sobre tratamentos ou níveis de um fator; o erro respeita o estrato.
- **MEE** (máxima eficiência econômica) para modelos de dose, a partir dos preços do insumo e do produto.
- **Parcelas perdidas em parcelas subdivididas**: a análise passa automaticamente para modelo misto (REML), com F de
  Wald e GL por contenção; as linhas de erro mostram os componentes de variância.
- **Análise conjunta**: use “Analisar separadamente por” (local, safra) e abra a sub-aba Análise conjunta. Razão de
  Hartley < 7 indica homogeneidade; com ambientes aleatórios os tratamentos são testados contra a interação.
- **Multivariada**: agrupamento hierárquico (UPGMA, Ward…; corte de Mojena; dendrograma editável no Estúdio) e
  análise de trilha (efeitos diretos e indiretos, VIF, número de condição, opção em crista).
- **Planejamento**: repetições necessárias para um poder desejado e DMS esperada, a partir do CV.
- **Relatório Word** e **arquivo de projeto** na aba Downloads; o projeto reabre pela barra lateral.

#### Tabelas
Toda tabela tem botões **Excel** e **Word** no padrão de periódico: filetes de 1,0 pt acima e abaixo, 0,5 pt sob o
cabeçalho, sem linhas verticais e apenas o cabeçalho em negrito (no Excel, as espessuras equivalentes são “média”
e “fina”; no Word, exatas).
""")


# ============================================================================
# Cabeçalho com o estado de cada etapa (preenchido por último, aparece no topo)
# ============================================================================
def _etapas():
    if ss.df is None:
        return [("Dados", "aguardando", ""), ("Análise", "", ""), ("Figuras", "", "")]
    out = [("Dados", f"{len(ss.df)} linhas", "ok")]
    ok = [r for r in ss.resultados.values() if not isinstance(r, Exception)]
    erros = len(ss.resultados) - len(ok)
    if not ss.resultados:
        return out + [("Análise", "a executar", ""), ("Figuras", "", "")]
    out.append(("Análise", f"{len(ok)} variável(is)" + (f", {erros} com erro" if erros else ""),
                "alerta" if erros else "ok"))
    violados = sum(1 for r in ok if (r.pressupostos.ok_normalidade is False or r.pressupostos.ok_homogeneidade is False))
    out.append(("Pressupostos", "atendidos" if not violados else f"{violados} com alerta", "alerta" if violados else "ok"))
    n_aj = sum(1 for v in ss.ajustes.values() if v)
    out.append(("Figuras", f"{n_aj} ajustada(s)" if n_aj else "tema padrão", "ok"))
    return out


with _topo:
    estilo.cabecalho(_etapas())
