"""
Motor gráfico v2 — figuras descritas por uma especificação de dados (Spec*) e
desenhadas segundo um tema (motor.tema). Cada desenho recebe um eixo, o que
permite montar painéis com qualquer combinação de figuras.

Tamanho final exato: as figuras usam layout restrito ("constrained") e são
salvas sem recorte, de modo que a largura exportada é a largura pedida em mm.
"""
from __future__ import annotations

import io
import math
import textwrap
from dataclasses import dataclass, field

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import ticker  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, to_rgba  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Ellipse, Patch, Rectangle  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

from . import tema as tm  # noqa: E402
from .graficos import registrar_fontes  # noqa: E402
from .regressao import fmt_num, _f as _f_modelo  # noqa: E402

MM = 1 / 25.4


# ============================================================================
# Especificações (somente dados)
# ============================================================================
@dataclass
class SpecMedias:
    niveis: list
    medias: np.ndarray
    ep: np.ndarray
    dp: np.ndarray
    n: np.ndarray
    obs: pd.DataFrame | None = None          # colunas: nivel, y
    letras: list | None = None
    sig: bool = True
    rotulo_x: str = ""
    rotulo_y: str = ""
    titulo: str = ""
    tipo: str = "medias"

    def grupos(self):
        return [str(n) for n in self.niveis]


@dataclass
class SpecGrupos:
    A: list
    B: list
    medias: pd.DataFrame                    # índice A, colunas B
    ep: pd.DataFrame
    dp: pd.DataFrame | None = None
    n: pd.DataFrame | None = None
    letras: pd.DataFrame | None = None       # "a A"
    obs: pd.DataFrame | None = None          # colunas: A, B, y
    nome_A: str = ""
    nome_B: str = ""
    rotulo_y: str = ""
    titulo: str = ""
    tipo: str = "grupos"

    def grupos(self):
        return [str(b) for b in self.B]


@dataclass
class Curva:
    rotulo: str | None
    x: np.ndarray
    medias: np.ndarray
    ep: np.ndarray
    dp: np.ndarray
    n: np.ndarray
    obs_x: np.ndarray | None = None
    obs_y: np.ndarray | None = None
    modelo: object = None                    # AjusteModelo
    sig: bool = True


@dataclass
class SpecRegressao:
    curvas: list
    rotulo_x: str = ""
    rotulo_y: str = ""
    titulo_legenda: str = ""
    titulo: str = ""
    tipo: str = "regressao"

    def grupos(self):
        return [str(c.rotulo) for c in self.curvas] if len(self.curvas) > 1 else ["série"]


@dataclass
class SpecPerfil:
    camadas: list
    series: list                             # dicts: rotulo, medias, ep, dp, n
    rotulo_valor: str = ""
    rotulo_camada: str = ""
    titulo_legenda: str = ""
    titulo: str = ""
    tipo: str = "perfil"

    def grupos(self):
        return [str(s.get("rotulo")) for s in self.series] if len(self.series) > 1 else ["série"]


@dataclass
class SpecCorrelacao:
    R: np.ndarray
    P: np.ndarray
    nomes: list
    metodo: str = "Pearson"
    titulo: str = ""
    tipo: str = "correlacao"

    def grupos(self):
        return []


@dataclass
class SpecPCA:
    escores: np.ndarray
    cargas: np.ndarray
    nomes: list
    grupos_obs: np.ndarray
    explicada: np.ndarray
    titulo_legenda: str = ""
    rotulos_pontos: list | None = None
    titulo: str = ""
    tipo: str = "pca"

    def grupos(self):
        return list(dict.fromkeys(str(g) for g in self.grupos_obs))


@dataclass
class SpecDiagnostico:
    res: np.ndarray
    ajust: np.ndarray
    rstd: np.ndarray
    trat: np.ndarray
    titulo: str = ""
    tipo: str = "diagnostico"

    def grupos(self):
        return []


@dataclass
class SpecDendrograma:
    ligacao: np.ndarray
    rotulos: list
    corte: float | None = None
    clusters: np.ndarray | None = None
    metodo: str = "UPGMA"
    titulo: str = ""
    tipo: str = "dendrograma"

    def grupos(self):
        if self.clusters is None:
            return []
        return [f"Grupo {g}" for g in sorted({int(x) for x in self.clusters})]


TIPOS_NOME = {"medias": "Médias", "grupos": "Interação", "regressao": "Regressão", "perfil": "Perfil",
              "correlacao": "Correlação", "pca": "PCA", "diagnostico": "Diagnóstico", "dendrograma": "Agrupamento"}


# ============================================================================
# Estilo
# ============================================================================
def familia(t):
    return tm.FONTES.get(t["fonte.familia"], "Roboto")


def rc(t) -> dict:
    registrar_fontes()
    cor = t["fonte.cor"]
    return {
        "font.family": [familia(t), "DejaVu Sans"],
        "font.size": t["fonte.tamanho"],
        "axes.labelsize": t["fonte.titulo_eixo"],
        "axes.labelweight": t["fonte.peso_titulos"],
        "axes.titlesize": t["fonte.tamanho"],
        "axes.titleweight": t["fonte.peso_titulos"],
        "axes.labelcolor": cor,
        "axes.edgecolor": t["eixos.cor"],
        "axes.linewidth": t["eixos.espessura"],
        "axes.grid": False,
        "axes.labelpad": t["eixos.pad_titulo"],
        "axes.unicode_minus": True,
        "axes.facecolor": t["tela.fundo"],
        "figure.facecolor": t["tela.fundo"],
        "text.color": cor,
        "xtick.color": t["eixos.cor"],
        "ytick.color": t["eixos.cor"],
        "xtick.labelcolor": cor,
        "ytick.labelcolor": cor,
        "xtick.labelsize": t["fonte.numeros"],
        "ytick.labelsize": t["fonte.numeros"],
        "xtick.direction": t["eixos.marcas_direcao"],
        "ytick.direction": t["eixos.marcas_direcao"],
        "xtick.major.size": t["eixos.marcas_comp"],
        "ytick.major.size": t["eixos.marcas_comp"],
        "xtick.major.width": t["eixos.marcas_esp"],
        "ytick.major.width": t["eixos.marcas_esp"],
        "xtick.minor.size": t["eixos.marcas_comp"] * 0.55,
        "ytick.minor.size": t["eixos.marcas_comp"] * 0.55,
        "xtick.minor.width": t["eixos.marcas_esp"] * 0.8,
        "ytick.minor.width": t["eixos.marcas_esp"] * 0.8,
        "xtick.major.pad": 2.2,
        "ytick.major.pad": 2.2,
        "legend.frameon": t["legenda.moldura"],
        "legend.fontsize": t["fonte.legenda"],
        "legend.title_fontsize": t["fonte.legenda"],
        "legend.handlelength": t["legenda.comp_simbolo"],
        "legend.handletextpad": 0.4,
        "legend.labelspacing": t["legenda.espaco"],
        "legend.borderaxespad": 0.3,
        "legend.columnspacing": 1.0,
        "legend.edgecolor": t["eixos.cor"],
        "lines.linewidth": t["series.linha_esp"],
        "errorbar.capsize": t["erro.chapeu"],
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "mathtext.default": "regular",
        "figure.constrained_layout.h_pad": 0.02 * t["tela.margem"] / 0.3,
        "figure.constrained_layout.w_pad": 0.02 * t["tela.margem"] / 0.3,
    }


def _sep(t, idioma="pt"):
    d = t["eixos.decimal"]
    if d == "vírgula":
        return ","
    if d == "ponto":
        return "."
    return "," if idioma == "pt" else "."


def _formatador(t, decimais, idioma):
    sep = _sep(t, idioma)

    def f(v, pos=None):
        if decimais is None or decimais < 0:
            s = f"{v:g}" if abs(v) < 1e6 else f"{v:.3g}"
        else:
            s = f"{v:.{decimais}f}"
        return s.replace(".", sep).replace("-", "−")
    return ticker.FuncFormatter(f)


def _num(v, t, idioma, dig=3):
    s = fmt_num(v, dig, "en")
    return s.replace(".", _sep(t, idioma))


def _quebrar(rotulos, largura):
    return ["\n".join(textwrap.wrap(str(r), max(int(largura), 4), break_long_words=False)) or str(r)
            for r in rotulos]


