"""
Estúdio de figuras: edição detalhada de cada figura, montagem de painéis e
tema global. Os controles são gerados a partir do esquema motor.tema.PARAMS.
"""
from __future__ import annotations

import copy
import json

import pandas as pd
import streamlit as st

from motor import figuras as fg, tema as tm
from ui_comum import (MIMES, ROT_FMT, botoes_figura, catalogo, hash_tema, nova_versao, previa, rotulo_item, ss,
                      tema_base, tema_figura)
from motor.regressao import CATALOGO

ABAS_POR_TIPO = {
    "medias": ["Tela", "Fontes", "Eixos", "Séries", "Médias", "Erros e letras", "Legenda"],
    "grupos": ["Tela", "Fontes", "Eixos", "Séries", "Médias", "Erros e letras", "Legenda"],
    "regressao": ["Tela", "Fontes", "Eixos", "Séries", "Regressão", "Médias", "Erros e letras", "Legenda"],
    "perfil": ["Tela", "Fontes", "Eixos", "Séries", "Erros e letras", "Legenda"],
    "correlacao": ["Tela", "Fontes", "Multivariada"],
    "dendrograma": ["Tela", "Fontes", "Eixos", "Séries"],
    "pca": ["Tela", "Fontes", "Eixos", "Séries", "Multivariada", "Legenda"],
    "diagnostico": ["Tela", "Fontes", "Eixos", "Séries", "Médias", "Painel"],
}
# parâmetros irrelevantes por tipo (para enxugar a interface)
_SO_BARRAS = {"medias.rotulo_valor", "medias.rotulo_decimais", "medias.contorno_auto", "medias.hachura_esp"}
OCULTAR = {
    "regressao": {"medias.tipo", "medias.horizontal", "medias.largura", "medias.barra_alfa", "medias.barra_cor",
                  "medias.contorno_esp", "medias.contorno_cor", "medias.hachuras", "medias.obs_lado",
                  "medias.espaco_grupos", "medias.conectar", "letras.mostrar", "letras.se_ns", "letras.posicao",
                  "letras.distancia", "letras.italico", "letras.separar", "series.colorir_niveis"} | _SO_BARRAS,
    "perfil": {"letras.mostrar", "letras.se_ns", "letras.posicao", "letras.distancia", "letras.italico", "letras.separar",
               "series.colorir_niveis", "eixos.y_escala", "eixos.y_fator", "eixos.y_log", "eixos.y_min", "eixos.y_max",
               "eixos.y_passo", "eixos.y_decimais", "eixos.quebra_de", "eixos.quebra_ate", "eixos.x_rotacao"},
    "grupos": {"medias.horizontal", "series.colorir_niveis", "medias.obs_lado", "medias.barra_cor", "eixos.x_escala",
               "eixos.x_min", "eixos.x_max", "eixos.x_passo", "eixos.x_decimais"},
    "medias": {"medias.espaco_grupos", "medias.conectar", "letras.separar", "eixos.x_escala", "eixos.x_min",
               "eixos.x_max", "eixos.x_passo", "eixos.x_decimais"},
    "pca": {"eixos.quebra_de", "eixos.quebra_ate", "eixos.y_log", "series.colorir_niveis", "series.variar_linha",
            "eixos.y_fator"},
    "dendrograma": {"eixos.y_escala", "eixos.y_fator", "eixos.y_log", "eixos.y_min", "eixos.y_max", "eixos.y_passo",
                    "eixos.y_decimais", "eixos.quebra_de", "eixos.quebra_ate", "eixos.x_rotacao", "eixos.linha_media",
                    "series.colorir_niveis", "series.marcador_tam", "series.marcador_borda", "series.marcador_borda_cor",
                    "series.vazados", "series.variar_marcador", "series.variar_linha"},
}
# opções de tipo de gráfico válidas para cada figura
TIPOS_VALIDOS = {"medias": ["pontos", "barras", "box", "meia-caixa", "violino", "meio-violino", "raincloud", "beeswarm",
                            "linhas"],
                 "grupos": ["pontos", "barras", "box", "linhas"]}
# o que fica de fora ao copiar/colar formato (específico dos dados de cada figura)
NAO_COPIAR = ("eixos.y_min", "eixos.y_max", "eixos.y_passo", "eixos.x_min", "eixos.x_max", "eixos.x_passo",
              "eixos.rotulo_x", "eixos.rotulo_y", "eixos.quebra_de", "eixos.quebra_ate", "tela.titulo")
HIST_MAX = 40


# ============================================================================
# Controles gerados pelo esquema
# ============================================================================
def _alvo(escopo):
    if escopo == "GLOBAL":
        return ss.tema_global
    if escopo == "PAINEL":
        return ss.setdefault("painel_tema", {})
    return ss.ajustes.setdefault(escopo, {})


def _base(escopo):
    """Valores sem a camada do próprio escopo (para saber se algo é ajuste de fato)."""
    if escopo == "GLOBAL":
        return tm.resolver(tm.PRESETS.get(ss.tema_preset, {}))
    return tema_base()


