"""
Estado e utilidades compartilhadas da interface (temas por figura, catálogo
de figuras, cache de prévias e tabelas com download em Excel/Word).
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
import streamlit as st

from motor import exportar, figuras as fg, relatorio, tabelas, tema as tm

ss = st.session_state

MIMES = {"png": "image/png", "svg": "image/svg+xml", "pdf": "application/pdf", "tiff": "image/tiff",
         "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
         "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
ROT_FMT = {"png": "PNG", "svg": "SVG", "pdf": "PDF", "tiff": "TIFF"}


def iniciar_estado():
    padrao = dict(df=None, nome_arquivo=None, resultados={}, config_exec=None, transf_var={}, modelo_escolhido={},
                  rotulos_y={}, extras={}, cache_figs={}, tema_preset="Solos (padrão da plataforma)",
                  tema_global={}, ajustes={}, versao=0, estudio_fig=None, painel_cfg=None, perfil_auto=True,
                  excluir={}, tabelas_extra={})
    for k, v in padrao.items():
        ss.setdefault(k, v)


def nova_versao():
    ss.versao = ss.get("versao", 0) + 1
    ss.cache_figs = {}


# ----------------------------------------------------------------------------
# Temas
# ----------------------------------------------------------------------------
def tema_base():
    return tm.resolver(tm.PRESETS.get(ss.tema_preset, {}), ss.tema_global)


def tema_figura(fig_id, tipo=None):
    t = tm.resolver(tm.PRESETS.get(ss.tema_preset, {}), ss.tema_global, ss.ajustes.get(fig_id, {}))
    if tipo == "diagnostico" and "tela.largura_mm" not in ss.ajustes.get(fig_id, {}):
        t["tela.largura_mm"] = max(t["tela.largura_mm"], 183.0)
    if tipo in ("correlacao", "pca", "dendrograma") and "tela.largura_mm" not in ss.ajustes.get(fig_id, {}) \
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


def botoes_figura(it, idioma="pt", chave="", formatos=("png", "svg", "pdf", "tiff"), horizontal=True, t=None):
    t = t or tema_figura(it.id, it.spec.tipo)
    spec = it.spec
    cols = st.columns(len(formatos)) if horizontal else [st.container() for _ in formatos]
    for c, fmt in zip(cols, formatos):
        rot = ROT_FMT[fmt] + (f" {int(t['tela.dpi'])} dpi" if fmt in ("png", "tiff") and not horizontal else "")
        c.download_button(rot, data=(lambda s=spec, tt=t, f=fmt: fg.gerar_arquivo(s, tt, f, idioma)),
                          file_name=f"{it.nome}.{fmt}", mime=MIMES[fmt], key=f"dl|{chave}|{it.id}|{fmt}",
                          width="stretch")


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
    linha = st.container(horizontal=True, gap="small")
    linha.download_button("Excel", data=lambda: tabelas.tabela_xlsx(base, titulo, nota, idioma, fonte),
                       file_name=f"{nome}.xlsx", mime=MIMES["xlsx"], key=f"tx|{chave}|{nome}", width="content",
                       help="Tabela formatada: filetes de 1,0 pt acima e abaixo, 0,5 pt sob o cabeçalho")
    linha.download_button("Word", data=lambda: tabelas.tabela_docx(base, titulo, nota, idioma, fonte),
                       file_name=f"{nome}.docx", mime=MIMES["docx"], key=f"td|{chave}|{nome}", width="content",
                       help="Espessuras exatas (1,0 e 0,5 pt); pronta para colar no manuscrito")