def estilizar_eixo(ax, t, idioma="pt", x_categorico=False, y_categorico=False):
    for lado, chave in [("left", "eixos.esquerda"), ("bottom", "eixos.inferior"), ("top", "eixos.superior"),
                        ("right", "eixos.direita")]:
        ax.spines[lado].set_visible(bool(t[chave]))
        ax.spines[lado].set_linewidth(t["eixos.espessura"])
        ax.spines[lado].set_color(t["eixos.cor"])
        if t["eixos.destacar"] > 0:
            ax.spines[lado].set_position(("outward", t["eixos.destacar"]))
    ax.tick_params(top=bool(t["eixos.superior"]) and not x_categorico, right=bool(t["eixos.direita"]),
                   bottom=bool(t["eixos.inferior"]), left=bool(t["eixos.esquerda"]))
    for lab in ax.get_xticklabels() + ax.get_yticklabels():
        lab.set_fontweight(t["fonte.peso_numeros"])
    if not y_categorico:
        if t["eixos.y_log"]:
            ax.set_yscale("log")
        else:
            ax.yaxis.set_major_formatter(_formatador(t, t["eixos.y_decimais"], idioma))
            if t["eixos.y_passo"]:
                ax.yaxis.set_major_locator(ticker.MultipleLocator(float(t["eixos.y_passo"])))
            if t["eixos.marcas_menores"]:
                ax.yaxis.set_minor_locator(ticker.AutoMinorLocator(int(t["eixos.marcas_menores"]) + 1))
    if not x_categorico:
        ax.xaxis.set_major_formatter(_formatador(t, t["eixos.x_decimais"], idioma))
        if t["eixos.x_passo"]:
            ax.xaxis.set_major_locator(ticker.MultipleLocator(float(t["eixos.x_passo"])))
        if t["eixos.marcas_menores"]:
            ax.xaxis.set_minor_locator(ticker.AutoMinorLocator(int(t["eixos.marcas_menores"]) + 1))
    if t["eixos.x_rotacao"]:
        plt.setp(ax.get_xticklabels(), rotation=t["eixos.x_rotacao"], ha="right", rotation_mode="anchor")
    if t["eixos.grade"]:
        ax.yaxis.grid(True, color=t["eixos.grade_cor"], lw=0.5, zorder=0)
        ax.set_axisbelow(True)
    if t["eixos.linha_zero"]:
        ax.axhline(0, color=t["eixos.cor"], lw=t["eixos.espessura"] * 0.8, ls=(0, (3, 2)), zorder=1)


def _rotulos_eixos(ax, t, rx, ry):
    kw = dict(fontsize=t["fonte.titulo_eixo"], fontweight=t["fonte.peso_titulos"],
              fontstyle="italic" if t["fonte.italico_titulos"] else "normal")
    rx = t["eixos.rotulo_x"] or rx
    ry = t["eixos.rotulo_y"] or ry
    if rx is not None:
        ax.set_xlabel(rx, **kw)
    if ry is not None:
        ax.set_ylabel(ry, **kw)


def _limites_y(ax, t, lo, hi, folga_sup=0.06, zero=False):
    faixa = (hi - lo) if hi > lo else (abs(hi) or 1.0)
    ymin = 0 if zero and lo >= 0 else lo - 0.06 * faixa
    ymax = hi + folga_sup * faixa
    if t["eixos.y_min"] is not None:
        ymin = float(t["eixos.y_min"])
    if t["eixos.y_max"] is not None:
        ymax = float(t["eixos.y_max"])
    if not t["eixos.y_log"]:
        ax.set_ylim(ymin, ymax)


def _cor_erro(t, cor):
    return {"série": cor, "preto": "#1A1A1A", "cinza": "#7A7A7A"}[t["erro.cor"]]


def _cor_obs(t, cor):
    return {"série": cor, "cinza": "#8A8A8A", "preto": "#1A1A1A"}[t["medias.obs_cor"]]


def _barra_erro(t, ep, dp, n):
    tipo = t["erro.tipo"]
    if tipo == "nenhuma":
        return np.zeros_like(np.asarray(ep, float))
    if tipo == "dp":
        return np.asarray(dp, float)
    if tipo == "ic95":
        n = np.asarray(n, float)
        return np.asarray(ep, float) * stats.t.ppf(0.975, np.maximum(n - 1, 1))
    return np.asarray(ep, float)


def _yerr(t, e):
    e = np.nan_to_num(np.asarray(e, float))
    if t["erro.so_superior"]:
        return np.vstack([np.zeros_like(e), e])
    return e


def _jitter(n, largura, semente=0):
    if n <= 1 or largura <= 0:
        return np.zeros(n)
    base = np.linspace(-largura, largura, n)
    np.random.default_rng(semente).shuffle(base)
    return base


def _legenda(ax, t, handles, labels, titulo=None, padrao="automática", n_itens=None):
    if not t["legenda.mostrar"] or not handles:
        return None
    pos = t["legenda.posicao"]
    if pos == "automática":
        pos = padrao
    ncol = t["legenda.colunas"] or None
    dx, dy = t["legenda.dx"], t["legenda.dy"]
    kw = dict(title=titulo if (t["legenda.titulo"] and titulo) else None, frameon=t["legenda.moldura"],
              fontsize=t["fonte.legenda"], title_fontsize=t["fonte.legenda"], alignment="left")
    mapa = {
        "dentro — sup. esquerda": dict(loc="upper left", bbox_to_anchor=(0 + dx, 1 + dy)),
        "dentro — sup. direita": dict(loc="upper right", bbox_to_anchor=(1 + dx, 1 + dy)),
        "dentro — inf. esquerda": dict(loc="lower left", bbox_to_anchor=(0 + dx, 0 + dy)),
        "dentro — inf. direita": dict(loc="lower right", bbox_to_anchor=(1 + dx, 0 + dy)),
        "fora — acima": dict(loc="lower left", bbox_to_anchor=(0 + dx, 1.01 + dy), ncol=ncol or min(len(handles), 5)),
        "fora — direita": dict(loc="upper left", bbox_to_anchor=(1.02 + dx, 1 + dy)),
        "fora — abaixo": dict(loc="upper left", bbox_to_anchor=(0 + dx, -0.14 + dy), ncol=ncol or min(len(handles), 3)),
    }
    k = mapa.get(pos, dict(loc="best"))
    if ncol and "ncol" not in k:
        k["ncol"] = ncol
    return ax.legend(handles, labels, **k, **kw)


def _texto_letra(t, ax, x, y, s, horizontal=False, cor=None):
    if not s:
        return
    kw = dict(fontsize=t["fonte.letras"], color=cor or t["fonte.cor"], clip_on=True,
              fontstyle="italic" if t["letras.italico"] else "normal")
    if horizontal:
        ax.text(y, x, " " + s, ha="left", va="center", **kw)
    else:
        ax.text(x, y, s, ha="center", va="bottom", **kw)


# ============================================================================
# Reordenar / renomear / ocultar níveis
# ============================================================================
def _ordem(niveis, t):
    niveis = [str(n) for n in niveis]
    ocultos = set(map(str, t["niveis.ocultar"]))
    ordem = [str(o) for o in t["niveis.ordem"] if str(o) in niveis]
    resto = [n for n in niveis if n not in ordem]
    return [n for n in ordem + resto if n not in ocultos]


def _idx(niveis, escolhidos):
    s = [str(n) for n in niveis]
    return [s.index(e) for e in escolhidos]


