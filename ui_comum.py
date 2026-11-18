"""
Estado e utilidades compartilhadas da interface (temas por figura, catálogo
de figuras, cache de prévias e tabelas com download em Excel/Word).
"""

from __future__ import annotations

REVISAO = "3.0.0"   # conferida pelo app.py para descartar módulos antigos em memória

import hashlib
import json

import numpy as np
import pandas as pd
import streamlit as st

from motor import exportar, figuras as fg, relatorio, tabelas, tema as tm

ss = st.session_state

MIMES = {"png": "image/png", "svg": "image/svg+xml", "pdf": "application/pdf", "tiff": "image/tiff",
         "eps": "application/postscript",
         "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
         "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
ROT_FMT = {"png": "PNG", "svg": "SVG", "pdf": "PDF", "tiff": "TIFF", "eps": "EPS"}


def iniciar_estado():
    padrao = dict(df=None, nome_arquivo=None, resultados={}, config_exec=None, transf_var={}, modelo_escolhido={},
                  rotulos_y={}, extras={}, cache_figs={}, tema_preset="Solos (padrão da plataforma)",
                  tema_global={}, ajustes={}, versao=0, estudio_fig=None, painel_cfg=None, perfil_auto=True,
                  excluir={}, tabelas_extra={}, pasta=[], cache_arq={}, cache_tab={},
                  arquivos_prontos={})
    for k, v in padrao.items():
        ss.setdefault(k, v)


def nova_versao():
    ss.versao = ss.get("versao", 0) + 1
    ss.cache_figs = {}
    ss.cache_arq = {}
    ss.arquivos_prontos = {}


# ----------------------------------------------------------------------------
# Temas
# ----------------------------------------------------------------------------
def tema_base():
    return tm.resolver(tm.PRESETS.get(ss.tema_preset, {}), ss.tema_global)


def tema_figura(fig_id, tipo=None):
    t = tm.resolver(tm.PRESETS.get(ss.tema_preset, {}), ss.tema_global, ss.ajustes.get(fig_id, {}))
    if tipo == "diagnostico" and "tela.largura_mm" not in ss.ajustes.get(fig_id, {}):
        t["tela.largura_mm"] = max(t["tela.largura_mm"], 183.0)
    if tipo in ("correlacao", "pca", "dendrograma", "empilhado") and "tela.largura_mm" not in ss.ajustes.get(fig_id, {}) \
            and "tela.largura_mm" not in ss.tema_global:
        t["tela.largura_mm"] = max(t["tela.largura_mm"], 120.0)
    return t


def hash_tema(t):
    return hashlib.md5(json.dumps(t, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


# ----------------------------------------------------------------------------
# Catálogo de figuras disponíveis
# ----------------------------------------------------------------------------
def camada_de(res):
    if not ss.get("perfil_auto", True):
        return None
    for i, f in enumerate(res.spec.fatores):
        if relatorio.parece_camada(f.coluna) or relatorio.parece_camada(f.rotulo):
            return i
    return None


def aplicar_modelos(res, chave):
    for fa in res.fatias:
        ce = ss.modelo_escolhido.get(chave, {}).get((fa.fator, tuple(sorted(fa.condicao.items()))))
        if fa.regressao and ce:
            alvo = [a for a in fa.regressao.ajustes if a.codigo == ce]
            if alvo:
                fa.regressao.melhor = alvo[0]


def catalogo(idioma="pt") -> dict:
    """id -> ItemFigura, para todas as variáveis analisadas e análises multivariadas."""
    chave = (ss.versao, idioma, json.dumps(ss.rotulos_y, sort_keys=True, ensure_ascii=False), ss.get("perfil_auto"))
    if ss.get("_cat_chave") == chave and ss.get("_cat"):
        return ss._cat
    out = {}
    for (g, v), r in ss.resultados.items():
        if isinstance(r, Exception):
            continue
        aplicar_modelos(r, (g, v))
        for it in relatorio.specs_para(r, ss.rotulos_y.get(v) or v, camada_de(r), grupo=g, idioma=idioma):
            out[it.id] = it
    ex = ss.extras
    if ex.get("correlacao") is not None:
        c = ex["correlacao"]
        out["multi::correlacao"] = relatorio.ItemFigura("multi::correlacao", "correlacao", "Matriz de correlação",
                                                        fg.SpecCorrelacao(c.R, c.P, c.nomes, c.metodo), "Multivariada")
    if ex.get("pca") is not None:
        p = ex["pca"]
        out["multi::pca"] = relatorio.ItemFigura(
            "multi::pca", "pca_biplot", "Biplot da PCA",
            fg.SpecPCA(p.escores, p.cargas, p.nomes, p.grupos, p.explicada, ex.get("pca_grupo") or "",
                       p.rotulos_linhas if p.base.startswith("médias") else None), "Multivariada")
    if ex.get("agrupamento") is not None:
        a = ex["agrupamento"]
        out["multi::dendrograma"] = relatorio.ItemFigura(
            "multi::dendrograma", "dendrograma", "Dendrograma",
            fg.SpecDendrograma(a.ligacao, a.rotulos, a.corte, a.grupos, a.metodo), "Multivariada")
    if ex.get("empilhado") is not None:
        out["multi::empilhado"] = relatorio.ItemFigura("multi::empilhado", "composicao", "Composição (barras empilhadas)",
                                                       ex["empilhado"], "Multivariada")
    ss._cat, ss._cat_chave = out, chave
    return out


def rotulo_item(it):
    pre = f"{it.variavel}" + (f" · {it.grupo}" if it.grupo else "")
    return f"{pre} — {it.titulo}"


# ----------------------------------------------------------------------------
# Prévia e arquivos
# ----------------------------------------------------------------------------
def previa(it, t=None, idioma="pt", dpi=150):
    t = t or tema_figura(it.id, it.spec.tipo)
    k = ("prev", it.id, ss.versao, hash_tema(t), idioma, dpi)
    if len(ss.cache_figs) > 120:
        ss.cache_figs = {}
    if k not in ss.cache_figs:
        ss.cache_figs[k] = fg.gerar_previa(it.spec, t, idioma, dpi)
    return ss.cache_figs[k]


def _guardar_cache(nome, k, gerar, limite=60):
    c = ss.setdefault(nome, {})
    if k not in c:
        if len(c) >= limite:
            c.clear()
        c[k] = gerar()
    return c[k]


def arquivo_figura(it, t, fmt, idioma="pt"):
    """Bytes do arquivo final, gerados uma vez e guardados (o download nunca depende de geração tardia)."""
    return _guardar_cache("cache_arq", (it.id, ss.versao, hash_tema(t), fmt, idioma),
                          lambda: fg.gerar_arquivo(it.spec, t, fmt, idioma), 40)


def _kb(b):
    n = len(b) / 1024
    return f"{n:.0f} kB" if n < 1024 else f"{n / 1024:.1f} MB".replace(".", ",")


@st.fragment
def baixar_figura(it, idioma="pt", chave="", t=None, formatos=("png", "tiff", "svg", "pdf", "eps")):
    """Escolha do formato e botão de download com o arquivo já pronto."""
    t = t or tema_figura(it.id, it.spec.tipo)
    fmt = st.segmented_control("Formato", list(formatos), format_func=lambda f: ROT_FMT[f],
                               key=f"fmt|{chave}|{it.id}", label_visibility="collapsed")
    if not fmt:
        st.caption("Escolha o formato; o arquivo é preparado na hora, no tamanho e na resolução do tema.")
        return
    try:
        dados = arquivo_figura(it, t, fmt, idioma)
    except Exception as e:
        st.error(f"Não foi possível gerar o arquivo {ROT_FMT[fmt]}: {e}")
        return
    det = f"{int(t['tela.dpi'])} dpi · " if fmt in ("png", "tiff") else ""
    st.download_button(f"Baixar {it.nome}.{fmt}", dados, file_name=f"{it.nome}.{fmt}", mime=MIMES[fmt],
                       key=f"dl|{chave}|{it.id}|{fmt}", type="primary", width="stretch", on_click="ignore")
    st.caption(f"{det}{_kb(dados)}")


def botoes_figura(it, idioma="pt", chave="", formatos=("png", "svg", "pdf", "tiff"), horizontal=True, t=None):
    baixar_figura(it, idioma, chave, t, formatos)


def gerar_e_baixar(rotulo, gerar, nome, mime, chave, assinatura=None, ajuda=None, rot_baixar=None):
    """Arquivos pesados (Excel, Word, pacotes): um clique prepara, o seguinte baixa. `assinatura` identifica o
    conteúdo; quando muda, o arquivo guardado é descartado."""
    pronto = ss.setdefault("arquivos_prontos", {})
    atual = pronto.get(chave)
    if atual and atual[0] != assinatura:
        pronto.pop(chave, None)
        atual = None
    if atual is None:
        if st.button(rotulo, key=f"gerar|{chave}", width="stretch", help=ajuda):
            try:
                with st.spinner("Preparando o arquivo…"):
                    pronto[chave] = (assinatura, gerar())
                st.rerun()
            except Exception as e:
                st.error(f"Não foi possível gerar o arquivo: {e}")
    else:
        st.download_button(rot_baixar or f"Baixar {nome} · {_kb(atual[1])}", atual[1], file_name=nome, mime=mime,
                           key=f"baixar|{chave}", type="primary", width="stretch", on_click="ignore")


# ----------------------------------------------------------------------------
# Pasta de figuras da sessão
# ----------------------------------------------------------------------------
def guardar_na_pasta(it, t=None, idioma="pt"):
    """Guarda a figura como está agora (dados, modelo e estilo); mudanças posteriores não a alteram."""
    import copy
    import datetime as dt
    t = copy.deepcopy(t or tema_figura(it.id, it.spec.tipo))
    pasta = ss.setdefault("pasta", [])
    marca = (it.id, ss.versao, hash_tema(t), idioma)
    if any(p["marca"] == marca for p in pasta):
        st.toast("Esta versão da figura já está na pasta.")
        return
    nomes = {p["nome"] for p in pasta}
    nome, n = it.nome, 2
    while nome in nomes:
        nome, n = f"{it.nome}_{n}", n + 1
    try:
        mini = fg.gerar_previa(it.spec, t, idioma, 90)
    except Exception as e:
        st.toast(f"Não foi possível guardar: {e}")
        return
    ss.contador_pasta = ss.get("contador_pasta", 0) + 1
    pasta.append(dict(uid=ss.contador_pasta, marca=marca, nome=nome, titulo=rotulo_item(it), spec=copy.deepcopy(it.spec),
                      tema=t, idioma=idioma, mini=mini, hora=dt.datetime.now().strftime("%H:%M")))
    st.toast(f"Figura guardada na pasta ({len(pasta)}).")


def botao_pasta(it, idioma="pt", chave="", t=None, rotulo="＋ Pasta"):
    st.button(rotulo, key=f"pasta|{chave}|{it.id}", on_click=guardar_na_pasta, args=(it, t, idioma), width="stretch",
              help="Guarda esta figura, como está agora, na pasta da sessão (aba Pasta e downloads), para baixar "
                   "todas de uma vez.")


def zip_pasta(itens, formatos):
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in itens:
            for fmt in formatos:
                z.writestr(f"{fmt}/{p['nome']}.{fmt}" if len(formatos) > 1 else f"{p['nome']}.{fmt}",
                           fg.gerar_arquivo(p["spec"], p["tema"], fmt, p["idioma"]))
    return buf.getvalue()


# ----------------------------------------------------------------------------
# Tabelas
# ----------------------------------------------------------------------------
def fmt_tabela(df: pd.DataFrame, p_cols=("p",)):
    out = df.copy()
    for c in out.columns:
        if c in p_cols:
            out[c] = [("< 0,0001" if v < 1e-4 else f"{v:.4f}".replace(".", ",")) if isinstance(v, (float, np.floating))
                      and np.isfinite(v) else ("" if not isinstance(v, str) else v) for v in out[c]]
        elif pd.api.types.is_numeric_dtype(out[c]) and out[c].dropna().apply(lambda v: float(v).is_integer()).all() \
                and c in ("GL", "n", "#", "GL erro", "Linha na planilha", "Posição", "Repetições",
                                                                    "GL resíduo", "Blocos", "Grupo"):
            out[c] = [f"{int(v)}" if pd.notna(v) else "" for v in out[c]]
        elif pd.api.types.is_numeric_dtype(out[c]) and not pd.api.types.is_bool_dtype(out[c]):
            def f(v):
                if v is None or not np.isfinite(v):
                    return ""
                return exportar._fmt_str(v, exportar._decimais(v), "pt")
            out[c] = [f(v) for v in out[c]]
    return out


def tabela_ui(df: pd.DataFrame, nome: str, titulo: str = "", nota: str = "", chave: str = "", p_cols=("p", "p ajustado"),
              indice=False, idioma="pt", mostrar=True, column_config=None):
    """Mostra a tabela e oferece download em Excel e Word no padrão de periódico."""
    if mostrar:
        st.dataframe(fmt_tabela(df.reset_index() if indice else df, p_cols), hide_index=True, width="stretch",
                     column_config=column_config)
    fonte = tm.FONTES.get(tema_base()["fonte.familia"], "Roboto")
    base = df if indice else df.set_index(df.columns[0])
    try:
        ass = hashlib.md5((base.to_csv() + f"|{titulo}|{nota}|{idioma}|{fonte}").encode()).hexdigest()
        xls = _guardar_cache("cache_tab", ("x", ass), lambda: tabelas.tabela_xlsx(base, titulo, nota, idioma, fonte), 400)
        doc = _guardar_cache("cache_tab", ("d", ass), lambda: tabelas.tabela_docx(base, titulo, nota, idioma, fonte), 400)
    except Exception as e:
        st.caption(f"Download da tabela indisponível: {e}")
        return
    linha = st.container(horizontal=True, gap="small")
    linha.download_button("Excel", data=xls, file_name=f"{nome}.xlsx", mime=MIMES["xlsx"], key=f"tx|{chave}|{nome}",
                          width="content", on_click="ignore",
                          help="Tabela formatada: filetes de 1,0 pt acima e abaixo, 0,5 pt sob o cabeçalho")
    linha.download_button("Word", data=doc, file_name=f"{nome}.docx", mime=MIMES["docx"], key=f"td|{chave}|{nome}",
                          width="content", on_click="ignore",
                          help="Espessuras exatas (1,0 e 0,5 pt); pronta para colar no manuscrito")