def _parse(p, v):
    if p.tipo == "num" and p.padrao is None:
        if v is None or str(v).strip() == "":
            return None
        try:
            return float(str(v).replace(",", "."))
        except ValueError:
            return None
    if p.tipo == "num":
        return float(v)
    if p.tipo == "int":
        return int(v)
    return v


def _exibir(p, v):
    if p.tipo == "num" and p.padrao is None:
        return "" if v is None else (f"{v:g}" if isinstance(v, (int, float)) else str(v))
    if p.tipo == "num":
        v = float(v)
        if p.minimo is not None:
            v = max(v, float(p.minimo))
        if p.maximo is not None:
            v = min(v, float(p.maximo))
        return v
    if p.tipo == "int":
        v = int(v)
        if p.minimo is not None:
            v = max(v, int(p.minimo))
        if p.maximo is not None:
            v = min(v, int(p.maximo))
        return v
    if p.tipo == "escolha" and p.opcoes and v not in p.opcoes:
        return p.opcoes[0]
    return v


def _snapshot(escopo):
    """Guarda o estado antes de cada alteração (botão Desfazer)."""
    h = ss.setdefault("historico", {}).setdefault(escopo, [])
    h.append(copy.deepcopy(_alvo(escopo)))
    del h[:-HIST_MAX]


def _desfazer(escopo):
    h = ss.get("historico", {}).get(escopo) or []
    if not h:
        return
    anterior = h.pop()
    if escopo == "GLOBAL":
        ss.tema_global = anterior
    elif escopo == "PAINEL":
        ss.painel_tema = anterior
    else:
        ss.ajustes[escopo] = anterior
    _limpar_widgets(escopo)


def _restaurar(escopo):
    _snapshot(escopo)
    ss.ajustes.pop(escopo, None)
    _limpar_widgets(escopo)


def _cb(escopo, chave, wkey):
    _snapshot(escopo)
    p = tm.POR_CHAVE[chave]
    v = _parse(p, ss[wkey])
    alvo = _alvo(escopo)
    if v == _base(escopo).get(chave):
        alvo.pop(chave, None)
    else:
        alvo[chave] = v


def _widget(p, escopo, valor, coluna, prefixo="ed", opcoes=None, rotulo=None):
    wkey = f"{prefixo}|{escopo}|{p.chave}"
    desejado = _exibir(p, valor)
    if ss.get(wkey) != desejado:
        ss[wkey] = desejado
    if opcoes and desejado not in opcoes:
        desejado = opcoes[0]
        ss[wkey] = desejado
    marcado = "● " if p.chave in _alvo(escopo) else ""
    kw = dict(key=wkey, on_change=_cb, args=(escopo, p.chave, wkey), help=p.ajuda or None)
    rot = marcado + (rotulo or p.rotulo)
    with coluna:
        if p.tipo == "bool":
            st.toggle(rot, **kw)
        elif p.tipo == "cor":
            st.color_picker(rot, **kw)
        elif p.tipo == "escolha":
            st.selectbox(rot, opcoes or p.opcoes, **kw)
        elif p.tipo == "texto":
            st.text_input(rot, **kw)
        elif p.tipo == "num" and p.padrao is None:
            st.text_input(rot, placeholder="automático", **kw)
        elif p.tipo == "num":
            st.number_input(rot, min_value=float(p.minimo) if p.minimo is not None else None,
                            max_value=float(p.maximo) if p.maximo is not None else None,
                            step=float(p.passo or 0.1), format="%g", **kw)
        elif p.tipo == "int":
            st.number_input(rot, min_value=int(p.minimo) if p.minimo is not None else None,
                            max_value=int(p.maximo) if p.maximo is not None else None, step=int(p.passo or 1), **kw)


def _visiveis(tipo):
    return [p for p in tm.PARAMS if p.tipo not in ("dict", "lista") and p.chave not in OCULTAR.get(tipo, set())]


def controles_aba(aba, escopo, t, tipo=None, prefixo="ed"):
    params = [p for p in _visiveis(tipo) if p.aba == aba]
    c1, c2 = st.columns(2)
    for i, p in enumerate(params):
        _widget(p, escopo, t[p.chave], c1 if i % 2 == 0 else c2, prefixo,
                opcoes=TIPOS_VALIDOS.get(tipo) if p.chave == "medias.tipo" else None)
    if aba == "Eixos":
        st.caption("Títulos aceitam códigos: kg ha^-1 → kg ha⁻¹ · P_{2}O_{5} → P₂O₅ · *Crotalaria* → itálico · "
                   "\\alpha → α · \\deg → °")


def busca_parametros(escopo, t, tipo, termo):
    termo = termo.strip().lower()
    achados = [p for p in _visiveis(tipo) if termo in p.rotulo.lower() or termo in p.chave.lower()
               or termo in (p.ajuda or "").lower() or termo in p.aba.lower()]
    if not achados:
        st.caption("Nenhuma opção encontrada.")
        return
    st.caption(f"{len(achados)} opção(ões) para “{termo}”")
    c1, c2 = st.columns(2)
    for i, p in enumerate(achados[:24]):
        _widget(p, escopo, t[p.chave], c1 if i % 2 == 0 else c2, "busca",
                opcoes=TIPOS_VALIDOS.get(tipo) if p.chave == "medias.tipo" else None,
                rotulo=f"{p.rotulo}  ·  {p.aba}")