# ============================================================================
# 1. Médias (um fator)
# ============================================================================
def desenhar_medias(ax, sp: SpecMedias, t, idioma="pt", legenda=True):
    H = bool(t["medias.horizontal"])
    ordem = _ordem(sp.niveis, t)
    ii = _idx(sp.niveis, ordem)
    k = len(ii)
    pos = np.arange(k, dtype=float)
    med = np.asarray(sp.medias, float)[ii]
    err = _barra_erro(t, np.asarray(sp.ep)[ii], np.asarray(sp.dp)[ii], np.asarray(sp.n)[ii])
    tipo = t["medias.tipo"]
    larg = t["medias.largura"]
    cores = [tm.cor_grupo(t, ordem[j], j) if t["series.colorir_niveis"] else
             (t["grupos.cores"].get(ordem[j]) or t["series.cor_unica"]) for j in range(k)]
    vals = []
    for j, i in enumerate(ii):
        if sp.obs is not None and len(sp.obs):
            vals.append(sp.obs.loc[sp.obs["nivel"].astype(str) == str(sp.niveis[i]), "y"].to_numpy(float))
        else:
            vals.append(np.array([]))
    mostrar_obs = t["medias.obs"] and any(len(v) for v in vals)
    ms = t["series.marcador_tam"]
    dx_med = 0.0
    dx_obs = 0.0
    if tipo == "pontos" and mostrar_obs and t["medias.obs_lado"]:
        dx_obs, dx_med = -0.12, 0.14
    if tipo == "raincloud":
        dx_obs = -0.24
    if tipo == "beeswarm":
        dx_obs, dx_med = -0.06, 0.24

    def sc(x, y, **kw):
        return ax.scatter(y, x, **kw) if H else ax.scatter(x, y, **kw)

    # preenchimentos
    for j in range(k):
        cor = cores[j]
        hach = tm.HACHURAS[j % len(tm.HACHURAS)] if t["medias.hachuras"] else ""
        if tipo == "barras":
            fc = (t["medias.barra_cor"] if (not t["series.colorir_niveis"] and not t["grupos.cores"].get(ordem[j]))
                  else cor)
            kw = dict(color=to_rgba(fc, t["medias.barra_alfa"]), edgecolor=t["medias.contorno_cor"],
                      linewidth=t["medias.contorno_esp"], hatch=hach, zorder=1)
            if H:
                ax.barh(pos[j], med[j], height=larg, **kw)
            else:
                ax.bar(pos[j], med[j], width=larg, **kw)
        elif tipo in ("box", "raincloud") and len(vals[j]) >= 2:
            w = larg if tipo == "box" else larg * 0.22
            p = pos[j] + (0 if tipo == "box" else 0.0)
            bp = ax.boxplot([vals[j]], positions=[p], widths=w, patch_artist=True, showfliers=tipo == "box",
                            **({"orientation": "horizontal"} if H else {}), manage_ticks=False,
                            medianprops=dict(color=t["fonte.cor"] if tipo == "box" else cor, lw=1.0),
                            whiskerprops=dict(color=cor, lw=t["erro.esp"]), capprops=dict(color=cor, lw=t["erro.esp"]),
                            boxprops=dict(lw=t["medias.contorno_esp"] or 0.6, edgecolor=cor),
                            flierprops=dict(marker="o", ms=2.5, mfc=cor, mec="none", alpha=0.6))
            for b in bp["boxes"]:
                b.set_facecolor(to_rgba(cor, 0.25 * t["medias.barra_alfa"]) if tipo == "box" else "white")
                b.set_hatch(hach)
        if tipo in ("violino", "raincloud") and len(vals[j]) >= 3:
            _violino(ax, pos[j] + (0.05 if tipo == "raincloud" else 0), vals[j], larg * (0.9 if tipo == "raincloud" else 1),
                     cor, 0.30 * t["medias.barra_alfa"], t["medias.contorno_esp"] or 0.5, tipo == "raincloud", H)
    # observações
    topo_obs = np.full(k, -np.inf)
    base_obs = np.full(k, np.inf)
    if mostrar_obs:
        for j in range(k):
            v = vals[j]
            if not len(v):
                continue
            topo_obs[j], base_obs[j] = np.nanmax(v), np.nanmin(v)
            cor = _cor_obs(t, cores[j])
            if tipo == "beeswarm":
                off = _swarm(v, t["medias.obs_tam"], ax, H)
            elif tipo == "raincloud":
                off = _jitter(len(v), min(t["medias.obs_disp"], 0.08), j)
            else:
                off = _jitter(len(v), t["medias.obs_disp"], j)
            sc(pos[j] + dx_obs + off, v, s=t["medias.obs_tam"], color=cor, alpha=t["medias.obs_alfa"], lw=0, zorder=2)
    # médias e erros
    for j in range(k):
        cor = cores[j]
        mostra_ponto = tipo in ("pontos", "violino", "beeswarm", "raincloud")
        if tipo == "raincloud":
            ax.plot(*((med[j], pos[j]) if H else (pos[j], med[j])), marker="o", ms=ms * 0.8, color=cor,
                    mec="white", mew=0.5, zorder=5)
            continue
        ye = _yerr(t, err[j:j + 1])
        kw = dict(fmt="o" if mostra_ponto else "none", color=_cor_erro(t, cor), ecolor=_cor_erro(t, cor),
                  ms=ms, elinewidth=t["erro.esp"], capthick=t["erro.esp"], capsize=t["erro.chapeu"], zorder=4,
                  mfc=("white" if t["series.vazados"] else cor), mec=(cor if t["series.vazados"] else t["series.marcador_borda_cor"]),
                  mew=(t["series.marcador_borda"] if not t["series.vazados"] else max(t["series.marcador_borda"], 0.8)))
        if tipo in ("box",):
            if t["erro.tipo"] != "nenhuma":
                pass
            ax.plot(*((med[j], pos[j]) if H else (pos[j], med[j])), marker="D", ms=ms * 0.7, color="white",
                    mec=cor, mew=0.8, zorder=5)
            continue
        p = pos[j] + dx_med
        if H:
            ax.errorbar(med[j], p, xerr=ye if t["erro.tipo"] != "nenhuma" else None, **kw)
        else:
            ax.errorbar(p, med[j], yerr=ye if t["erro.tipo"] != "nenhuma" else None, **kw)
    # limites
    topo = med + np.nan_to_num(err)
    base = med - (0 if t["erro.so_superior"] else np.nan_to_num(err))
    if tipo in ("box", "violino", "raincloud", "beeswarm") or mostrar_obs:
        topo = np.maximum(topo, np.where(np.isfinite(topo_obs), topo_obs, topo))
        base = np.minimum(base, np.where(np.isfinite(base_obs), base_obs, base))
    lo, hi = float(np.nanmin(base)), float(np.nanmax(topo))
    zero = tipo == "barras"
    if zero:
        lo = min(lo, 0.0)
    faixa = (hi - lo) or abs(hi) or 1
    letras = sp.letras if (sp.letras is not None and (sp.sig or t["letras.se_ns"])) else None
    tem_letras = letras is not None and t["letras.mostrar"] and any(letras)
    d = t["letras.distancia"] * faixa
    if tem_letras:
        alvo = {"acima dos dados": topo, "acima do erro": med + np.nan_to_num(err),
                "topo alinhado": np.full(k, hi)}[t["letras.posicao"]]
        for j, i in enumerate(ii):
            xl = pos[j] + (dx_med if tipo == "pontos" else 0)
            _texto_letra(t, ax, xl, alvo[j] + d, letras[i], H)
    colchetes = _colchetes(ax, t, ordem, pos, hi + (0.10 * faixa if tem_letras else 0.02 * faixa), faixa, H)
    folga = (0.14 if tem_letras else 0.06) + 0.09 * colchetes
    if H:
        faixa_x = faixa
        xmin = 0 if zero else lo - 0.06 * faixa_x
        xmax = hi + folga * faixa_x + (0.05 * faixa_x if tem_letras else 0)
        if t["eixos.y_min"] is not None:
            xmin = float(t["eixos.y_min"])
        if t["eixos.y_max"] is not None:
            xmax = float(t["eixos.y_max"])
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(k - 0.5, -0.5)
        ax.set_yticks(pos, _quebrar([tm.nome_nivel(t, o) for o in ordem], 22))
        ax.tick_params(axis="y", length=0)
    else:
        _limites_y(ax, t, lo, hi, folga, zero=zero)
        ax.set_xlim(-0.6, k - 0.4)
        larg_char = max(6, (_largura_ax_mm(ax) * 1.12 / max(k, 1)) / (0.165 * t["fonte.numeros"]))
        nomes = [tm.nome_nivel(t, o) for o in ordem]
        _rotulos_categoricos(ax, pos, nomes, larg_char, t)
    _anotacoes(ax, t)
    estilizar_eixo(ax, t, idioma, x_categorico=not H, y_categorico=H)
    if H:
        ax.xaxis.set_major_formatter(_formatador(t, t["eixos.y_decimais"], idioma))
        _rotulos_eixos(ax, t, sp.rotulo_y, sp.rotulo_x)
    else:
        _rotulos_eixos(ax, t, sp.rotulo_x, sp.rotulo_y)
    if t["series.colorir_niveis"] and legenda and t["legenda.posicao"] != "automática":
        hs = [Patch(facecolor=cores[j], label=tm.nome_nivel(t, ordem[j])) for j in range(k)]
        _legenda(ax, t, hs, [h.get_label() for h in hs], sp.rotulo_x)
    return ax


def _violino(ax, c, v, larg, cor, alfa, lw, metade, H):
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    if len(v) < 3 or np.std(v) == 0:
        return
    kde = stats.gaussian_kde(v)
    pad = 0.15 * (v.max() - v.min())
    y = np.linspace(v.min() - pad * 0.3, v.max() + pad * 0.3, 160)
    d = kde(y)
    d = d / d.max() * larg / 2
    esq = c if metade else c - d
    dirt = c + d
    if H:
        ax.fill_between(y, esq, dirt, color=to_rgba(cor, alfa), lw=0, zorder=1)
        ax.plot(y, dirt, color=cor, lw=lw, zorder=1)
        if not metade:
            ax.plot(y, esq, color=cor, lw=lw, zorder=1)
    else:
        ax.fill_betweenx(y, esq, dirt, color=to_rgba(cor, alfa), lw=0, zorder=1)
        ax.plot(dirt, y, color=cor, lw=lw, zorder=1)
        if not metade:
            ax.plot(esq, y, color=cor, lw=lw, zorder=1)


def _rotulos_categoricos(ax, pos, nomes, larg_char, t):
    """Quebra rótulos longos; se ainda assim não couberem, inclina (quando o usuário não fixou rotação)."""
    quebrados = _quebrar(nomes, larg_char)
    excede = any(max(len(l) for l in q.split("\n")) > larg_char * 1.05 or q.count("\n") >= 3 for q in quebrados)
    if excede and not t["eixos.x_rotacao"]:
        ax.set_xticks(pos, nomes)
        plt.setp(ax.get_xticklabels(), rotation=35, ha="right", rotation_mode="anchor")
    else:
        ax.set_xticks(pos, quebrados)
    ax.tick_params(axis="x", length=0)


def _largura_ax_mm(ax):
    try:
        return ax.get_position().width * ax.figure.get_figwidth() * 25.4
    except Exception:
        return 70.0


