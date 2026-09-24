"""
Estatística Experimental — plataforma de análise de experimentos agronômicos.
Python + motor determinístico + Streamlit; entrada e saída em Excel.
"""
from __future__ import annotations

import io
import traceback
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from motor import __version__
from motor import exportar, graficos as gr, multivariada as mv, relatorio, templates, textos
from motor.anova import Opcoes, analisar
from motor.comparacoes import METODOS
from motor.exemplos import exemplo_para
from motor.modelo import (BASES, ESTRUTURAS, ErroDelineamento, Especificacao, Fator, TRANSFORMACOES,
                          rotulo_transformacao, sugerir_colunas)
from motor.regressao import CATALOGO, PADRAO

RAIZ = Path(__file__).resolve().parent
st.set_page_config(page_title="Estatística Experimental", page_icon=str(RAIZ / "assets" / "icone.png")
                   if (RAIZ / "assets" / "icone.png").exists() else None, layout="wide")

# ============================================================================
# Identidade visual
# ============================================================================
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Roboto:ital,wght@0,300;0,400;0,500;1,400&display=swap');
html, body, [class*="css"], .stMarkdown, .stText, button, input, textarea, select, label {
  font-family: 'Roboto', sans-serif !important; }
h1, h2, h3, h4 { font-family: 'Roboto', sans-serif !important; font-weight: 400 !important; color: #3E2A1E; }
h1 { letter-spacing: -0.3px; }
strong, b { font-weight: 500; }
.faixa-topo { height: 5px; border-radius: 3px; margin: 0.9rem 0 1.0rem 0;
  background: linear-gradient(90deg, #5B3A29 0%, #A6461E 30%, #D29A1C 55%, #3E8A45 80%, #2878A8 100%); }
.sub { color: #6B6B6B; font-size: 0.98rem; margin-top: -0.6rem; }
.papel { display:inline-block; padding: 2px 8px; margin: 2px 4px 2px 0; border-radius: 4px; font-size: 0.82rem;
  border: 1px solid #D9CFC4; }
table.esquema { border-collapse: collapse; font-size: 0.82rem; margin: 0.4rem 0 0.6rem 0; }
table.esquema th { font-weight: 400; padding: 4px 10px; border-top: 2px solid #3E2A1E; border-bottom: 1px solid #3E2A1E; }
table.esquema td { padding: 3px 10px; color: #333; }
table.esquema tr:last-child td { border-bottom: 2px solid #3E2A1E; }
.ok { color: #3E8A45; } .falha { color: #A6461E; }
div[data-testid="stMetricValue"] { font-weight: 300; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

logo = RAIZ / "assets" / "logo.png"
c_logo, c_tit = st.columns([1, 9]) if logo.exists() else (None, st.container())
if logo.exists():
    c_logo.image(str(logo), width="stretch")
with c_tit:
    st.markdown("# Estatística Experimental")
    st.markdown('<div class="sub">Análise de experimentos agronômicos — ANOVA, pressupostos, testes de médias, '
                'regressão, correlações e PCA, com tabelas e gráficos prontos para publicação</div>',
                unsafe_allow_html=True)
st.markdown('<div class="faixa-topo"></div>', unsafe_allow_html=True)

ss = st.session_state
for k, v in dict(df=None, nome_arquivo=None, resultados={}, config_exec=None, transf_var={}, modelo_escolhido={},
                 rotulos_y={}, extras={}, cache_figs={}).items():
    ss.setdefault(k, v)

# ============================================================================
# Barra lateral: delineamento e opções
# ============================================================================
with st.sidebar:
    st.markdown("### 1. Delineamento")
    base = st.radio("Casualização", list(BASES), index=1, format_func=lambda b: BASES[b], key="base")
    estruturas_validas = [e for e in ESTRUTURAS if not (base == "DQL" and e in ("subdividida", "subsubdividida", "faixas"))
                          and not (base == "DIC" and e == "faixas")]
    estrutura = st.selectbox("Estrutura dos tratamentos", estruturas_validas, format_func=lambda e: ESTRUTURAS[e],
                             key="estrutura")
    st.markdown("### 2. Análise")
    alfa = st.select_slider("Nível de significância (α)", [0.01, 0.05, 0.10], value=0.05)
    metodo = st.selectbox("Teste de médias", list(METODOS), format_func=lambda m: METODOS[m])
    transf = st.selectbox("Transformação (todas as variáveis)", list(TRANSFORMACOES),
                          format_func=lambda t: TRANSFORMACOES[t],
                          help="Também é possível aplicar a transformação sugerida pelo Box-Cox em cada variável, "
                               "na aba Pressupostos.")
    with st.expander("Opções avançadas"):
        comparar_q = st.toggle("Aplicar também teste de médias a fatores quantitativos", value=False)
        alfa_int = st.select_slider("α para desdobrar interações", [0.01, 0.05, 0.10], value=alfa)
        modelos = st.multiselect("Modelos de regressão candidatos", PADRAO, default=PADRAO,
                                 format_func=lambda c: CATALOGO[c].nome)
        com_ep = st.toggle("Tabelas com média ± erro-padrão", value=True)
    st.markdown("### 3. Gráficos")
    largura = st.selectbox("Largura", list(gr.LARGURAS), index=0)
    estilo_g = st.radio("Estilo das médias", ["pontos", "barras"], horizontal=True,
                        format_func=lambda s: {"pontos": "Pontos", "barras": "Barras"}[s])
    erro_g = st.radio("Barra de erro", ["ep", "dp", "ic95"], horizontal=True,
                      format_func=lambda s: {"ep": "Erro-padrão", "dp": "Desvio-padrão", "ic95": "IC 95%"}[s])
    mostrar_obs = st.toggle("Mostrar observações individuais", value=True)
    alfa_obs = st.slider("Transparência das observações", 0.1, 1.0, 0.45, 0.05)
    fonte_pt = st.select_slider("Corpo do texto (pt)", [6, 6.5, 7, 7.5, 8, 9], value=7)
    idioma = st.radio("Idioma das saídas", ["pt", "en"], horizontal=True,
                      format_func=lambda s: {"pt": "Português", "en": "English"}[s])
    st.caption(f"Motor v{__version__} · resultados determinísticos")

cfg = gr.ConfigGrafico(largura_mm=gr.LARGURAS[largura], estilo=estilo_g, erro=erro_g, mostrar_obs=mostrar_obs,
                       alfa_obs=alfa_obs, fonte_pt=fonte_pt, idioma=idioma)
opcoes_base = dict(alfa=alfa, metodo=metodo, transformacao=transf, comparar_quantitativos=comparar_q,
                   alfa_interacao=alfa_int, modelos_regressao=modelos or None)

aba_dados, aba_res, aba_multi, aba_down, aba_guia = st.tabs(
    ["Dados e modelo", "Resultados", "Correlações e PCA", "Downloads", "Guia"])


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


def fmt_tabela(df: pd.DataFrame, p_cols=("p",)):
    out = df.copy()
    for c in out.columns:
        if c in p_cols:
            out[c] = [("< 0,0001" if v < 1e-4 else f"{v:.4f}".replace(".", ",")) if isinstance(v, (float, np.floating))
                      and np.isfinite(v) else "" for v in out[c]]
        elif pd.api.types.is_numeric_dtype(out[c]) and out[c].dropna().apply(lambda v: float(v).is_integer()).all() \
                and c in ("GL", "n", "#", "GL erro", "Linha na planilha"):
            out[c] = [f"{int(v)}" if pd.notna(v) else "" for v in out[c]]
        elif pd.api.types.is_numeric_dtype(out[c]):
            def f(v):
                if v is None or not np.isfinite(v):
                    return ""
                d = exportar._decimais(v)
                return exportar._fmt_str(v, d, "pt")
            out[c] = [f(v) for v in out[c]]
    return out


def anova_df(res):
    return exportar._tabela_anova(res, "pt").reset_index()


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
            bloco = st.selectbox(rot, colunas, index=idx, key="w_bloco")
        if base == "DQL":
            linha = st.selectbox("Coluna de linhas", colunas,
                                 index=colunas.index(sug["linha"]) if sug["linha"] in colunas else 0, key="w_lin")
            coluna = st.selectbox("Coluna de colunas", colunas,
                                  index=colunas.index(sug["coluna"]) if sug["coluna"] in colunas else 0, key="w_col")
        if estrutura == "fatorial_adicional":
            trat = st.selectbox("Coluna com o nome de cada tratamento", colunas, key="w_trat",
                                index=colunas.index(sug["tratamento"]) if sug["tratamento"] in colunas else 0,
                                help="Nos tratamentos adicionais, as colunas dos fatores devem estar vazias.")
    usados = {bloco, linha, coluna, trat}
    cand = [c for c in colunas if c not in usados]
    sug_f = [c for c in sug["fatores"] if c in cand]
    with c2:
        if estrutura == "simples":
            f1 = st.selectbox("Fator (tratamentos)", cand, index=cand.index(sug_f[0]) if sug_f else 0, key="w_f1")
            escolha = [(f1, 1)]
        elif estrutura in ("fatorial", "fatorial_adicional"):
            fs = st.multiselect("Fatores do fatorial (2 a 4)", cand, default=sug_f[:2], key="w_fat", max_selections=4)
            escolha = [(c, 1) for c in fs]
        elif estrutura == "faixas":
            fa = st.selectbox("Fator nas faixas horizontais", cand, key="w_fa")
            fb = st.selectbox("Fator nas faixas verticais", [c for c in cand if c != fa], key="w_fb")
            escolha = [(fa, 1), (fb, 2)]
        else:
            niveis = 3 if estrutura == "subsubdividida" else 2
            nomes = {1: "Fator(es) na parcela", 2: "Fator(es) na subparcela", 3: "Fator(es) na sub-subparcela"}
            escolha = []
            restante = list(cand)
            for n in range(1, niveis + 1):
                pad = [c for c in sug_f if c in restante][:1]
                fs = st.multiselect(nomes[n], restante, default=pad, key=f"w_nivel{n}")
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
            rot = k1.text_input(f"Rótulo de '{col}'", value=str(col), key=f"rot_{col}")
            q = k2.toggle("Quantitativo (regressão)", value=sug_q, key=f"q_{col}", disabled=not numerico,
                          help="Doses, épocas, idades… Habilita o ajuste de modelos de regressão.")
            un = k3.text_input("Unidade (eixo x)", value="", key=f"un_{col}", placeholder="ex.: kg ha⁻¹") if q else ""
            fatores.append(Fator(col, rot, n, q, un))
    return Especificacao(base=base, estrutura=estrutura, fatores=fatores, bloco=bloco, linha=linha, coluna=coluna,
                         tratamento=trat), [c for c in colunas if c not in usados | {c for c, _ in escolha}]


# ============================================================================
# Aba: Dados e modelo
# ============================================================================
with aba_dados:
    tpl_bytes, tpl_df, tpl_pap = templates.gerar_template(base, estrutura)
    with st.expander("Como organizar a planilha — modelo para este delineamento", expanded=ss.df is None):
        st.markdown(f"**{BASES[base]} — {ESTRUTURAS[estrutura].lower()}.** Formato longo: **uma linha por unidade "
                    "experimental** (parcela, vaso ou subparcela), uma coluna para cada fator, uma para bloco/repetição "
                    "e uma para cada variável-resposta.")
        st.html(esquema_html(tpl_df, tpl_pap))
        gerais, esp = templates.instrucoes(base, estrutura)
        cA, cB = st.columns(2)
        cA.markdown("**Regras gerais**\n\n" + "\n".join(f"- {g}" for g in gerais[:5]))
        cB.markdown("**Neste delineamento**\n\n" + "\n".join(f"- {g}" for g in esp + gerais[5:]))
        b1, b2, _ = st.columns([2, 2, 4])
        b1.download_button("Baixar modelo em Excel", tpl_bytes, file_name=f"modelo_{base}_{estrutura}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
        if b2.button("Carregar este exemplo"):
            df_ex, spec_ex, resp_ex = exemplo_para(base, estrutura)
            ss.df, ss.nome_arquivo = df_ex, f"exemplo_{base}_{estrutura}.xlsx"
            ss.resultados = {}
            st.rerun()

    up = st.file_uploader("Planilha de dados (.xlsx, .xls ou .csv)", type=["xlsx", "xls", "csv", "txt"])
    if up is not None:
        conteudo = up.getvalue()
        _, abas = ler_planilha(conteudo, up.name)
        aba = st.selectbox("Aba", abas) if abas and len(abas) > 1 else None
        df_novo, _ = ler_planilha(conteudo, up.name, aba)
        if ss.nome_arquivo != f"{up.name}:{aba}":
            ss.df, ss.nome_arquivo, ss.resultados = df_novo, f"{up.name}:{aba}", {}
    df = ss.df
    if df is None:
        st.info("Envie sua planilha ou carregue o exemplo acima para começar.")
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
        respostas = st.multiselect("Variáveis-resposta", num_livres, default=padrao_resp, key="w_resp")
        cS1, cS2 = st.columns([1, 1])
        sep_opts = ["(nenhuma)"] + [c for c in livres if c not in respostas and df[c].nunique() <= 20]
        separar = cS1.selectbox("Analisar separadamente por", sep_opts,
                                help="Ex.: rodar a análise para cada camada, local ou safra separadamente.")
        executar = cS2.button("Executar análise", type="primary", width="stretch",
                              disabled=spec is None or not respostas)
        if executar and spec is not None:
            try:
                spec.validar(df)
            except ErroDelineamento as e:
                st.error(str(e))
                st.stop()
            grupos = [(None, df)]
            if separar != "(nenhuma)":
                grupos = [(f"{separar} = {g}", d.reset_index(drop=True)) for g, d in df.groupby(separar, sort=False)]
            resultados = {}
            barra = st.progress(0.0, text="Analisando…")
            tot = len(grupos) * len(respostas)
            i = 0
            for nome_g, d in grupos:
                for v in respostas:
                    t_ = ss.transf_var.get(v, transf)
                    op = Opcoes(**{**opcoes_base, "transformacao": t_})
                    try:
                        resultados[(nome_g, v)] = analisar(d, spec, v, op)
                    except ErroDelineamento as e:
                        resultados[(nome_g, v)] = e
                    except Exception as e:  # erro inesperado: registra para diagnóstico
                        e.detalhe = traceback.format_exc()
                        resultados[(nome_g, v)] = e
                    i += 1
                    barra.progress(i / tot, text=f"Analisando {v}…")
            barra.empty()
            ss.resultados = resultados
            ss.config_exec = dict(spec=spec, opcoes=Opcoes(**opcoes_base), separar=separar, grupos=grupos,
                                  respostas=respostas)
            ss.cache_figs = {}
            ss.extras = {}
            n_ok = sum(not isinstance(r, Exception) for r in resultados.values())
            st.success(f"{n_ok} de {len(resultados)} análise(s) concluída(s). Veja a aba Resultados.")
            for (g, v), r in resultados.items():
                if isinstance(r, Exception):
                    st.error(f"{v}{' — ' + g if g else ''}: {r}")


# ============================================================================
# Aba: Resultados
# ============================================================================
def figuras_cache(chave, res, rotulo_y, perfil, modelos_esc):
    k = (chave, tuple(sorted(cfg.__dict__.items(), key=lambda x: x[0])).__str__(), rotulo_y, perfil,
         tuple(sorted(modelos_esc.items())))
    if len(ss.cache_figs) > 40:
        ss.cache_figs = {}
    if k not in ss.cache_figs:
        # aplica escolhas manuais de modelo
        for fa in res.fatias:
            ce = modelos_esc.get(chave_fatia(fa))
            if fa.regressao and ce:
                alvo = [a for a in fa.regressao.ajustes if a.codigo == ce]
                if alvo:
                    fa.regressao.melhor = alvo[0]
        figs = relatorio.figuras_para(res, cfg, rotulo_y, perfil)
        saida = []
        for nome, titulo, fig in figs:
            saida.append((nome, titulo, gr.png_preview(fig, 200), gr.exportar(fig, cfg, ("png", "svg", "pdf", "tiff"))))
            plt.close(fig)
        ss.cache_figs[k] = saida
    return ss.cache_figs[k]


def fig_cache(chave, construtor):
    """Gera (uma vez por configuração) a prévia e os arquivos de uma figura avulsa."""
    k = ("avulsa", chave, str(sorted(cfg.__dict__.items(), key=lambda x: x[0])))
    if k not in ss.cache_figs:
        fig = construtor()
        ss.cache_figs[k] = (gr.png_preview(fig, 180), gr.exportar(fig, cfg, ("png", "svg", "pdf", "tiff")))
        plt.close(fig)
    return ss.cache_figs[k]


def botoes_download_fig(arqs, nome, chave, vertical=True):
    mimes = {"png": "image/png", "svg": "image/svg+xml", "pdf": "application/pdf", "tiff": "image/tiff"}
    rot = {"png": "PNG 600 dpi", "svg": "SVG editável", "pdf": "PDF vetorial", "tiff": "TIFF 600 dpi"}
    alvos = [st.container() for _ in arqs] if vertical else st.columns(4)
    for c, (ext, dados) in zip(alvos, arqs.items()):
        c.download_button(rot[ext], dados, file_name=f"{nome}.{ext}", mime=mimes[ext], key=f"dl_{chave}_{ext}",
                          width="stretch")


with aba_res:
    if not ss.resultados:
        st.info("Execute a análise na aba Dados e modelo.")
    else:
        chaves = list(ss.resultados)
        rotulo_ch = lambda k: k[1] + (f"  ·  {k[0]}" if k[0] else "")
        i_sel = st.selectbox("Variável", list(range(len(chaves))), format_func=lambda i: rotulo_ch(chaves[i]))
        sel = chaves[i_sel]
        res = ss.resultados[sel]
        if isinstance(res, Exception):
            st.error(str(res))
            if hasattr(res, "detalhe"):
                with st.expander("Detalhes técnicos"):
                    st.code(res.detalhe)
        else:
            spec = res.spec
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Média geral", exportar._fmt_str(res.media_geral, exportar._decimais(res.media_geral), "pt"))
            cvs = list(res.cv.items())
            m2.metric(cvs[0][0].replace(" [escala transformada]", ""), exportar._fmt_str(cvs[0][1], 2, "pt"))
            if len(cvs) > 1:
                m3.metric(cvs[1][0].replace(" [escala transformada]", ""), exportar._fmt_str(cvs[1][1], 2, "pt"))
            else:
                m3.metric("R² do modelo", exportar._fmt_str(res.r2, 3, "pt"))
            pr = res.pressupostos
            estado = ("atendidos" if (pr.ok_normalidade is not False and pr.ok_homogeneidade is not False)
                      else "violados")
            m4.metric("Pressupostos", estado)
            for a in res.avisos:
                st.warning(a)
            if res.transformacao:
                st.info(f"Transformação aplicada: {rotulo_transformacao(res.transformacao)}")

            t_anova, t_med, t_reg, t_pres, t_txt = st.tabs(["ANOVA", "Médias e gráficos", "Regressão", "Pressupostos", "Texto"])
            with t_anova:
                st.dataframe(fmt_tabela(anova_df(res), p_cols=("p",)), hide_index=True, width="stretch")
                st.caption("; ".join(f"{k} = {exportar._fmt_str(v, 2, 'pt')}" for k, v in res.cv.items())
                           + f" · R² = {exportar._fmt_str(res.r2, 3, 'pt')} · ns: p ≥ {str(alfa).replace('.', ',')}; * p < 0,05; ** p < 0,01; *** p < 0,001")
                if res.desdobramento:
                    st.markdown("**Desdobramento da interação**")
                    d = pd.DataFrame(res.desdobramento)
                    d[" "] = [textos.estrela(p) for p in d["p"]]
                    st.dataframe(fmt_tabela(d, ("p",)), hide_index=True, width="stretch")
                    if spec.multiestrato:
                        st.caption("Desdobramentos que combinam estratos usam erro combinado com GL de Satterthwaite.")
                for fa in res.fatias:
                    if fa.polinomial:
                        cond = ", ".join(f"{spec.fatores[k].rotulo} = {v}" for k, v in fa.condicao.items())
                        st.markdown(f"**Decomposição polinomial — {spec.fatores[fa.fator].rotulo}**" + (f" ({cond})" if cond else ""))
                        d = pd.DataFrame(fa.polinomial)
                        d[" "] = [textos.estrela(p) for p in d["p"]]
                        st.dataframe(fmt_tabela(d, ("p",)), hide_index=True, width="stretch")

            with t_med:
                cfg_col, _ = st.columns([2, 3])
                rot_padrao = ss.rotulos_y.get(sel[1], sel[1])
                ss.rotulos_y[sel[1]] = cfg_col.text_input("Rótulo do eixo Y", value=rot_padrao, key=f"roty_{sel}",
                                                          help="Use sobrescritos Unicode para unidades: ⁻¹ ⁻² ⁻³ ² ³")
                camadas = [i for i, f in enumerate(spec.fatores) if relatorio.parece_camada(f.coluna) or relatorio.parece_camada(f.rotulo)]
                perfil = None
                if camadas:
                    if cfg_col.toggle(f"Gráfico em perfil para '{spec.fatores[camadas[0]].rotulo}'", value=True, key=f"perf_{sel}"):
                        perfil = camadas[0]
                modelos_esc = ss.modelo_escolhido.get(sel, {})
                figs = figuras_cache(sel, res, ss.rotulos_y[sel[1]], perfil, modelos_esc)
                # tabelas de médias
                for fa in res.fatias:
                    cond = ", ".join(f"{spec.fatores[k].rotulo} = {v}" for k, v in fa.condicao.items())
                    sig = fa.p is not None and fa.p < res.alfa
                    tit = f"{spec.fatores[fa.fator].rotulo}" + (f" — {cond}" if cond else "")
                    with st.expander(f"Médias: {tit}  ·  F = {exportar._fmt_str(fa.f, 2, 'pt')}; "
                                     f"{textos._p(fa.p)} {'' if sig else '(ns)'}",
                                     expanded=False):
                        d = pd.DataFrame({"Nível": fa.niveis, "Média": fa.medias_orig, "EP": fa.ep_dados, "n": fa.n})
                        if fa.comparacao is not None:
                            d["Letras" if fa.comparacao.metodo != "dunnett" else "Dunnett"] = (
                                fa.comparacao.letras if sig else [""] * len(fa.niveis))
                        st.dataframe(fmt_tabela(d), hide_index=True, width="stretch")
                        if fa.comparacao is not None and fa.comparacao.dms:
                            st.caption(f"DMS = {exportar._fmt_str(fa.comparacao.dms, exportar._decimais(fa.comparacao.dms), 'pt')}"
                                       f"; GL do erro = {exportar._fmt_str(fa.gl, 1, 'pt')}")
                for td in res.tabelas_duplas:
                    st.markdown(f"**Interação {td['linhas']} × {td['colunas']}** — minúsculas comparam "
                                f"{td['linhas']} na coluna; maiúsculas comparam {td['colunas']} na linha")
                    med, ep, let = td["medias"], td["ep"], td["letras"]
                    dec = exportar._decimais(np.nanmean(np.abs(med.to_numpy(float))))
                    tab = pd.DataFrame({b: [exportar._celula_media(med.loc[a, b], ep.loc[a, b],
                                                                   let.loc[a, b].replace(" ", ""), "pt", True, dec)
                                            for a in med.index] for b in med.columns}, index=med.index)
                    st.dataframe(tab, width="stretch")
                st.markdown("#### Gráficos")
                for i, (nome, titulo, png, arqs) in enumerate(figs):
                    st.markdown(f"**{titulo}**")
                    ci, cb = st.columns([3, 1])
                    ci.image(png, width="stretch" if cfg.largura_mm > 120 else "content")
                    with cb:
                        st.caption("Baixar")
                        botoes_download_fig(arqs, nome, f"{sel}_{i}")

            with t_reg:
                tem = [fa for fa in res.fatias if fa.regressao]
                if not tem:
                    st.info("Nenhum fator quantitativo com 3 ou mais níveis. Marque o fator como quantitativo na aba Dados.")
                for fa in tem:
                    cond = ", ".join(f"{spec.fatores[k].rotulo} = {v}" for k, v in fa.condicao.items())
                    st.markdown(f"**{spec.fatores[fa.fator].rotulo}**" + (f" — {cond}" if cond else ""))
                    if fa.p is not None and fa.p >= res.alfa:
                        st.caption("Efeito não significativo pelo teste F: a resposta é representada pela média; "
                                   "os ajustes são apenas descritivos.")
                    linhas = []
                    for a in fa.regressao.ajustes:
                        linhas.append({"#": a.rank, "Modelo": a.nome, "Equação": a.equacao("pt"), "R²": a.r2,
                                       "AICc": a.aicc, "ΔAICc": a.delta_aicc, "Peso": a.peso,
                                       "p (falta de ajuste)": a.p_falta, "Adequado": "sim" if a.adequado else "não",
                                       "Observação": a.motivo})
                    d = pd.DataFrame(linhas)
                    st.dataframe(fmt_tabela(d, ("p (falta de ajuste)",)), hide_index=True, width="stretch")
                    opcoes_m = [a.codigo for a in fa.regressao.ajustes if a.convergiu]
                    atual = ss.modelo_escolhido.get(sel, {}).get(chave_fatia(fa))
                    padrao = fa.regressao.melhor.codigo if fa.regressao.melhor else (opcoes_m[0] if opcoes_m else None)
                    if opcoes_m:
                        esc = st.selectbox("Modelo usado no gráfico e no texto", opcoes_m,
                                           index=opcoes_m.index(atual or padrao) if (atual or padrao) in opcoes_m else 0,
                                           format_func=lambda c: CATALOGO[c].nome, key=f"mod_{sel}_{chave_fatia(fa)}")
                        if esc != (atual or padrao):
                            ss.modelo_escolhido.setdefault(sel, {})[chave_fatia(fa)] = esc
                            st.rerun()
                        m = [a for a in fa.regressao.ajustes if a.codigo == esc][0]
                        pts = {k: v for k, v in m.pontos.items() if not isinstance(v, bool)}
                        if pts:
                            st.caption(" · ".join(f"{k}: {exportar._fmt_str(v, exportar._decimais(v), 'pt')}" for k, v in pts.items()))
                    if fa.regressao.nota:
                        st.caption(fa.regressao.nota)

            with t_pres:
                tb = pr.tabela()
                tb["Situação"] = ["✓" if t.ok else ("✗" if t.ok is False else "") for t in pr.testes]
                st.dataframe(fmt_tabela(tb, ("p",)), hide_index=True, width="stretch")
                if len(pr.outliers):
                    st.markdown("**Possíveis valores discrepantes** (confira a digitação antes de excluir)")
                    st.dataframe(fmt_tabela(pr.outliers), hide_index=True)
                if pr.recomendacao:
                    st.warning(pr.recomendacao)
                if pr.boxcox and pr.boxcox.get("codigo"):
                    cbx1, cbx2 = st.columns([3, 1])
                    cbx1.caption(f"Box-Cox: λ̂ = {pr.boxcox['lambda_hat']:.2f} "
                                 f"(IC 95%: {pr.boxcox['ic95'][0]:.2f} a {pr.boxcox['ic95'][1]:.2f})".replace(".", ","))
                    if cbx2.button("Aplicar sugestão e reanalisar", key=f"bc_{sel}"):
                        ss.transf_var[sel[1]] = pr.boxcox["codigo"]
                        ce = ss.config_exec
                        d = dict(ce["grupos"])[sel[0]]
                        op = Opcoes(**{**opcoes_base, "transformacao": pr.boxcox["codigo"]})
                        try:
                            ss.resultados[sel] = analisar(d, ce["spec"], sel[1], op)
                        except Exception as e:
                            ss.resultados[sel] = e
                        ss.cache_figs = {}
                        st.rerun()
                if res.transformacao and st.button("Remover transformação desta variável", key=f"rt_{sel}"):
                    ss.transf_var.pop(sel[1], None)
                    ce = ss.config_exec
                    d = dict(ce["grupos"])[sel[0]]
                    ss.resultados[sel] = analisar(d, ce["spec"], sel[1], Opcoes(**{**opcoes_base, "transformacao": None}))
                    ss.cache_figs = {}
                    st.rerun()
                png_d, arq_d = fig_cache(("diag", sel, res.transformacao), lambda: relatorio.fig_diagnostico(res, cfg))
                st.image(png_d, width="stretch")
                botoes_download_fig(arq_d, f"diagnostico_{relatorio._slug(sel[1])}", f"diag_{sel}", vertical=False)

            with t_txt:
                st.markdown("**Resultados (rascunho)**")
                st.text_area("Interpretação", textos.interpretar(res, idioma), height=220, key=f"txt_{sel}_{idioma}",
                             label_visibility="collapsed")
                st.markdown("**Material e Métodos (rascunho)**")
                st.text_area("Métodos", textos.metodos(spec, Opcoes(**opcoes_base), [res], idioma), height=200,
                             key=f"met_{sel}_{idioma}", label_visibility="collapsed")
                st.caption("Texto gerado deterministicamente a partir dos resultados — revise antes de usar.")


# ============================================================================
# Aba: Correlações e PCA
# ============================================================================
with aba_multi:
    if ss.df is None:
        st.info("Carregue os dados primeiro.")
    else:
        df = ss.df
        numericas = [c for c in df.columns if pd.to_numeric(df[c], errors="coerce").notna().mean() > 0.8
                     and df[c].nunique() > 5]
        padrao = (ss.config_exec or {}).get("respostas") or numericas[:6]
        vs = st.multiselect("Variáveis", numericas, default=[v for v in padrao if v in numericas])
        c1, c2, c3 = st.columns(3)
        met = c1.radio("Correlação", ["pearson", "spearman"], horizontal=True,
                       format_func=lambda s: {"pearson": "Pearson", "spearman": "Spearman"}[s])
        cat = [c for c in df.columns if df[c].nunique() <= 30 and c not in vs]
        grupo = c2.selectbox("Agrupar por (tratamento)", ["(nenhum)"] + cat)
        usar_med = c3.toggle("Usar médias dos tratamentos", value=False, disabled=grupo == "(nenhum)")
        filtro_col = st.selectbox("Filtrar (opcional)", ["(nenhum)"] + [c for c in cat if c != grupo])
        dsel = df
        if filtro_col != "(nenhum)":
            nv = st.selectbox("Nível", list(dict.fromkeys(df[filtro_col].astype(str))))
            dsel = df[df[filtro_col].astype(str) == nv].reset_index(drop=True)
        if len(vs) >= 2 and st.button("Calcular correlações e PCA", type="primary"):
            g = None if grupo == "(nenhum)" else grupo
            cor = mv.correlacoes(dsel, vs, met, agrupar_por=g if usar_med else None)
            ss.extras["correlacao"] = cor
            if len(vs) >= 3:
                ss.extras["pca"] = mv.pca(dsel, vs, grupo=g, usar_medias=usar_med)
                ss.extras["pca_grupo"] = g
        if ss.extras.get("correlacao") is not None:
            cor = ss.extras["correlacao"]
            st.markdown(f"#### Correlação de {cor.metodo} ({cor.base})")
            cfg_c = gr.ConfigGrafico(**{**cfg.__dict__, "largura_mm": max(cfg.largura_mm, 120)})
            png_c, arq_c = fig_cache(("cor", id(cor)), lambda: gr.fig_correlacao(cor.R, cor.P, cor.nomes, cfg_c, cor.metodo))
            a, b = st.columns([3, 1])
            a.image(png_c, width="stretch")
            with b:
                botoes_download_fig(arq_c, "correlacao", "cor")
            st.dataframe(cor.tabela("pt"), width="stretch")
        if ss.extras.get("pca") is not None:
            p = ss.extras["pca"]
            st.markdown(f"#### Componentes principais ({p.base})")
            cfg_p = gr.ConfigGrafico(**{**cfg.__dict__, "largura_mm": max(cfg.largura_mm, 120)})
            png_p, arq_p = fig_cache(("pca", id(p)), lambda: gr.fig_pca(
                p.escores, p.cargas, p.nomes, p.grupos, p.explicada, cfg_p, titulo_legenda=ss.extras.get("pca_grupo"),
                rotulos_pontos=p.rotulos_linhas if p.base.startswith("médias") else None))
            a, b = st.columns([3, 1])
            a.image(png_p, width="stretch")
            with b:
                botoes_download_fig(arq_p, "pca_biplot", "pca")
            c1, c2 = st.columns(2)
            c1.dataframe(fmt_tabela(p.tabela_autovalores()), hide_index=True, width="stretch")
            c2.dataframe(fmt_tabela(p.tabela_cargas().reset_index().rename(columns={"index": "Variável"})),
                         hide_index=True, width="stretch")


# ============================================================================
# Aba: Downloads
# ============================================================================
with aba_down:
    if not ss.resultados:
        st.info("Execute a análise para gerar os arquivos.")
    else:
        ce = ss.config_exec
        grupos_nomes = list(dict.fromkeys(k[0] for k in ss.resultados))
        st.markdown("#### Planilha de resultados")
        st.caption("ANOVA, médias com letras, desdobramentos, regressões ranqueadas, pressupostos, estatística "
                   "descritiva, correlações/PCA (se calculadas) e rascunho de Métodos e Resultados.")
        for g in grupos_nomes:
            res_g = [r for (gg, v), r in ss.resultados.items() if gg == g and not isinstance(r, Exception)]
            erros = {v: str(r) for (gg, v), r in ss.resultados.items() if gg == g and isinstance(r, Exception)}
            if not res_g:
                continue
            dados_g = dict(ce["grupos"])[g]
            xls = exportar.gerar_excel(res_g, ce["opcoes"], idioma, extras={**ss.extras, "erros": erros},
                                       dados_brutos=dados_g, com_ep=com_ep)
            nome = "resultados" + (f"_{relatorio._slug(g)}" if g else "") + ".xlsx"
            st.download_button(f"Baixar Excel{' — ' + g if g else ''}", xls, file_name=nome, type="primary",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"xl_{g}")
        st.markdown("#### Pacote de figuras")
        formatos = st.multiselect("Formatos", ["png", "svg", "pdf", "tiff"], default=["png", "svg"],
                                  help="PNG e TIFF em 600 dpi; SVG com texto editável; PDF vetorial.")
        incl_diag = st.toggle("Incluir gráficos de diagnóstico dos resíduos", value=False)
        if st.button("Gerar pacote (.zip)"):
            itens = []
            with st.spinner("Gerando figuras…"):
                for (g, v), r in ss.resultados.items():
                    if isinstance(r, Exception):
                        continue
                    camadas = [i for i, f in enumerate(r.spec.fatores)
                               if relatorio.parece_camada(f.coluna) or relatorio.parece_camada(f.rotulo)]
                    for nome, titulo, fig in relatorio.figuras_para(r, cfg, ss.rotulos_y.get(v, v),
                                                                    camadas[0] if camadas else None):
                        itens.append((g or "", nome, fig))
                    if incl_diag:
                        itens.append((g or "", f"diagnostico_{relatorio._slug(v)}", relatorio.fig_diagnostico(r, cfg)))
                ss.zip_figs = relatorio.zip_figuras(itens, cfg, formatos)
        if ss.get("zip_figs"):
            st.download_button("Baixar figuras (.zip)", ss.zip_figs, file_name="figuras.zip", mime="application/zip")


# ============================================================================
# Aba: Guia
# ============================================================================
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
- **ANOVA** com somas de quadrados exatas. Em delineamentos de um estrato, usa médias ajustadas (mínimos quadrados) e
  testes equivalentes à SQ tipo III, válidos também com parcelas perdidas. Em parcelas subdivididas e faixas, cada
  efeito é testado contra o erro do seu estrato.
- **Pressupostos**: Shapiro-Wilk e Anderson-Darling (normalidade dos resíduos), Bartlett e Levene/Brown-Forsythe
  (homogeneidade), não aditividade de Tukey (DBC), resíduos studentizados > 3 (discrepantes) e Box-Cox (sugestão de transformação).
- **Testes de médias**: Tukey (Tukey-Kramer se desbalanceado), Scott-Knott, LSD, Duncan, SNK, Bonferroni e Dunnett.
- **Interações**: desdobramento automático de cada fator dentro dos níveis dos fatores com que interage. Quando o
  desdobramento cruza estratos de erro, usa o erro combinado com GL de Satterthwaite.
- **Regressão** para fatores quantitativos: decomposição polinomial na ANOVA e 12 modelos candidatos (linear,
  quadrático, cúbico, raiz quadrada, logarítmico, Mitscherlich, linear-platô, quadrático-platô, exponencial, potência,
  Michaelis-Menten e logístico), ranqueados por adequação (falta de ajuste, significância dos parâmetros,
  plausibilidade) e AICc, com pontos notáveis (máxima eficiência técnica, platô, doses para 90/95% do máximo).
- **Fatorial + adicional**: decomposição de tratamentos em fatorial, fatorial vs. adicional(is) e entre adicionais,
  comparação de todos os tratamentos e Dunnett contra cada testemunha.

#### Gráficos
Roboto, 7 pt no tamanho final, sem grade e sem negrito, barras de erro-padrão, observações semitransparentes,
larguras de coluna de periódico (89/120/183 mm). PNG e TIFF em 600 dpi, SVG com texto editável e PDF vetorial.
A paleta de cores foi validada para daltonismo e todos os grupos também são diferenciados pela forma do marcador.
""")