# ============================================================================
# Seções dinâmicas: grupos, níveis e anotações
# ============================================================================
def _set_dict(escopo, chave, sub, valor, base_val):
    alvo = _alvo(escopo)
    d = copy.deepcopy(alvo.get(chave, {}))
    if valor == base_val or valor in (None, ""):
        d.pop(sub, None)
    else:
        d[sub] = valor
    if d:
        alvo[chave] = d
    else:
        alvo.pop(chave, None)


def _cb_grupo(escopo, chave, sub, wkey, base_val):
    _snapshot(escopo)
    v = ss[wkey]
    if chave == "grupos.marcadores":
        v = v if v != "auto" else None
    if chave == "grupos.linhas":
        v = v if v != "auto" else None
    _set_dict(escopo, chave, sub, v, base_val)


def secao_grupos(sp, escopo, t):
    grupos = sp.grupos()
    if not grupos:
        return
    st.markdown("**Cor, marcador e linha de cada grupo**")
    t_sem = {**t, "grupos.cores": {}, "grupos.marcadores": {}, "grupos.linhas": {}}
    for i, g in enumerate(grupos[:20]):
        c0, c1, c2, c3 = st.columns([3, 1.2, 2, 2])
        c0.markdown(f"<div style='padding-top:0.45rem'>{tm.nome_nivel(t, g)}</div>", unsafe_allow_html=True)
        if g == "série" or (sp.tipo == "medias" and not t["series.colorir_niveis"]):
            padrao_cor = t_sem["series.cor_unica"]
        else:
            padrao_cor = tm.cor_grupo(t_sem, g, i)
        cor_atual = t["grupos.cores"].get(g, padrao_cor)
        wk = f"edg|{escopo}|cor|{g}"
        if ss.get(wk) != cor_atual:
            ss[wk] = cor_atual
        c1.color_picker("Cor", key=wk, label_visibility="collapsed",
                        on_change=_cb_grupo, args=(escopo, "grupos.cores", g, wk, padrao_cor))
        mk_inv = {v: k for k, v in tm.MARCADORES.items()}
        opcoes_mk = ["auto"] + list(tm.MARCADORES)
        atual_mk = t["grupos.marcadores"].get(g)
        atual_mk = atual_mk if atual_mk in tm.MARCADORES else mk_inv.get(atual_mk, "auto") if atual_mk else "auto"
        wk = f"edg|{escopo}|mk|{g}"
        if ss.get(wk) != atual_mk:
            ss[wk] = atual_mk
        c2.selectbox("Marcador", opcoes_mk, key=wk, label_visibility="collapsed",
                     on_change=_cb_grupo, args=(escopo, "grupos.marcadores", g, wk, None))
        if sp.tipo in ("regressao", "perfil", "grupos"):
            opcoes_ln = ["auto"] + list(tm.ESTILOS_LINHA)
            atual_ln = t["grupos.linhas"].get(g) or "auto"
            wk = f"edg|{escopo}|ln|{g}"
            if ss.get(wk) != atual_ln:
                ss[wk] = atual_ln
            c3.selectbox("Linha", opcoes_ln, key=wk, label_visibility="collapsed",
                         on_change=_cb_grupo, args=(escopo, "grupos.linhas", g, wk, None))


def _niveis_da_spec(sp):
    if sp.tipo == "medias":
        return [(str(n), "eixo") for n in sp.niveis]
    if sp.tipo == "grupos":
        return [(str(a), "eixo X") for a in sp.A] + [(str(b), "grupo") for b in sp.B]
    if sp.tipo == "regressao":
        return [(str(c.rotulo), "curva") for c in sp.curvas] if len(sp.curvas) > 1 else []
    if sp.tipo == "perfil":
        return [(str(s.get("rotulo")), "série") for s in sp.series if s.get("rotulo") is not None] + \
               [(str(c), "camada") for c in sp.camadas]
    if sp.tipo == "correlacao":
        return [(str(n), "variável") for n in sp.nomes]
    if sp.tipo == "pca":
        return [(str(n), "variável") for n in sp.nomes] + [(g, "grupo") for g in sp.grupos()]
    return []