def _swarm(v, s_pt2, ax, H):
    """Deslocamentos de um beeswarm simples (em unidades de categoria)."""
    v = np.asarray(v, float)
    if len(v) < 2:
        return np.zeros(len(v))
    diam_pt = math.sqrt(s_pt2) * 1.05
    fig = ax.figure
    alt_in = ax.get_position().height * fig.get_figheight()
    larg_in = ax.get_position().width * fig.get_figwidth()
    lo, hi = np.nanmin(v), np.nanmax(v)
    faixa = (hi - lo) or 1.0
    # escala aproximada: faixa dos dados ocupa ~80% da altura do eixo
    por_pt_y = faixa / (0.8 * (larg_in if H else alt_in) * 72)
    n_cat = max(len(ax.get_xticks()), 1)
    por_pt_x = 1.0 / (((alt_in if H else larg_in) * 72) / max(n_cat, 6))
    dy = diam_pt * por_pt_y
    dxu = diam_pt * por_pt_x
    ordem = np.argsort(v)
    xs = np.zeros(len(v))
    colocados = []
    for i in ordem:
        cand = [0.0]
        for m in range(1, 60):
            cand += [m * dxu * 0.5, -m * dxu * 0.5]
        for c in cand:
            ok = True
            for (xj, yj) in colocados:
                if ((c - xj) / dxu) ** 2 + ((v[i] - yj) / dy) ** 2 < 1:
                    ok = False
                    break
            if ok:
                xs[i] = c
                colocados.append((c, v[i]))
                break
    lim = 0.4
    if np.max(np.abs(xs)) > lim:
        xs = xs * lim / np.max(np.abs(xs))
    return xs


def _colchetes(ax, t, ordem, pos, y0, faixa, H=False):
    itens = [c for c in (t["anot.colchetes"] or []) if str(c.get("de")) in ordem and str(c.get("ate")) in ordem]
    for n, c in enumerate(itens):
        a, b = pos[ordem.index(str(c["de"]))], pos[ordem.index(str(c["ate"]))]
        y = y0 + n * 0.09 * faixa
        h = 0.025 * faixa
        kw = dict(color=t["eixos.cor"], lw=t["eixos.espessura"], clip_on=False)
        if H:
            ax.plot([y, y + h, y + h, y], [a, a, b, b], **kw)
            ax.text(y + h * 1.6, (a + b) / 2, c.get("texto", "*"), va="center", ha="left", fontsize=t["fonte.letras"])
        else:
            ax.plot([a, a, b, b], [y, y + h, y + h, y], **kw)
            ax.text((a + b) / 2, y + h * 1.2, c.get("texto", "*"), ha="center", va="bottom", fontsize=t["fonte.letras"])
    return len(itens)


def _anotacoes(ax, t):
    for l in t["anot.linhas"] or []:
        try:
            v = float(l.get("valor"))
        except (TypeError, ValueError):
            continue
        ls = tm.ESTILOS_LINHA.get(l.get("estilo", "tracejada"), "--")
        kw = dict(color=l.get("cor", "#7A7A7A"), lw=float(l.get("esp", 0.6)), ls=ls, zorder=1)
        if l.get("eixo", "y") == "y":
            ax.axhline(v, **kw)
            if l.get("texto"):
                ax.text(1.0, v, " " + l["texto"], transform=ax.get_yaxis_transform(), va="center", ha="left",
                        fontsize=t["fonte.legenda"], color=kw["color"], clip_on=False)
        else:
            ax.axvline(v, **kw)
            if l.get("texto"):
                ax.text(v, 1.0, l["texto"], transform=ax.get_xaxis_transform(), va="bottom", ha="center",
                        fontsize=t["fonte.legenda"], color=kw["color"], clip_on=False)
    for tx in t["anot.textos"] or []:
        try:
            ax.text(float(tx.get("x", 0.5)), float(tx.get("y", 0.95)), tx.get("texto", ""), transform=ax.transAxes,
                    fontsize=float(tx.get("tam", t["fonte.tamanho"])), ha=tx.get("alinhar", "left"), va="top",
                    color=tx.get("cor", t["fonte.cor"]), fontstyle="italic" if tx.get("italico") else "normal")
        except (TypeError, ValueError):
            continue


# ============================================================================
# 2. Interação (x = níveis de A; grupos = níveis de B)
# ============================================================================
def desenhar_grupos(ax, sp: SpecGrupos, t, idioma="pt", legenda=True):
    A = _ordem(sp.A, t)
    B = [b for b in _ordem(sp.B, t)]
    ka, kb = len(A), len(B)
    tipo = t["medias.tipo"] if t["medias.tipo"] in ("pontos", "barras", "box") else "pontos"
    larg = min(t["medias.espaco_grupos"] / max(kb, 1), 0.32)
    ms = t["series.marcador_tam"]
    topo_g, base_g = -np.inf, np.inf
    handles, labels = [], []
    letras_pos = []
    for j, b in enumerate(B):
        cor = tm.cor_grupo(t, b, j)
        mk = tm.marcador_grupo(t, b, j)
        x = np.arange(ka) + (j - (kb - 1) / 2) * larg
        m = np.array([sp.medias.loc[a, b] if b in sp.medias.columns else np.nan for a in A], float)
        e_ep = np.array([sp.ep.loc[a, b] for a in A], float)
        e_dp = np.array([sp.dp.loc[a, b] for a in A], float) if sp.dp is not None else e_ep
        nn = np.array([sp.n.loc[a, b] for a in A], float) if sp.n is not None else np.full(ka, 2)
        e = np.nan_to_num(_barra_erro(t, e_ep, e_dp, nn))
        topo = m + e
        base = m - (0 if t["erro.so_superior"] else e)
        hach = tm.HACHURAS[j % len(tm.HACHURAS)] if t["medias.hachuras"] else ""
        if tipo == "barras":
            ax.bar(x, m, width=larg * 0.92, color=to_rgba(cor, 0.3 * t["medias.barra_alfa"] if not t["medias.hachuras"] else 0.15),
                   edgecolor=t["medias.contorno_cor"] if t["medias.contorno_esp"] else "none",
                   linewidth=t["medias.contorno_esp"], hatch=hach, zorder=1)
        if t["medias.obs"] and sp.obs is not None:
            for i, a in enumerate(A):
                v = sp.obs.loc[(sp.obs["A"].astype(str) == a) & (sp.obs["B"].astype(str) == b), "y"].to_numpy(float)
                if tipo == "box" and len(v) >= 2:
                    bp = ax.boxplot([v], positions=[x[i]], widths=larg * 0.8, patch_artist=True, manage_ticks=False,
                                    medianprops=dict(color=t["fonte.cor"], lw=0.9), showfliers=False,
                                    whiskerprops=dict(color=cor, lw=t["erro.esp"]), capprops=dict(color=cor, lw=t["erro.esp"]),
                                    boxprops=dict(edgecolor=cor, lw=0.6))
                    for bx in bp["boxes"]:
                        bx.set_facecolor(to_rgba(cor, 0.25))
                ax.scatter(x[i] + _jitter(len(v), larg * 0.18, i + 7 * j), v, s=t["medias.obs_tam"] * 0.8,
                           color=_cor_obs(t, cor), alpha=t["medias.obs_alfa"], lw=0, zorder=2, marker=mk)
                if len(v):
                    topo[i] = max(topo[i], np.nanmax(v))
                    base[i] = min(base[i], np.nanmin(v))
        if tipo != "box":
            ax.errorbar(x, m, yerr=_yerr(t, e) if t["erro.tipo"] != "nenhuma" else None, fmt=mk,
                        color=cor, ecolor=_cor_erro(t, cor), ms=ms * 0.9, elinewidth=t["erro.esp"],
                        capsize=t["erro.chapeu"], capthick=t["erro.esp"], zorder=4,
                        mfc="white" if t["series.vazados"] else cor,
                        mec=cor if t["series.vazados"] else t["series.marcador_borda_cor"],
                        mew=t["series.marcador_borda"] if not t["series.vazados"] else 0.8,
                        ls=tm.linha_grupo(t, b, j) if t["medias.conectar"] else "none",
                        lw=t["series.linha_esp"])
        handles.append(Line2D([], [], color=cor, marker=mk, ms=ms * 0.9, lw=t["series.linha_esp"] if t["medias.conectar"] else 0,
                              ls=tm.linha_grupo(t, b, j) if t["medias.conectar"] else "none", mfc="white" if t["series.vazados"] else cor,
                              mec=cor if t["series.vazados"] else t["series.marcador_borda_cor"]) if tipo != "barras"
                       else Patch(facecolor=to_rgba(cor, 0.35), edgecolor=cor, hatch=hach, lw=0.5))
        labels.append(tm.nome_nivel(t, b))
        topo_g, base_g = max(topo_g, np.nanmax(topo)), min(base_g, np.nanmin(base))
        for i, a in enumerate(A):
            L = ""
            if sp.letras is not None and a in sp.letras.index and b in sp.letras.columns:
                L = str(sp.letras.loc[a, b]).strip()
                if not t["letras.separar"]:
                    L = L.replace(" ", "")
            letras_pos.append((x[i], topo[i], m[i] + e[i], L))
    lo = 0.0 if tipo == "barras" and base_g >= 0 else base_g
    faixa = (topo_g - lo) or 1
    tem = t["letras.mostrar"] and any(l[3] for l in letras_pos)
    if tem:
        for (xx, tp, te, L) in letras_pos:
            yy = {"acima dos dados": tp, "acima do erro": te, "topo alinhado": topo_g}[t["letras.posicao"]]
            ax.text(xx, yy + t["letras.distancia"] * faixa, L, ha="center", va="bottom", fontsize=t["fonte.letras"],
                    clip_on=True, fontstyle="italic" if t["letras.italico"] else "normal",
                    rotation=90 if (len(L) > 3 and kb * ka > 16) else 0)
    _limites_y(ax, t, lo, topo_g, 0.16 if tem else 0.06, zero=tipo == "barras")
    larg_char = max(6, (_largura_ax_mm(ax) * 1.12 / max(ka, 1)) / (0.165 * t["fonte.numeros"]))
    _rotulos_categoricos(ax, np.arange(ka), [tm.nome_nivel(t, a) for a in A], larg_char, t)
    ax.set_xlim(-0.6, ka - 0.4)
    _anotacoes(ax, t)
    estilizar_eixo(ax, t, idioma, x_categorico=True)
    _rotulos_eixos(ax, t, sp.nome_A, sp.rotulo_y)
    if legenda:
        _legenda(ax, t, handles, labels, sp.nome_B, padrao="fora — acima")
    return ax


# ============================================================================
# 3. Regressão
# ============================================================================
def _banda(mod, xx):
    if mod is None or getattr(mod, "cov", None) is None:
        return None
    th = np.asarray(mod.params, float)
    G = np.zeros((len(xx), len(th)))
    for j in range(len(th)):
        h = 1e-6 * max(1.0, abs(th[j]))
        tp, tn = th.copy(), th.copy()
        tp[j] += h
        tn[j] -= h
        G[:, j] = (_f_modelo(mod.codigo, xx, tp, mod.desloc_log) - _f_modelo(mod.codigo, xx, tn, mod.desloc_log)) / (2 * h)
    var = np.einsum("ij,jk,ik->i", G, mod.cov, G)
    gl = mod.gl_erro if mod.gl_erro and np.isfinite(mod.gl_erro) else 30
    return stats.t.ppf(0.975, gl) * np.sqrt(np.clip(var, 0, None))


def _texto_modelo(mod, t, idioma):
    partes = []
    estilo_num = "en" if _sep(t, idioma) == "." else "pt"
    if t["reg.equacao"]:
        partes.append(mod.equacao(estilo_num, int(t["reg.digitos"])))
    if t["reg.r2"]:
        r2 = mod.r2_aj if (t["reg.r2_aj"] and mod.r2_aj is not None) else mod.r2
        nome = "R²aj" if (t["reg.r2_aj"] and mod.r2_aj is not None) else "R²"
        partes.append(f"{nome} = {_num(r2, t, idioma, 3)}")
    return partes