def secao_niveis(sp, escopo, t):
    niveis = _niveis_da_spec(sp)
    if not niveis:
        return
    st.markdown("**Nomes, ordem e visibilidade**")
    st.caption("Edite o nome exibido, a posição (1, 2, 3…) e marque para ocultar. A ordem vale dentro de cada papel.")
    ordem = [str(o) for o in t["niveis.ordem"]]
    pos = {}
    for papel in dict.fromkeys(p for _, p in niveis):
        do_papel = [n for n, pp in niveis if pp == papel]
        ord_p = [o for o in ordem if o in do_papel] + [n for n in do_papel if n not in ordem]
        for i, n in enumerate(ord_p):
            pos[(n, papel)] = i + 1
    base = pd.DataFrame({"Nível": [n for n, _ in niveis], "Papel": [p for _, p in niveis],
                         "Exibir como": [tm.nome_nivel(t, n) for n, _ in niveis],
                         "Posição": [pos[(n, p)] for n, p in niveis],
                         "Ocultar": [n in map(str, t["niveis.ocultar"]) for n, _ in niveis]})
    wk = f"edn|{escopo}"
    ed = st.data_editor(base, key=wk, hide_index=True, width="stretch", disabled=["Nível", "Papel"],
                        column_config={"Posição": st.column_config.NumberColumn(min_value=1, step=1),
                                       "Ocultar": st.column_config.CheckboxColumn()})
    if not ed.equals(base):
        renomear = {r["Nível"]: r["Exibir como"] for _, r in ed.iterrows()
                    if r["Exibir como"] and str(r["Exibir como"]) != r["Nível"]}
        ordem_n = []
        for papel in dict.fromkeys(ed["Papel"]):
            sub = ed[ed["Papel"] == papel].sort_values("Posição", kind="stable")
            ordem_n += list(sub["Nível"])
        ocultar = [r["Nível"] for _, r in ed.iterrows() if r["Ocultar"]]
        _snapshot(escopo)
        alvo = _alvo(escopo)
        for k, v in (("niveis.renomear", renomear), ("niveis.ordem", ordem_n), ("niveis.ocultar", ocultar)):
            if v:
                alvo[k] = v
            else:
                alvo.pop(k, None)
        del ss[wk]
        st.rerun(scope="fragment")


def _editor_lista(escopo, t, chave, colunas, config, titulo, ajuda=""):
    st.markdown(f"**{titulo}**")
    if ajuda:
        st.caption(ajuda)
    dados = t[chave] or []
    base = pd.DataFrame(dados, columns=list(colunas)) if dados else pd.DataFrame({c: pd.Series(dtype=tp) for c, tp in colunas.items()})
    wk = f"edl|{escopo}|{chave}"
    ed = st.data_editor(base, key=wk, num_rows="dynamic", hide_index=True, width="stretch", column_config=config)
    if not ed.reset_index(drop=True).equals(base.reset_index(drop=True)):
        linhas = [ {k: (None if (isinstance(v, float) and pd.isna(v)) else v) for k, v in r.items()}
                   for r in ed.to_dict("records")]
        linhas = [l for l in linhas if any(v not in (None, "") for v in l.values())]
        _snapshot(escopo)
        alvo = _alvo(escopo)
        if linhas:
            alvo[chave] = linhas
        else:
            alvo.pop(chave, None)
        del ss[wk]
        st.rerun(scope="fragment")


def secao_anotacoes(sp, escopo, t):
    niveis = [str(n) for n in sp.niveis] if sp.tipo == "medias" else None
    if niveis:
        _editor_lista(escopo, t, "anot.colchetes", {"de": "object", "ate": "object", "texto": "object"},
                      {"de": st.column_config.SelectboxColumn("de", options=niveis),
                       "ate": st.column_config.SelectboxColumn("até", options=niveis),
                       "texto": st.column_config.TextColumn("texto", default="*")},
                      "Colchetes de significância", "Ex.: de 'Controle' até 'Calcário', texto '**'.")
    _editor_lista(escopo, t, "anot.linhas", {"eixo": "object", "valor": "float", "estilo": "object", "cor": "object",
                                             "texto": "object"},
                  {"eixo": st.column_config.SelectboxColumn("eixo", options=["y", "x"], default="y"),
                   "estilo": st.column_config.SelectboxColumn("estilo", options=list(tm.ESTILOS_LINHA), default="tracejada"),
                   "cor": st.column_config.TextColumn("cor (hex)", default="#7A7A7A")},
                  "Linhas de referência", "Ex.: nível crítico, teor adequado, média geral.")
    _editor_lista(escopo, t, "anot.faixas", {"eixo": "object", "de": "float", "ate": "float", "cor": "object",
                                             "alfa": "float", "texto": "object"},
                  {"eixo": st.column_config.SelectboxColumn("eixo", options=["y", "x"], default="y"),
                   "ate": st.column_config.NumberColumn("até"),
                   "cor": st.column_config.TextColumn("cor (hex)", default="#D9C9B6"),
                   "alfa": st.column_config.NumberColumn("opacidade", default=0.25, min_value=0.02, max_value=1.0,
                                                          step=0.05)},
                  "Faixas sombreadas", "Ex.: faixa adequada de um nutriente, dose ótima, período crítico (unidades dos dados).")
    _editor_lista(escopo, t, "anot.formas", {"tipo": "object", "x0": "float", "y0": "float", "x1": "float",
                                             "y1": "float", "cor": "object", "texto": "object"},
                  {"tipo": st.column_config.SelectboxColumn("tipo", options=["seta", "linha", "retângulo", "elipse"],
                                                            default="seta"),
                   "x0": st.column_config.NumberColumn("x início", default=0.3, step=0.01),
                   "y0": st.column_config.NumberColumn("y início", default=0.9, step=0.01),
                   "x1": st.column_config.NumberColumn("x fim", default=0.2, step=0.01),
                   "y1": st.column_config.NumberColumn("y fim", default=0.7, step=0.01),
                   "cor": st.column_config.TextColumn("cor (hex)", default="#1A1A1A")},
                  "Setas e formas", "Posições em fração do eixo (0–1). Na seta, o texto fica no início e a ponta no fim.")
    _editor_lista(escopo, t, "anot.textos", {"x": "float", "y": "float", "texto": "object", "tam": "float"},
                  {"x": st.column_config.NumberColumn("x (0–1)", default=0.05, step=0.01),
                   "y": st.column_config.NumberColumn("y (0–1)", default=0.95, step=0.01),
                   "tam": st.column_config.NumberColumn("tamanho (pt)", default=7.0, step=0.5)},
                  "Textos livres", "Posição em fração do eixo: (0, 0) = canto inferior esquerdo; (1, 1) = superior direito. "
                  "Aceita ^{ } sobrescrito, _{ } subscrito, *itálico* e \\alpha.")


# ============================================================================
# Modelo ajustado (curvas de regressão)
# ============================================================================
def _trocar_modelo(it, chave_curva, wkey):
    cod = ss[wkey]
    ss.modelo_escolhido.setdefault((it.grupo, it.variavel), {})[chave_curva] = cod
    nova_versao()


def secao_modelos(it, sp, prefixo="mdl"):
    """Escolha do modelo de cada curva — o mesmo ajuste usado no texto, no Excel e no relatório."""
    curvas = [c for c in sp.curvas if c.ajustes and c.chave is not None]
    if not curvas:
        return
    for c in curvas:
        cods = [a.codigo for a in c.ajustes]
        atual = c.modelo.codigo if c.modelo is not None else cods[0]
        wkey = f"{prefixo}|{it.id}|{c.chave}"
        if ss.get(wkey) != atual:
            ss[wkey] = atual
        rot = "Modelo ajustado" + (f" — {c.rotulo}" if c.rotulo is not None else "")
        r2 = {a.codigo: a.r2 for a in c.ajustes}
        st.selectbox(rot, cods, key=wkey, on_change=_trocar_modelo, args=(it, c.chave, wkey),
                     format_func=lambda k, r2=r2: f"{CATALOGO[k].nome}  ·  R² {r2[k]:.3f}".replace(".", ","),
                     help="Lista todos os modelos que convergiram, do mais indicado (AICc) ao menos indicado.")


# ============================================================================
# Barra rápida (os ajustes mais usados, como a mini barra de ferramentas do OriginPro)
# ============================================================================
RAPIDOS = {
    "medias": ["medias.tipo", "medias.obs", "erro.tipo", "letras.mostrar", "series.paleta", "tela.largura_mm"],
    "grupos": ["medias.tipo", "medias.obs", "erro.tipo", "letras.mostrar", "series.paleta", "tela.largura_mm"],
    "regressao": ["medias.obs", "reg.banda", "reg.banda_tipo", "reg.equacao", "erro.tipo", "tela.largura_mm"],
    "perfil": ["erro.tipo", "series.paleta", "series.marcador_tam", "tela.largura_mm"],
    "pca": ["pca.elipses", "pca.setas", "series.paleta", "tela.largura_mm"],
    "correlacao": ["cor.triangulo", "cor.valores", "cor.paleta", "tela.largura_mm"],
    "dendrograma": ["series.paleta", "series.linha_esp", "tela.largura_mm"],
    "diagnostico": ["series.cor_unica", "medias.obs_alfa", "tela.largura_mm"],
}
ROTULOS_RAPIDOS = {"medias.obs": "Valores individuais", "medias.tipo": "Tipo de gráfico", "erro.tipo": "Barra de erro",
                   "letras.mostrar": "Letras", "series.paleta": "Paleta", "tela.largura_mm": "Largura (mm)",
                   "reg.banda": "Faixa da curva", "reg.banda_tipo": "Tipo de faixa", "reg.equacao": "Equação"}


def barra_rapida(it, t, prefixo="rap", vertical=False):
    sp = it.spec
    chaves = RAPIDOS.get(sp.tipo, ["tela.largura_mm"])
    cols = [st.container() for _ in chaves] if vertical else st.columns(len(chaves))
    for c, k in zip(cols, chaves):
        p = tm.POR_CHAVE[k]
        _widget(p, it.id, t[k], c, prefixo, opcoes=TIPOS_VALIDOS.get(sp.tipo) if k == "medias.tipo" else None,
                rotulo=ROTULOS_RAPIDOS.get(k))