def desenhar_regressao(ax, sp: SpecRegressao, t, idioma="pt", legenda=True):
    ordem_rot = _ordem([c.rotulo for c in sp.curvas], t) if len(sp.curvas) > 1 else [str(sp.curvas[0].rotulo)]
    curvas = [c for c in sp.curvas if str(c.rotulo) in ordem_rot]
    curvas.sort(key=lambda c: ordem_rot.index(str(c.rotulo)))
    multi = len(curvas) > 1
    xs = np.concatenate([c.x for c in curvas])
    xr = (xs.max() - xs.min()) or 1.0
    ms = t["series.marcador_tam"]
    textos, handles = [], []
    ys_all = []
    for j, c in enumerate(curvas):
        g = str(c.rotulo) if multi else "série"
        cor = tm.cor_grupo(t, g, j) if multi else (t["grupos.cores"].get("série") or t["series.cor_unica"])
        mk = tm.marcador_grupo(t, g, j) if multi else (tm.MARCADORES.get(t["grupos.marcadores"].get("série"), "o"))
        ls = tm.linha_grupo(t, g, j) if multi else "-"
        off = (j - (len(curvas) - 1) / 2) * 0.012 * xr if multi else 0
        if t["medias.obs"] and c.obs_x is not None:
            ax.scatter(c.obs_x + off + _jitter(len(c.obs_x), 0.006 * xr * (t["medias.obs_disp"] / 0.14), j), c.obs_y,
                       s=t["medias.obs_tam"] * 0.85, color=_cor_obs(t, cor), alpha=t["medias.obs_alfa"], lw=0,
                       marker=mk, zorder=2)
            ys_all.append(c.obs_y)
        e = np.nan_to_num(_barra_erro(t, c.ep, c.dp, c.n))
        ax.errorbar(c.x + off, c.medias, yerr=_yerr(t, e) if t["erro.tipo"] != "nenhuma" else None, fmt=mk, color=cor,
                    ecolor=_cor_erro(t, cor), ms=ms, elinewidth=t["erro.esp"], capsize=t["erro.chapeu"],
                    capthick=t["erro.esp"], zorder=5, mfc="white" if t["series.vazados"] else cor,
                    mec=cor if t["series.vazados"] else t["series.marcador_borda_cor"],
                    mew=t["series.marcador_borda"] if not t["series.vazados"] else 0.8)
        ys_all += [c.medias + e, c.medias - e]
        ext = t["reg.estender"] * xr
        xx = np.linspace(c.x.min() - ext, c.x.max() + ext, 300)
        mod = c.modelo
        if c.sig and mod is not None:
            yy = mod.prever(xx)
            if t["reg.banda"]:
                b = _banda(mod, xx)
                if b is not None:
                    ax.fill_between(xx, yy - b, yy + b, color=cor, alpha=t["reg.banda_alfa"], lw=0, zorder=1)
            ax.plot(xx, yy, color=cor, lw=t["reg.esp"], ls=ls, zorder=3)
            if t["reg.marcar_ponto"]:
                xp = next((v for k_, v in mod.pontos.items() if isinstance(v, (int, float)) and k_.startswith("x ")), None)
                if xp is not None and c.x.min() <= xp <= c.x.max():
                    yp = float(mod.prever(np.array([xp]))[0])
                    ax.plot([xp, xp], [np.nanmin(c.medias), yp], color=cor, lw=0.5, ls=(0, (2, 2)), zorder=2)
                    ax.plot([xp], [yp], marker="|", ms=ms * 1.5, color=cor, zorder=4)
            textos.append((c.rotulo, _texto_modelo(mod, t, idioma), cor, mk, ls))
        else:
            ybar = float(np.sum(c.medias * c.n) / np.sum(c.n))
            if t["reg.media_ns"]:
                ax.plot(xx, np.full_like(xx, ybar), color=cor, lw=t["reg.esp"] * 0.8, ls=(0, (2, 2)), zorder=3)
            textos.append((c.rotulo, [f"ȳ = {_num(ybar, t, idioma, 4)} (ns)"], cor, mk, ls))
        handles.append(Line2D([], [], color=cor, marker=mk, ms=ms * 0.9, lw=t["reg.esp"], ls=ls,
                              mfc="white" if t["series.vazados"] else cor,
                              mec=cor if t["series.vazados"] else t["series.marcador_borda_cor"]))
    ys = np.concatenate([np.ravel(y) for y in ys_all]) if ys_all else np.array([0, 1])
    lo, hi = float(np.nanmin(ys)), float(np.nanmax(ys))
    faixa = (hi - lo) or 1
    ax.set_xticks(np.unique(xs)) if not t["eixos.x_passo"] else None
    xmin = t["eixos.x_min"] if t["eixos.x_min"] is not None else xs.min() - 0.06 * xr
    xmax = t["eixos.x_max"] if t["eixos.x_max"] is not None else xs.max() + 0.06 * xr
    ax.set_xlim(xmin, xmax)
    pos = t["reg.posicao"]
    mostrar_txt = t["reg.equacao"] or t["reg.r2"]
    if pos == "automática":
        pos = "abaixo do gráfico" if multi else None
        if not multi:
            c = curvas[0]
            meio = max(len(c.x) // 2, 1)
            crescente = np.mean(c.medias[:meio]) <= np.mean(c.medias[-meio:])
            pos = "sup. esquerda" if crescente else "sup. direita"
    folga = 0.06
    if mostrar_txt and pos != "abaixo do gráfico" and pos and pos.startswith("sup"):
        n_l = sum(len(_quebrar_eq(tx, t)) for _, tx, *_ in textos)
        folga = 0.06 + 0.085 * n_l * t["fonte.equacao"] / 6.5
    _limites_y(ax, t, lo, hi, folga)
    if mostrar_txt:
        if not multi:
            linhas = _quebrar_eq(textos[0][1], t)
            if pos == "abaixo do gráfico":
                ax.text(0, -0.2, "\n".join(linhas), transform=ax.transAxes, va="top", ha="left",
                        fontsize=t["fonte.equacao"], linespacing=1.35)
            else:
                xa = 0.03 if "esquerda" in pos else 0.97
                ya, va = (0.98, "top") if pos.startswith("sup") else (0.03, "bottom")
                ax.text(xa, ya, "\n".join(linhas), transform=ax.transAxes, va=va, ha="left" if xa < 0.5 else "right",
                        fontsize=t["fonte.equacao"], linespacing=1.35)
        elif legenda:
            chars = int(_largura_ax_mm(ax) / (0.19 * t["fonte.equacao"]))
            labs = []
            for r, tx, *_ in textos:
                s = f"{tm.nome_nivel(t, r)}: " + "; ".join(tx)
                labs.append("\n".join(textwrap.wrap(s, max(chars - 8, 20), break_long_words=False)))
            mapa_pos = {"abaixo do gráfico": "fora — abaixo", "sup. esquerda": "dentro — sup. esquerda",
                        "sup. direita": "dentro — sup. direita", "inf. esquerda": "dentro — inf. esquerda",
                        "inf. direita": "dentro — inf. direita"}
            tt = dict(t)
            if t["legenda.posicao"] == "automática":
                tt["legenda.posicao"] = mapa_pos.get(pos, "fora — abaixo")
            tt["fonte.legenda"] = t["fonte.equacao"]
            tt["legenda.colunas"] = t["legenda.colunas"] or 1
            leg = _legenda(ax, tt, handles, labs, sp.titulo_legenda, "fora — abaixo")
            if leg is not None and tt["legenda.posicao"] == "fora — abaixo":
                leg.set_bbox_to_anchor((-0.02 + t["legenda.dx"], -0.13 - 0.02 * t["fonte.titulo_eixo"] / 7 + t["legenda.dy"]))
    elif multi and legenda:
        _legenda(ax, t, handles, [tm.nome_nivel(t, r) for r, *_ in textos], sp.titulo_legenda, "dentro — inf. direita")
    _anotacoes(ax, t)
    estilizar_eixo(ax, t, idioma)
    _rotulos_eixos(ax, t, sp.rotulo_x, sp.rotulo_y)
    return ax


def _quebrar_eq(partes, t):
    linhas = []
    for p in partes:
        linhas += p.split("; ")
    return linhas


# ============================================================================
# 4. Perfil em profundidade
# ============================================================================
def desenhar_perfil(ax, sp: SpecPerfil, t, idioma="pt", legenda=True):
    camadas = _ordem(sp.camadas, t) if False else [str(c) for c in sp.camadas]
    ordem_s = _ordem([s.get("rotulo") for s in sp.series], t) if len(sp.series) > 1 else None
    series = sp.series if ordem_s is None else sorted([s for s in sp.series if str(s.get("rotulo")) in ordem_s],
                                                       key=lambda s: ordem_s.index(str(s.get("rotulo"))))
    multi = len(series) > 1
    kc = len(camadas)
    pos = np.arange(kc)
    ms = t["series.marcador_tam"]
    handles, labels = [], []
    for j, s in enumerate(series):
        g = str(s.get("rotulo")) if multi else "série"
        cor = tm.cor_grupo(t, g, j) if multi else (t["grupos.cores"].get("série") or t["series.cor_unica"])
        mk = tm.marcador_grupo(t, g, j) if multi else "o"
        ls = tm.linha_grupo(t, g, j) if multi else "-"
        off = (j - (len(series) - 1) / 2) * min(0.05, 0.3 / max(len(series), 1)) if multi else 0
        m = np.asarray(s["medias"], float)
        e = np.nan_to_num(_barra_erro(t, s["ep"], s["dp"], s["n"]))
        ax.plot(m, pos + off, color=cor, lw=t["series.linha_esp"], ls=ls, zorder=2)
        ax.errorbar(m, pos + off, xerr=_yerr(t, e) if t["erro.tipo"] != "nenhuma" else None, fmt=mk, color=cor,
                    ecolor=_cor_erro(t, cor), ms=ms, elinewidth=t["erro.esp"], capsize=t["erro.chapeu"], zorder=3,
                    mfc="white" if t["series.vazados"] else cor,
                    mec=cor if t["series.vazados"] else t["series.marcador_borda_cor"], mew=t["series.marcador_borda"])
        handles.append(Line2D([], [], color=cor, marker=mk, ms=ms * 0.9, lw=t["series.linha_esp"], ls=ls,
                              mec=t["series.marcador_borda_cor"]))
        labels.append(tm.nome_nivel(t, s.get("rotulo")))
    ax.set_yticks(pos, [tm.nome_nivel(t, c) for c in camadas])
    ax.set_ylim(kc - 0.6, -0.4)
    if t["eixos.x_min"] is not None or t["eixos.x_max"] is not None:
        a, b = ax.get_xlim()
        ax.set_xlim(t["eixos.x_min"] if t["eixos.x_min"] is not None else a, t["eixos.x_max"] if t["eixos.x_max"] is not None else b)
    tt = dict(t)
    tt["eixos.inferior"], tt["eixos.superior"] = t["eixos.superior"], True
    estilizar_eixo(ax, tt, idioma, y_categorico=True)
    ax.xaxis.set_ticks_position("top")
    ax.xaxis.set_label_position("top")
    _rotulos_eixos(ax, t, sp.rotulo_valor, sp.rotulo_camada)
    _anotacoes(ax, t)
    if multi and legenda:
        _legenda(ax, t, handles, labels, sp.titulo_legenda, "fora — abaixo")
        leg = ax.get_legend()
        if leg is not None and t["legenda.posicao"] == "automática":
            leg.set_bbox_to_anchor((0 + t["legenda.dx"], -0.02 + t["legenda.dy"]))
    return ax


# ============================================================================
# 5. Correlação
# ============================================================================
def desenhar_correlacao(ax, sp: SpecCorrelacao, t, idioma="pt", legenda=True):
    k = len(sp.nomes)
    cmap = LinearSegmentedColormap.from_list("div", tm.DIVERGENTES[t["cor.paleta"]])
    completa = t["cor.triangulo"] == "completa"
    fs = max(t["fonte.numeros"] - 0.5 - max(0, k - 8) * 0.35, 4.0)
    for i in range(k):
        for j in range(k):
            if not completa and j >= i:
                continue
            if completa and i == j:
                ax.add_patch(Rectangle((j - 0.47, i - 0.47), 0.94, 0.94, color="#EFEFEF", lw=0))
                continue
            v = sp.R[i, j]
            if not np.isfinite(v):
                continue
            ax.add_patch(Rectangle((j - 0.47, i - 0.47), 0.94, 0.94, color=cmap((v + 1) / 2), lw=0))
            cor_txt = "white" if abs(v) > 0.6 else t["fonte.cor"]
            if t["cor.valores"]:
                s = f"{v:.{int(t['cor.decimais'])}f}".replace(".", _sep(t, idioma)).replace("-", "−")
                ax.text(j, i - (0.08 if t["cor.estrelas"] else 0), s, ha="center", va="center", color=cor_txt, fontsize=fs)
            if t["cor.estrelas"]:
                p = sp.P[i, j]
                est = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
                if est:
                    ax.text(j, i + (0.25 if t["cor.valores"] else 0), est, ha="center", va="center", color=cor_txt,
                            fontsize=fs - 0.5)
    nomes = [tm.nome_nivel(t, n) for n in sp.nomes]
    if completa:
        ax.set_xlim(-0.5, k - 0.5)
        ax.set_ylim(k - 0.5, -0.5)
        ax.set_xticks(range(k), _quebrar(nomes, 12))
        ax.set_yticks(range(k), _quebrar(nomes, 18))
    else:
        ax.set_xlim(-0.5, k - 1.5)
        ax.set_ylim(k - 0.5, 0.5)
        ax.set_xticks(range(k - 1), _quebrar(nomes[:-1], 12))
        ax.set_yticks(range(1, k), _quebrar(nomes[1:], 18))
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    ax.set_aspect("equal")
    if legenda:
        sm = matplotlib.cm.ScalarMappable(cmap=cmap, norm=matplotlib.colors.Normalize(-1, 1))
        cb = ax.figure.colorbar(sm, ax=ax, fraction=0.04, pad=0.02, ticks=[-1, -0.5, 0, 0.5, 1], shrink=0.85)
        cb.outline.set_visible(False)
        cb.ax.tick_params(length=2, width=0.5, labelsize=t["fonte.numeros"])
        cb.ax.set_yticklabels([s.replace(".", _sep(t, idioma)) for s in ["−1", "−0.5", "0", "0.5", "1"]])
        cb.set_label(f"r ({sp.metodo})" if idioma == "en" else f"r de {sp.metodo}", fontsize=t["fonte.titulo_eixo"])
        if t["cor.estrelas"]:
            nota = "* p < 0,05; ** p < 0,01; *** p < 0,001" if idioma == "pt" else "* P < 0.05; ** P < 0.01; *** P < 0.001"
            ax.text(1.0, 1.0, nota, transform=ax.transAxes, ha="right", va="top", fontsize=t["fonte.legenda"] - 0.5,
                    color="#6B6B6B")
    return ax


# ============================================================================
# 6. PCA
# ============================================================================
def desenhar_pca(ax, sp: SpecPCA, t, idioma="pt", legenda=True):
    cx, cy = int(t["pca.eixo_x"]) - 1, int(t["pca.eixo_y"]) - 1
    ncp = sp.escores.shape[1]
    cx, cy = min(cx, ncp - 1), min(cy, ncp - 1)
    grupos = np.asarray([str(g) for g in sp.grupos_obs])
    ordem = _ordem(list(dict.fromkeys(grupos)), t)
    eli = {"automático": len(ordem) <= 5, "sim": True, "não": False}[t["pca.elipses"]]
    ax.axhline(0, color="#BDBDBD", lw=0.4, zorder=0)
    ax.axvline(0, color="#BDBDBD", lw=0.4, zorder=0)
    E = sp.escores[:, [cx, cy]]
    for j, g in enumerate(ordem):
        sel = grupos == g
        cor, mk = tm.cor_grupo(t, g, j), tm.marcador_grupo(t, g, j)
        ax.scatter(E[sel, 0], E[sel, 1], s=t["pca.tam_pontos"], color=cor, alpha=max(t["medias.obs_alfa"], 0.6), lw=0,
                   marker=mk, label=tm.nome_nivel(t, g), zorder=3)
        if eli and sel.sum() >= 3:
            _elipse(ax, E[sel], cor)
    pos_txt = []
    if t["pca.setas"]:
        C = sp.cargas[:, [cx, cy]]
        esc = np.abs(E).max() / max(np.abs(C).max(), 1e-9) * 0.85
        for i in range(len(sp.nomes)):
            x, y = C[i] * esc
            ax.annotate("", xy=(x, y), xytext=(0, 0), zorder=4,
                        arrowprops=dict(arrowstyle="-|>,head_length=0.35,head_width=0.18", color=t["pca.setas_cor"], lw=0.6))
            pos_txt.append([x * 1.1, y * 1.1])
        pos_txt = _repelir(np.array(pos_txt), np.abs(E).max() * 0.07)
        for (x, y), nm, c in zip(pos_txt, sp.nomes, C):
            ax.text(x, y, tm.nome_nivel(t, nm), fontsize=t["fonte.legenda"], color=t["pca.setas_cor"],
                    ha="left" if c[0] >= 0 else "right", va="center", zorder=5)
    if sp.rotulos_pontos is not None:
        for (x, y), r in zip(E, sp.rotulos_pontos):
            ax.text(x, y, " " + str(r), fontsize=t["fonte.legenda"] - 1, color="#6B6B6B", va="center")
    tudo = np.vstack([E] + ([np.asarray(pos_txt)] if len(pos_txt) else []))
    lo, hi = tudo.min(axis=0), tudo.max(axis=0)
    mg = (hi - lo) * 0.08
    ax.set_xlim(t["eixos.x_min"] if t["eixos.x_min"] is not None else lo[0] - mg[0],
                t["eixos.x_max"] if t["eixos.x_max"] is not None else hi[0] + mg[0] * 2.2)
    ax.set_ylim(t["eixos.y_min"] if t["eixos.y_min"] is not None else lo[1] - mg[1],
                t["eixos.y_max"] if t["eixos.y_max"] is not None else hi[1] + mg[1])
    pre = "CP" if idioma == "pt" else "PC"
    estilizar_eixo(ax, t, idioma)
    _rotulos_eixos(ax, t, f"{pre}{cx + 1} ({_num(sp.explicada[cx] * 100, t, idioma, 3)}%)",
                   f"{pre}{cy + 1} ({_num(sp.explicada[cy] * 100, t, idioma, 3)}%)")
    if legenda and len(ordem) > 1:
        hs, ls = ax.get_legend_handles_labels()
        _legenda(ax, t, hs, ls, sp.titulo_legenda, "fora — direita")
    return ax


def _repelir(p, escala, iter_=200):
    p = p.astype(float).copy()
    for _ in range(iter_):
        mov = False
        for i in range(len(p)):
            for j in range(i + 1, len(p)):
                d = p[i] - p[j]
                dist = np.hypot(*d)
                if dist < escala:
                    if dist < 1e-9:
                        d, dist = np.array([0.0, 1.0]), 1.0
                    aj = (escala - dist) / 2 * d / dist
                    aj[1] *= 1.6
                    p[i] += aj
                    p[j] -= aj
                    mov = True
        if not mov:
            break
    return p


def _elipse(ax, pts, cor, conf=0.95):
    cov = np.cov(pts, rowvar=False)
    if not np.all(np.isfinite(cov)) or np.linalg.det(cov) <= 0:
        return
    vals, vecs = np.linalg.eigh(cov)
    o = vals.argsort()[::-1]
    vals, vecs = vals[o], vecs[:, o]
    ang = math.degrees(math.atan2(vecs[1, 0], vecs[0, 0]))
    k = math.sqrt(stats.chi2.ppf(conf, 2))
    w, h = 2 * k * np.sqrt(vals)
    ax.add_patch(Ellipse(pts.mean(axis=0), w, h, angle=ang, facecolor=cor, alpha=0.10, edgecolor=cor, lw=0.6, zorder=1))


# ============================================================================
# 7. Diagnóstico (figura própria, 4 painéis)
# ============================================================================
def figura_diagnostico(sp: SpecDiagnostico, t, idioma="pt"):
    pt = idioma == "pt"
    with plt.rc_context(rc(t)):
        alt = t["tela.altura_mm"] or max(t["tela.largura_mm"] * 0.29, 45)
        fig, axs = plt.subplots(1, 4, figsize=(t["tela.largura_mm"] * MM, alt * MM), layout="constrained")
        cor, a = t["series.cor_unica"], t["medias.obs_alfa"]
        r = np.asarray(sp.res, float)
        n = len(r)
        s = t["medias.obs_tam"] * 1.1
        ax = axs[0]
        ax.scatter(sp.ajust, sp.rstd, s=s, color=cor, alpha=a, lw=0)
        ax.axhline(0, color="#6B6B6B", lw=0.5, ls=(0, (2, 2)))
        for lim in (-3, 3):
            ax.axhline(lim, color="#A6461E", lw=0.5, ls=(0, (1, 2)))
        _rotulos_eixos(ax, {**t, "eixos.rotulo_x": "", "eixos.rotulo_y": ""}, "Valores ajustados" if pt else "Fitted values",
                       "Resíduo studentizado" if pt else "Studentized residual")
        ax = axs[1]
        z = (r - r.mean()) / (r.std(ddof=1) or 1)
        pp = (np.arange(1, n + 1) - 0.375) / (n + 0.25)
        teo = stats.norm.ppf(pp)
        i = np.arange(1, n + 1)
        lo = stats.norm.ppf(stats.beta.ppf(0.025, i, n - i + 1))
        hi = stats.norm.ppf(stats.beta.ppf(0.975, i, n - i + 1))
        ax.fill_between(teo, lo, hi, color="#E4D5C7", lw=0)
        ax.plot(teo, teo, color="#6B6B6B", lw=0.6)
        ax.scatter(teo, np.sort(z), s=s, color=cor, alpha=a, lw=0, zorder=3)
        _rotulos_eixos(ax, {**t, "eixos.rotulo_x": "", "eixos.rotulo_y": ""}, "Quantis teóricos" if pt else "Theoretical quantiles",
                       "Quantis amostrais" if pt else "Sample quantiles")
        ax = axs[2]
        ax.hist(r, bins=max(5, min(20, int(np.sqrt(n)) + 2)), color="#E4D5C7", edgecolor="white", lw=0.5, density=True)
        xx = np.linspace(r.min(), r.max(), 200)
        ax.plot(xx, stats.norm.pdf(xx, r.mean(), r.std(ddof=1) or 1), color=cor, lw=0.9)
        _rotulos_eixos(ax, {**t, "eixos.rotulo_x": "", "eixos.rotulo_y": ""}, "Resíduo" if pt else "Residual",
                       "Densidade" if pt else "Density")
        ax = axs[3]
        g = np.asarray(sp.trat)
        ordem = list(dict.fromkeys(g))
        for k, gg in enumerate(ordem):
            v = r[g == gg]
            ax.scatter(np.full(len(v), k) + _jitter(len(v), 0.15, k), v, s=s * 0.8, color=cor, alpha=a, lw=0)
            if len(v) > 1:
                ax.plot([k - 0.25, k + 0.25], [np.median(v)] * 2, color=t["fonte.cor"], lw=0.8)
        ax.axhline(0, color="#6B6B6B", lw=0.5, ls=(0, (2, 2)))
        passo = int(np.ceil(len(ordem) / 8))
        ax.set_xticks(range(0, len(ordem), passo), [str(k + 1) for k in range(0, len(ordem), passo)])
        ax.tick_params(axis="x", length=0)
        _rotulos_eixos(ax, {**t, "eixos.rotulo_x": "", "eixos.rotulo_y": ""}, "Tratamento" if pt else "Treatment",
                       "Resíduo" if pt else "Residual")
        for k, ax in enumerate(axs):
            estilizar_eixo(ax, t, idioma, x_categorico=k == 3)
            ax.text(t["painel.dx"], t["painel.dy"], tm.rotulo_painel(t["painel.estilo"], k), transform=ax.transAxes,
                    fontsize=t["painel.tamanho"], fontweight=t["painel.peso"], ha="right", va="bottom")
    return fig


# ============================================================================
# Montagem
# ============================================================================
def desenhar_dendrograma(ax, sp, t, idioma="pt", legenda=True):
    from scipy.cluster import hierarchy as h
    D = h.dendrogram(sp.ligacao, labels=[tm.nome_nivel(t, r) for r in sp.rotulos], no_plot=True,
                     orientation="right")
    grupos_obs = sp.clusters
    folhas = D["ivl"]
    # cor de cada folha pelo grupo (critério de Mojena)
    cor_folha = {}
    if grupos_obs is not None:
        nomes = [tm.nome_nivel(t, r) for r in sp.rotulos]
        for nome, g in zip(nomes, grupos_obs):
            cor_folha[nome] = tm.cor_grupo(t, f"Grupo {int(g)}", int(g) - 1)
    lw = t["series.linha_esp"]
    n = len(folhas)
    for xs, ys in zip(D["dcoord"], D["icoord"]):
        ax.plot(xs, ys, color=t["eixos.cor"], lw=lw, solid_capstyle="butt")
    ax.set_yticks([5 + 10 * i for i in range(n)], folhas)
    for lab in ax.get_yticklabels():
        c = cor_folha.get(lab.get_text())
        if c:
            lab.set_color(c)
    if sp.corte:
        ax.axvline(sp.corte, color=t["eixos.cor"], lw=lw * 0.7, ls=(0, (3, 2)))
        ax.text(sp.corte, n * 10 + 1, " Mojena", fontsize=t["fonte.legenda"], va="bottom", ha="left")
    ax.set_ylim(0, n * 10 + 4)
    tt = {**t, "eixos.esquerda": False, "eixos.inferior": True}
    estilizar_eixo(ax, tt, idioma, y_categorico=True)
    ax.tick_params(axis="y", length=0)
    _rotulos_eixos(ax, t, "Distância euclidiana (variáveis padronizadas)" if idioma == "pt"
                   else "Euclidean distance (standardized variables)", "")
    return ax


DESENHAR = {"dendrograma": desenhar_dendrograma, "medias": desenhar_medias, "grupos": desenhar_grupos, "regressao": desenhar_regressao,
            "perfil": desenhar_perfil, "correlacao": desenhar_correlacao, "pca": desenhar_pca}


def _altura_padrao(sp, t):
    W = t["tela.largura_mm"]
    if sp.tipo == "perfil":
        return max(W * 0.9, 18 * len(sp.camadas) + 30)
    if sp.tipo == "correlacao":
        return W * 0.88
    if sp.tipo == "pca":
        return W * 0.8
    if sp.tipo == "dendrograma":
        return max(40, 6 * len(sp.rotulos) + 22)
    if sp.tipo == "medias" and t["medias.horizontal"]:
        return max(50, 6.5 * len(sp.niveis) + 22)
    if sp.tipo == "regressao" and len(sp.curvas) > 1 and (t["reg.equacao"] or t["reg.r2"]):
        return W * t["tela.proporcao"] + 7 * len(sp.curvas) * t["fonte.equacao"] / 6.5
    return W * t["tela.proporcao"]


def figura(sp, t, idioma="pt"):
    """Cria a figura completa de uma especificação, no tamanho exato do tema."""
    if sp.tipo == "diagnostico":
        return figura_diagnostico(sp, t, idioma)
    W = t["tela.largura_mm"]
    H = t["tela.altura_mm"] or _altura_padrao(sp, t)
    quebra = (t["eixos.quebra_de"] is not None and t["eixos.quebra_ate"] is not None
              and float(t["eixos.quebra_ate"]) > float(t["eixos.quebra_de"])
              and sp.tipo in ("medias", "grupos", "regressao") and not t["medias.horizontal"])
    with plt.rc_context(rc(t)):
        if not quebra:
            fig, ax = plt.subplots(figsize=(W * MM, H * MM), layout="constrained")
            DESENHAR[sp.tipo](ax, sp, t, idioma)
            if t["tela.titulo"]:
                ax.set_title(t["tela.titulo"], loc="left", fontsize=t["fonte.tamanho"], fontweight=t["fonte.peso_titulos"])
        else:
            fig = _figura_quebrada(sp, t, idioma, W, H)
    return fig


def _figura_quebrada(sp, t, idioma, W, H):
    q0, q1 = float(t["eixos.quebra_de"]), float(t["eixos.quebra_ate"])
    fig = plt.figure(figsize=(W * MM, H * MM), layout="constrained")
    # desenha uma vez para obter limites automáticos
    tmp = fig.add_subplot(111)
    DESENHAR[sp.tipo](tmp, sp, t, idioma, legenda=False)
    y0, y1 = tmp.get_ylim()
    fig.delaxes(tmp)
    alto, baixo = max(y1 - q1, 1e-9), max(q0 - y0, 1e-9)
    gs = fig.add_gridspec(2, 1, height_ratios=[alto, baixo], hspace=0.05)
    a1 = fig.add_subplot(gs[0])
    a2 = fig.add_subplot(gs[1], sharex=a1)
    t_sup = {**t, "eixos.inferior": False, "eixos.rotulo_x": " ", "eixos.y_min": q1, "eixos.y_max": y1}
    t_inf = {**t, "eixos.y_min": y0, "eixos.y_max": q0}
    DESENHAR[sp.tipo](a1, sp, t_sup, idioma, legenda=True)
    DESENHAR[sp.tipo](a2, sp, t_inf, idioma, legenda=False)
    a1.set_ylim(q1, y1)
    a2.set_ylim(y0, q0)
    a1.set_xlabel("")
    a1.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
    rot_y = a2.get_ylabel()
    a1.set_ylabel("")
    a2.set_ylabel("")
    fig.supylabel(rot_y, fontsize=t["fonte.titulo_eixo"], fontweight=t["fonte.peso_titulos"])
    d = 0.012
    kw = dict(color=t["eixos.cor"], clip_on=False, lw=t["eixos.espessura"])
    a1.plot((-d, +d), (-d * 3, +d * 3), transform=a1.transAxes, **kw)
    a2.plot((-d, +d), (1 - d * 3, 1 + d * 3), transform=a2.transAxes, **kw)
    return fig


def painel(itens, linhas, colunas, t_painel, idioma="pt", largura_mm=None, altura_mm=None, ordem_rotulos=True):
    """itens: lista de (spec, tema). Monta grade linhas × colunas (itens a mais são ignorados)."""
    W = largura_mm or t_painel["tela.largura_mm"]
    H = altura_mm or (W / colunas * 0.85 * linhas)
    with plt.rc_context(rc(t_painel)):
        fig = plt.figure(figsize=(W * MM, H * MM), layout="constrained")
        gs = fig.add_gridspec(linhas, colunas, wspace=t_painel["painel.wspace"] * 0.1,
                              hspace=t_painel["painel.hspace"] * 0.1)
        fig.get_layout_engine().set(wspace=t_painel["painel.wspace"] * 0.1, hspace=t_painel["painel.hspace"] * 0.1)
    for k, (sp, t) in enumerate(itens[: linhas * colunas]):
        if sp is None:
            continue
        r_, c_ = divmod(k, colunas)
        with plt.rc_context(rc(t)):
            ax = fig.add_subplot(gs[r_, c_])
            if sp.tipo == "diagnostico":
                ax.text(0.5, 0.5, "Diagnóstico não pode\nser usado em painel", ha="center", va="center",
                        transform=ax.transAxes)
                ax.axis("off")
                continue
            DESENHAR[sp.tipo](ax, sp, t, idioma)
            rot = tm.rotulo_painel(t_painel["painel.estilo"], k)
            if rot:
                ax.text(t_painel["painel.dx"] - 0.12, t_painel["painel.dy"], rot, transform=ax.transAxes,
                        fontsize=t_painel["painel.tamanho"], fontweight=t_painel["painel.peso"], ha="left", va="bottom",
                        family=familia(t_painel))
    return fig


# ============================================================================
# Exportação
# ============================================================================
def exportar(fig, t, formatos=("png", "svg", "pdf", "tiff")) -> dict:
    out = {}
    transp = bool(t["tela.transparente"])
    for fmt in formatos:
        buf = io.BytesIO()
        kw = dict(format=fmt, transparent=transp, facecolor="none" if transp else t["tela.fundo"])
        if fmt in ("png", "tiff"):
            kw["dpi"] = int(t["tela.dpi"])
        if fmt == "tiff":
            kw["pil_kwargs"] = {"compression": "tiff_lzw"}
        with plt.rc_context({"svg.fonttype": "none", "pdf.fonttype": 42}):
            fig.savefig(buf, **kw)
        out[fmt] = buf.getvalue()
    return out


def previa(fig, dpi=170) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi)
    return buf.getvalue()


# ============================================================================
# Geração segura (prévia e arquivos podem rodar em threads diferentes)
# ============================================================================
import threading  # noqa: E402

_TRAVA = threading.RLock()


def gerar_previa(sp, t, idioma="pt", dpi=150) -> bytes:
    with _TRAVA:
        fig = figura(sp, t, idioma)
        try:
            return previa(fig, dpi)
        finally:
            plt.close(fig)


def gerar_arquivo(sp, t, fmt, idioma="pt") -> bytes:
    with _TRAVA:
        fig = figura(sp, t, idioma)
        try:
            return exportar(fig, t, (fmt,))[fmt]
        finally:
            plt.close(fig)


def gerar_painel(itens, linhas, colunas, t_painel, idioma="pt", largura_mm=None, altura_mm=None, fmt=None, dpi=150):
    with _TRAVA:
        fig = painel(itens, linhas, colunas, t_painel, idioma, largura_mm, altura_mm)
        try:
            if fmt is None:
                return previa(fig, dpi)
            return exportar(fig, t_painel, (fmt,))[fmt]
        finally:
            plt.close(fig)