# ============================================================================
# Copiar e colar formato
# ============================================================================
def secao_formato(it, cat, t):
    sp = it.spec
    with st.expander("Copiar e colar formato entre figuras"):
        st.caption("Leva o formato desta figura (como está na prévia) para outras figuras, escolhendo quais partes. "
                   "Limites dos eixos, títulos e quebra de eixo ficam de fora, pois dependem dos dados.")
        partes_ok = [a for a in tm.ABAS if a not in ("Painel", "Multivariada")]
        partes = st.multiselect("Partes do formato", partes_ok, key=f"cf_partes|{it.id}",
                                default=["Fontes", "Eixos", "Séries", "Médias", "Erros e letras", "Legenda"])
        mesmos = [k for k, v in cat.items() if k != it.id and v.spec.tipo != "diagnostico"]
        padrao = [k for k in mesmos if cat[k].spec.tipo == sp.tipo]
        alvos = st.multiselect("Colar em", mesmos, default=padrao, key=f"cf_alvos|{it.id}",
                               format_func=lambda k: rotulo_item(cat[k]))
        c1, c2 = st.columns(2)
        com_grupos = c1.toggle("Incluir cores e marcadores por grupo", value=False, key=f"cf_grp|{it.id}")
        com_niveis = c2.toggle("Incluir nomes, ordem e anotações", value=False, key=f"cf_niv|{it.id}")
        if st.button("Colar formato", type="primary", disabled=not (alvos and partes), key=f"cf_ok|{it.id}"):
            chaves = [p.chave for p in tm.PARAMS if p.aba in partes and p.chave not in NAO_COPIAR
                      and p.tipo not in ("dict", "lista")]
            if com_grupos:
                chaves += ["grupos.cores", "grupos.marcadores", "grupos.linhas"]
            if com_niveis:
                chaves += ["niveis.renomear", "niveis.ordem", "niveis.ocultar", "anot.colchetes", "anot.linhas",
                           "anot.textos", "anot.faixas", "anot.formas"]
            base = tema_base()
            for k_alvo in alvos:
                _snapshot(k_alvo)
                aj = ss.ajustes.setdefault(k_alvo, {})
                for ch in chaves:
                    if t[ch] == base.get(ch):
                        aj.pop(ch, None)
                    else:
                        aj[ch] = copy.deepcopy(t[ch])
                _limpar_widgets(k_alvo)
            st.toast(f"Formato colado em {len(alvos)} figura(s).")


# ============================================================================
# Modo figura
# ============================================================================
@st.fragment
def modo_figura(idioma):
    cat = catalogo(idioma)
    if not cat:
        st.info("Execute uma análise (ou calcule correlações/PCA) para editar figuras.")
        return
    ids = list(cat)
    if ss.get("est_sel_fig") not in ids:
        ss.est_sel_fig = ss.estudio_fig if ss.get("estudio_fig") in ids else ids[0]
    c_sel, c_desf, c_rest = st.columns([6, 1.2, 1.2], vertical_alignment="bottom")
    sel = c_sel.selectbox("Figura", ids, format_func=lambda i: rotulo_item(cat[i]), key="est_sel_fig")
    ss.estudio_fig = sel
    it = cat[sel]
    sp = it.spec
    t = tema_figura(it.id, sp.tipo)
    n_aj = len(ss.ajustes.get(it.id, {}))
    n_hist = len(ss.get("historico", {}).get(it.id, []))
    c_desf.button("↶ Desfazer", width="stretch", disabled=n_hist == 0, key="est_desfazer",
                  help=f"{n_hist} alteração(ões) para desfazer", on_click=_desfazer, args=(it.id,))
    c_rest.button("Restaurar", width="stretch", disabled=n_aj == 0, key="est_restaurar",
                  help="Volta esta figura ao tema global", on_click=_restaurar, args=(it.id,))
    with st.container(key="barra_rapida"):
        barra_rapida(it, t)
        if sp.tipo == "regressao":
            secao_modelos(it, sp, "mdl_rap")
    col_ctrl, col_prev = st.columns([5, 6], gap="large")
    with col_prev:
        with st.container(key="previa_fixa"):
            alt = t["tela.altura_mm"] or (fg._altura_padrao(sp, t) if sp.tipo != "diagnostico" else 0)
            st.html(f"<div class='ss-legenda'><b>Prévia</b> em {t['tela.largura_mm']:g} × {alt:.0f} mm, "
                    f"{n_aj} ajuste(s) próprio(s) nesta figura</div>")
            try:
                png = previa(it, t, idioma, dpi=150)
                st.image(png, width="content")
            except Exception as e:  # mostra o erro sem derrubar o editor
                st.error(f"Não foi possível desenhar com estes ajustes: {e}")
            st.html("<div class='ss-legenda'><b>Exportar</b> no tamanho exato acima</div>")
            botoes_figura(it, idioma, "est", formatos=("png", "tiff", "svg", "pdf", "eps"), t=t)
            b1, b2 = st.columns(2)
            if b1.button("Tornar tema global", width="stretch", disabled=n_aj == 0, key="est_global",
                         help="Leva os ajustes de estilo desta figura para o tema de todas as figuras"):
                estilo = {k: v for k, v in ss.ajustes.get(it.id, {}).items()
                          if not k.startswith(("niveis.", "anot.", "grupos.")) and k not in NAO_COPIAR}
                ss.tema_global.update(estilo)
                for k in estilo:
                    ss.ajustes[it.id].pop(k, None)
                st.rerun()
            b2.download_button("Salvar ajustes (.json)",
                               tm.para_json(ss.ajustes.get(it.id, {}), f"Ajustes — {it.titulo}"),
                               file_name=f"ajustes_{it.nome}.json", mime="application/json", width="stretch")
            secao_formato(it, cat, t)
    with col_ctrl:
        termo = st.text_input("Buscar opção", key=f"est_busca", placeholder="ex.: hachura, log, legenda, decimais…",
                              label_visibility="collapsed")
        if termo.strip():
            busca_parametros(it.id, t, sp.tipo, termo)
        else:
            abas = ABAS_POR_TIPO.get(sp.tipo, tm.ABAS)
            extras = ["Grupos e níveis"] + (["Anotações"] if sp.tipo in ("medias", "grupos", "regressao", "perfil") else [])
            tabs = st.tabs(abas + extras)
            for tab, aba in zip(tabs, abas + extras):
                with tab:
                    if aba == "Grupos e níveis":
                        secao_grupos(sp, it.id, t)
                        secao_niveis(sp, it.id, t)
                    elif aba == "Anotações":
                        secao_anotacoes(sp, it.id, t)
                    else:
                        if aba == "Regressão":
                            secao_modelos(it, sp)
                        controles_aba(aba, it.id, t, sp.tipo)
        st.caption("● parâmetro alterado nesta figura; os demais vêm do tema global. Cada alteração pode ser desfeita.")


def _limpar_widgets(escopo):
    for k in list(ss.keys()):
        if isinstance(k, str) and k.startswith(("ed|", "edg|", "edn|", "edl|", "rap|", "busca|", "mdl|", "mdl_rap|", "rres|", "mres|")) and f"|{escopo}" in k:
            del ss[k]


# ============================================================================
# Modo painel
# ============================================================================
@st.fragment
def modo_painel(idioma):
    cat = {k: v for k, v in catalogo(idioma).items() if v.spec.tipo != "diagnostico"}
    if not cat:
        st.info("Execute uma análise para montar painéis.")
        return
    cfg = ss.get("painel_cfg") or {"linhas": 1, "colunas": 2, "largura": 183.0, "altura": 0.0, "slots": {},
                                   "uniformizar": True}
    ss.painel_cfg = cfg
    col_ctrl, col_prev = st.columns([5, 6], gap="large")
    with col_ctrl:
        c1, c2, c3, c4 = st.columns(4)
        cfg["linhas"] = int(c1.number_input("Linhas", 1, 4, int(cfg["linhas"]), key="pn_l"))
        cfg["colunas"] = int(c2.number_input("Colunas", 1, 4, int(cfg["colunas"]), key="pn_c"))
        cfg["largura"] = float(c3.number_input("Largura (mm)", 40.0, 260.0, float(cfg["largura"]), 1.0, key="pn_w",
                                               format="%g"))
        cfg["altura"] = float(c4.number_input("Altura (mm; 0 = auto)", 0.0, 300.0, float(cfg["altura"]), 1.0, key="pn_h",
                                              format="%g"))
        cfg["uniformizar"] = st.toggle("Uniformizar fontes e espessuras (tema global em todos os painéis)",
                                       value=cfg.get("uniformizar", True), key="pn_u",
                                       help="Desligado, cada painel mantém os ajustes feitos para a figura no modo Figura.")
        st.markdown("**Conteúdo de cada painel**")
        ids = ["(vazio)"] + list(cat)
        for r in range(cfg["linhas"]):
            cols = st.columns(cfg["colunas"])
            for c in range(cfg["colunas"]):
                k = f"{r},{c}"
                atual = cfg["slots"].get(k, "(vazio)")
                if atual not in ids:
                    atual = "(vazio)"
                rot = tm.rotulo_painel(tema_painel()["painel.estilo"], r * cfg["colunas"] + c) or f"{r + 1},{c + 1}"
                cfg["slots"][k] = cols[c].selectbox(f"Painel {rot}", ids, index=ids.index(atual), key=f"pn_s_{k}",
                                                    format_func=lambda i: "(vazio)" if i == "(vazio)" else rotulo_item(cat[i]))
        with st.expander("Rótulos e espaçamento dos painéis", expanded=False):
            controles_aba("Painel", "PAINEL", tema_painel())
        with st.expander("Fontes do painel", expanded=False):
            controles_aba("Fontes", "PAINEL", tema_painel())
    itens = []
    tp = tema_painel()
    for r in range(cfg["linhas"]):
        for c in range(cfg["colunas"]):
            fid = cfg["slots"].get(f"{r},{c}", "(vazio)")
            if fid == "(vazio)" or fid not in cat:
                itens.append((None, None))
                continue
            it = cat[fid]
            t = tema_figura(fid, it.spec.tipo)
            if cfg["uniformizar"]:
                proprios = {k: v for k, v in ss.ajustes.get(fid, {}).items()
                            if k.startswith(("niveis.", "anot.", "grupos.", "eixos.rotulo", "eixos.y_", "eixos.x_", "medias.tipo"))}
                t = tm.resolver(tm.PRESETS.get(ss.tema_preset, {}), ss.tema_global, ss.get("painel_tema", {}), proprios)
            itens.append((it.spec, t))
    with col_prev:
        if not any(sp for sp, _ in itens):
            import estilo
            estilo.vazio("Painel vazio", "Escolha à esquerda a figura de cada posição (a, b, c…).")
            return
        alt = cfg["altura"] or None
        k = ("painel", ss.versao, json.dumps(cfg, sort_keys=True), hash_tema(tp),
             tuple(hash_tema(t) if t else None for _, t in itens), idioma)
        if k not in ss.cache_figs:
            ss.cache_figs[k] = fg.gerar_painel(itens, cfg["linhas"], cfg["colunas"], tp, idioma, cfg["largura"], alt,
                                               dpi=130)
        st.html(f"<div class='ss-legenda'><b>Prévia</b> do painel em {cfg['largura']:g} mm de largura</div>")
        st.image(ss.cache_figs[k], width="stretch")
        cols = st.columns(5)
        for col, fmt in zip(cols, ("png", "tiff", "svg", "pdf", "eps")):
            col.download_button(ROT_FMT[fmt], data=(lambda f=fmt: fg.gerar_painel(itens, cfg["linhas"], cfg["colunas"], tp,
                                                                                  idioma, cfg["largura"], alt, fmt=f)),
                                file_name=f"painel.{fmt}", mime=MIMES[fmt], key=f"pn_dl_{fmt}", width="stretch")


def tema_painel():
    return tm.resolver(tm.PRESETS.get(ss.tema_preset, {}), ss.tema_global, ss.get("painel_tema", {}))


# ============================================================================
# Modo tema global
# ============================================================================
@st.fragment
def modo_global(idioma):
    cat = catalogo(idioma)
    col_ctrl, col_prev = st.columns([5, 6], gap="large")
    with col_ctrl:
        c1, c2 = st.columns([3, 2])
        presets = list(tm.PRESETS)
        novo = c1.selectbox("Ponto de partida (preset)", presets, index=presets.index(ss.tema_preset), key="est_preset")
        if novo != ss.tema_preset:
            ss.tema_preset = novo
            st.rerun()
        if c2.button("Limpar tema global", width="stretch", disabled=not ss.tema_global):
            ss.tema_global = {}
            st.rerun()
        up = st.file_uploader("Carregar tema (.json)", type=["json"], key="est_up_tema")
        if up is not None and ss.get("_tema_carregado") != up.file_id:
            try:
                nome, params, ign = tm.de_json(up.getvalue().decode("utf-8"))
                ss.tema_global = params
                ss._tema_carregado = up.file_id
                st.success(f"Tema “{nome}” carregado ({len(params)} parâmetros)."
                           + (f" Ignorados: {', '.join(ign)}." if ign else ""))
                st.rerun()
            except Exception as e:
                st.error(f"Arquivo de tema inválido: {e}")
        t = tema_base()
        tabs = st.tabs(tm.ABAS)
        for tab, aba in zip(tabs, tm.ABAS):
            with tab:
                controles_aba(aba, "GLOBAL", t)
        st.caption("● indica parâmetro alterado em relação ao preset. Ajustes feitos em figuras específicas "
                   "continuam valendo por cima do tema global.")
    with col_prev:
        st.download_button("Salvar tema global (.json)", tm.para_json({**tm.PRESETS.get(ss.tema_preset, {}),
                                                                       **ss.tema_global}, "Meu tema"),
                           file_name="tema_stat_soil.json", mime="application/json", width="stretch")
        if cat:
            ids = [i for i in cat if cat[i].spec.tipo != "diagnostico"]
            if ids:
                ex = st.selectbox("Figura de exemplo", ids, format_func=lambda i: rotulo_item(cat[i]), key="est_glob_ex")
                st.image(previa(cat[ex], tema_figura(ex, cat[ex].spec.tipo), idioma, 150), width="content")
        n_fig = sum(1 for v in ss.ajustes.values() if v)
        if n_fig:
            st.caption(f"{n_fig} figura(s) têm ajustes próprios.")
            if st.button("Remover ajustes de todas as figuras"):
                ss.ajustes = {}
                for k in list(ss.keys()):
                    if isinstance(k, str) and k.startswith(("ed|", "edg|", "edn|", "edl|")) and "|GLOBAL" not in k:
                        del ss[k]
                st.rerun()


def render(idioma="pt"):
    ss.setdefault("est_modo", "Figura")
    modo = st.segmented_control("Modo", ["Figura", "Painel", "Tema global"], key="est_modo",
                                label_visibility="collapsed")
    if modo == "Painel":
        modo_painel(idioma)
    elif modo == "Tema global":
        modo_global(idioma)
    else:
        modo_figura(idioma)


def ajuste_rapido(it, idioma="pt", chave=""):
    """Popover ao lado de cada figura na aba Resultados: tipo, valores individuais, erro, modelo…"""
    t = tema_figura(it.id, it.spec.tipo)
    with st.popover("Ajuste rápido", width="stretch"):
        barra_rapida(it, t, "rres", vertical=True)
        if it.spec.tipo == "regressao":
            secao_modelos(it, it.spec, "mres")
        st.caption("Para tudo o mais (fontes, eixos, cores, anotações), use o Estúdio.")
