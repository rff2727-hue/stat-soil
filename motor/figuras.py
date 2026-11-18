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
    estat: dict | None = None                # teste que sustenta a figura: F, gl1, gl2, p, eta2p, n, metodo
    pares: list | None = None                # comparações par a par: g1, g2, p, sig

    def grupos(self):
        return [str(n) for n in self.niveis]


@dataclass
class SpecEmpilhado:
    """Barras empilhadas: categorias no eixo e componentes (ex.: frações de P) como segmentos."""
    categorias: list
    componentes: list
    valores: pd.DataFrame                    # índice = categorias, colunas = componentes (médias)
    ep_total: np.ndarray | None = None       # erro-padrão do total por categoria
    rotulo_x: str = ""
    rotulo_y: str = ""
    titulo_legenda: str = ""
    tipo: str = "empilhado"

    def grupos(self):
        return [str(c) for c in self.componentes]


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
    qm_erro: float | None = None             # para a faixa de predição
    ajustes: list = field(default_factory=list)   # modelos alternativos (para trocar no Estúdio)
    chave: tuple | None = None               # (fator, condição) — liga a curva à escolha de modelo


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


TIPOS_NOME = {"empilhado": "Barras empilhadas", "medias": "Médias", "grupos": "Interação", "regressao": "Regressão", "perfil": "Perfil",
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
        "svg.fonttype": "path" if t["tela.svg_texto"] == "contornos" else "none",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "mathtext.default": "regular",
        "mathtext.fontset": "custom",
        "mathtext.rm": familia(t),
        "mathtext.it": f"{familia(t)}:italic",
        "mathtext.bf": f"{familia(t)}:bold",
        "hatch.linewidth": t["medias.hachura_esp"],
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


def _formatador(t, decimais, idioma, fator=0):
    sep = _sep(t, idioma)
    milhar = bool(t.get("eixos.milhar"))
    sep_mil = "." if sep == "," else ","
    div = 10.0 ** int(fator or 0)

    def f(v, pos=None):
        v = v / div
        if decimais is None or decimais < 0:
            s = f"{v:g}" if abs(v) < 1e6 else f"{v:.3g}"
            if milhar and abs(v) >= 1000 and "e" not in s:
                d = len(s.split(".")[1]) if "." in s else 0
                s = f"{v:,.{d}f}"
        else:
            s = f"{v:,.{decimais}f}" if milhar else f"{v:.{decimais}f}"
        if milhar:
            s = s.replace(",", "\0").replace(".", sep).replace("\0", sep_mil)
        else:
            s = s.replace(".", sep)
        return s.replace("-", "−")
    return ticker.FuncFormatter(f)


ESCALAS = {"log10": ("log", 10), "log2": ("log", 2), "ln": ("log", math.e)}


def _escala(t, eixo):
    e = t.get(f"eixos.{eixo}_escala", "linear")
    if eixo == "y" and e == "linear" and t.get("eixos.y_log"):
        e = "log10"
    return e


def _aplicar_escala(ax, t, eixo, idioma, decimais):
    """Escalas do OriginPro mais usadas: log10, log2, ln e raiz quadrada."""
    e = _escala(t, eixo)
    if e == "linear":
        return False
    axis = ax.yaxis if eixo == "y" else ax.xaxis
    setter = ax.set_yscale if eixo == "y" else ax.set_xscale
    if e == "raiz quadrada":
        setter("function", functions=(lambda v: np.sqrt(np.clip(v, 0, None)), lambda v: np.square(v)))
        axis.set_major_formatter(_formatador(t, decimais, idioma))
        return True
    base = ESCALAS[e][1]
    setter("log", base=base)
    if e == "ln":
        sup = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")
        axis.set_major_locator(ticker.LogLocator(base=math.e))
        axis.set_major_formatter(ticker.FuncFormatter(
            lambda v, p=None: "e" + str(int(round(math.log(v)))).translate(sup) if v > 0 else ""))
    else:
        lo, hi = (ax.get_ylim() if eixo == "y" else ax.get_xlim())
        lo, hi = max(min(lo, hi), 1e-12), max(lo, hi)
        decadas = math.log(hi / lo, base) if hi > lo else 0
        subs = (1.0,) if decadas >= 3 else (1.0, 2.0, 5.0) if decadas >= 1.2 else tuple(np.arange(1.0, base if base > 2 else 2.0))
        if base == 2:
            subs = (1.0,) if decadas >= 2 else (1.0, 1.5)
        axis.set_major_locator(ticker.LogLocator(base=base, subs=subs))
        axis.set_major_formatter(_formatador(t, decimais, idioma))
    axis.set_minor_formatter(ticker.NullFormatter())
    return True


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
        if not _aplicar_escala(ax, t, "y", idioma, t["eixos.y_decimais"]):
            ax.yaxis.set_major_formatter(_formatador(t, t["eixos.y_decimais"], idioma, t["eixos.y_fator"]))
            if t["eixos.y_passo"]:
                ax.yaxis.set_major_locator(ticker.MultipleLocator(float(t["eixos.y_passo"])))
            if t["eixos.marcas_menores"]:
                ax.yaxis.set_minor_locator(ticker.AutoMinorLocator(int(t["eixos.marcas_menores"]) + 1))
    if not x_categorico:
        if not _aplicar_escala(ax, t, "x", idioma, t["eixos.x_decimais"]):
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
    n = int(t.get("eixos.y_fator") or 0)
    if ry and n and _escala(t, "y") == "linear":
        ry = f"{ry} (×10{str(n).translate(str.maketrans('0123456789', '⁰¹²³⁴⁵⁶⁷⁸⁹'))})"
    if rx is not None:
        ax.set_xlabel(tm.rico(rx), **kw)
    if ry is not None:
        ax.set_ylabel(tm.rico(ry), **kw)


def _limites_y(ax, t, lo, hi, folga_sup=0.06, zero=False):
    faixa = (hi - lo) if hi > lo else (abs(hi) or 1.0)
    ymin = 0 if zero and lo >= 0 else lo - 0.06 * faixa
    ymax = hi + folga_sup * faixa
    if t["eixos.y_min"] is not None:
        ymin = float(t["eixos.y_min"])
    if t["eixos.y_max"] is not None:
        ymax = float(t["eixos.y_max"])
    if _escala(t, "y") == "linear":
        ax.set_ylim(ymin, ymax)
    elif _escala(t, "y") == "raiz quadrada":
        ax.set_ylim(max(ymin, 0), ymax)
    else:
        ax.set_ylim(ymin if (t["eixos.y_min"] is not None and ymin > 0) else None,
                    ymax * (1.0 if t["eixos.y_max"] is not None else 1.12) if ymax > 0 else None)


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


def _rotulos_diretos(ax, t, pontas, labels, cores, abaixo=False):
    """Nome de cada série ao lado do último ponto, na cor da série, afastando rótulos que se sobrepõem."""
    fs = t["fonte.legenda"]
    if abaixo:      # perfis: abaixo do último ponto de cada série
        for (x, y), lb, cor in zip(pontas, labels, cores):
            ax.annotate(lb, (x, y), xytext=(0, -fs * 0.9), textcoords="offset points", ha="center", va="top",
                        fontsize=fs, color=cor, annotation_clip=False, gid="legenda")
        return
    fig = ax.figure
    tr = ax.transData
    ys = np.array([tr.transform((x, y))[1] for x, y in pontas], float)
    passo = fs * 1.25 * fig.dpi / 72
    ordem = np.argsort(ys)
    alvo = ys.copy()
    for _ in range(60):
        mudou = False
        for a, b in zip(ordem[:-1], ordem[1:]):
            d = alvo[b] - alvo[a]
            if d < passo:
                alvo[a] -= (passo - d) / 2
                alvo[b] += (passo - d) / 2
                mudou = True
        if not mudou:
            break
    for (x, y), ya, y0, lb, cor in zip(pontas, alvo, ys, labels, cores):
        dy = (ya - y0) * 72 / fig.dpi
        # na borda direita da área do gráfico, alinhado à altura do último ponto: fica livre de dados e letras
        ax.annotate(lb, (1.0, y), xycoords=ax.get_yaxis_transform(), xytext=(fs * 0.55, dy), textcoords="offset points",
                    ha="left", va="center", fontsize=fs, color=cor, annotation_clip=False, gid="legenda")


def _legenda(ax, t, handles, labels, titulo=None, padrao="automática", n_itens=None, pontas=None, abaixo=False):
    if not t["legenda.mostrar"] or not handles:
        return None
    if t.get("legenda.direta") and pontas is not None and len(pontas) == len(handles):
        _rotulos_diretos(ax, t, pontas, labels, [h.get_color() if hasattr(h, "get_color") else t["fonte.cor"]
                                                 for h in handles], abaixo)
        return None
    pos = t["legenda.posicao"]
    if pos == "automática":
        pos = padrao
    ncol = t["legenda.colunas"] or None
    dx, dy = t["legenda.dx"], t["legenda.dy"]
    kw = dict(title=tm.rico(titulo) if (t["legenda.titulo"] and titulo) else None, frameon=t["legenda.moldura"],
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
        ax.text(y, x, " " + s, ha="left", va="center", gid="letras", **kw)
    else:
        ax.text(x, y, s, ha="center", va="bottom", gid="letras", **kw)


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
    if t["medias.ordenar"] != "original":
        m_ = {str(n): float(v) for n, v in zip(sp.niveis, np.asarray(sp.medias, float))}
        ordem = sorted(ordem, key=lambda o: m_.get(str(o), 0.0), reverse=t["medias.ordenar"] == "decrescente")
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
    if tipo in ("meia-caixa", "meio-violino"):
        dx_obs = -0.17
        dx_med = 0.14 if tipo == "meia-caixa" else 0.10
    if tipo == "linhas":
        tipo_lin, tipo = True, "pontos"
        if mostrar_obs and t["medias.obs_lado"]:
            dx_obs, dx_med = -0.12, 0.14
    else:
        tipo_lin = False

    def sc(x, y, **kw):
        return ax.scatter(y, x, **kw) if H else ax.scatter(x, y, **kw)

    # preenchimentos
    for j in range(k):
        cor = cores[j]
        hach = tm.HACHURAS[j % len(tm.HACHURAS)] if t["medias.hachuras"] else ""
        if tipo == "barras":
            fc = (t["medias.barra_cor"] if (not t["series.colorir_niveis"] and not t["grupos.cores"].get(ordem[j]))
                  else cor)
            auto = t["medias.contorno_auto"]
            kw = dict(color=to_rgba(fc, t["medias.barra_alfa"]),
                      edgecolor=_escurecer(fc) if auto else t["medias.contorno_cor"],
                      linewidth=t["medias.contorno_esp"] or (0.6 if auto else 0), hatch=hach, zorder=1)
            if H:
                ax.barh(pos[j], med[j], height=larg, **kw)
            else:
                ax.bar(pos[j], med[j], width=larg, **kw)
        elif tipo == "pirulito":
            b0 = float(t["eixos.y_min"]) if t["eixos.y_min"] is not None else 0.0
            lw_h = max(1.1, t["series.linha_esp"] * 1.4)
            if H:
                ax.hlines(pos[j], b0, med[j], color=to_rgba(cor, 0.55), lw=lw_h, zorder=1)
            else:
                ax.vlines(pos[j], b0, med[j], color=to_rgba(cor, 0.55), lw=lw_h, zorder=1)
        elif tipo in ("box", "raincloud", "meia-caixa") and len(vals[j]) >= 2:
            w = {"box": larg, "raincloud": larg * 0.22, "meia-caixa": larg * 0.34}[tipo]
            p = pos[j] + (dx_med if tipo == "meia-caixa" else 0.0)
            bp = ax.boxplot([vals[j]], positions=[p], widths=w, patch_artist=True, showfliers=tipo == "box",
                            **({"orientation": "horizontal"} if H else {}), manage_ticks=False,
                            medianprops=dict(color=t["fonte.cor"] if tipo != "raincloud" else cor, lw=1.0),
                            whiskerprops=dict(color=cor, lw=t["erro.esp"]), capprops=dict(color=cor, lw=t["erro.esp"]),
                            boxprops=dict(lw=t["medias.contorno_esp"] or 0.6, edgecolor=cor),
                            flierprops=dict(marker="o", ms=2.5, mfc=cor, mec="none", alpha=0.6))
            for b in bp["boxes"]:
                b.set_facecolor(to_rgba(cor, 0.25 * t["medias.barra_alfa"]) if tipo != "raincloud" else "white")
                b.set_hatch(hach)
        if tipo in ("violino", "raincloud", "meio-violino") and len(vals[j]) >= 3:
            meio = tipo in ("raincloud", "meio-violino")
            _violino(ax, pos[j] + (0.05 if tipo == "raincloud" else 0.02 if tipo == "meio-violino" else 0), vals[j],
                     larg * (0.9 if meio else 1), cor, 0.30 * t["medias.barra_alfa"], t["medias.contorno_esp"] or 0.5,
                     meio, H)
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
            elif tipo in ("raincloud", "meia-caixa", "meio-violino"):
                off = _jitter(len(v), min(t["medias.obs_disp"], 0.08), j)
            else:
                off = _jitter(len(v), t["medias.obs_disp"], j)
            sc(pos[j] + dx_obs + off, v, s=t["medias.obs_tam"], color=cor, alpha=t["medias.obs_alfa"], lw=0, zorder=2)
    # médias e erros
    for j in range(k):
        cor = cores[j]
        mostra_ponto = tipo in ("pontos", "violino", "beeswarm", "raincloud", "meio-violino", "pirulito")
        if tipo == "raincloud":
            ax.plot(*((med[j], pos[j]) if H else (pos[j], med[j])), marker="o", ms=ms * 0.8, color=cor,
                    mec="white", mew=0.5, zorder=5)
            continue
        ye = _yerr(t, err[j:j + 1])
        kw = dict(fmt="o" if mostra_ponto else "none", color=_cor_erro(t, cor), ecolor=_cor_erro(t, cor),
                  ms=ms * (1.35 if tipo == "pirulito" else 1), elinewidth=t["erro.esp"], capthick=t["erro.esp"],
                  capsize=t["erro.chapeu"], zorder=4,
                  mfc=("white" if t["series.vazados"] else cor), mec=(cor if t["series.vazados"] else t["series.marcador_borda_cor"]),
                  mew=(t["series.marcador_borda"] if not t["series.vazados"] else max(t["series.marcador_borda"], 0.8)))
        if tipo in ("box", "meia-caixa"):
            pb = pos[j] + (dx_med if tipo == "meia-caixa" else 0)
            ax.plot(*((med[j], pb) if H else (pb, med[j])), marker="D", ms=ms * 0.7, color="white",
                    mec=cor, mew=0.8, zorder=5)
            continue
        p = pos[j] + dx_med
        if H:
            ax.errorbar(med[j], p, xerr=ye if t["erro.tipo"] != "nenhuma" else None, **kw)
        else:
            ax.errorbar(p, med[j], yerr=ye if t["erro.tipo"] != "nenhuma" else None, **kw)
    if tipo_lin and k > 1:
        cor_l = cores[0] if not t["series.colorir_niveis"] else t["series.cor_unica"]
        xs_l = pos + dx_med
        ax.plot(*((med, xs_l) if H else (xs_l, med)), color=cor_l, lw=t["series.linha_esp"], zorder=3)
    # limites
    topo = med + np.nan_to_num(err)
    base = med - (0 if t["erro.so_superior"] else np.nan_to_num(err))
    if tipo in ("box", "violino", "raincloud", "beeswarm", "meia-caixa", "meio-violino") or mostrar_obs:
        topo = np.maximum(topo, np.where(np.isfinite(topo_obs), topo_obs, topo))
        base = np.minimum(base, np.where(np.isfinite(base_obs), base_obs, base))
    lo, hi = float(np.nanmin(base)), float(np.nanmax(topo))
    zero = tipo in ("barras", "pirulito") and t["eixos.y_min"] is None
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
            xl = pos[j] + (dx_med if tipo in ("pontos", "meia-caixa", "meio-violino", "beeswarm") else 0)
            _texto_letra(t, ax, xl, alvo[j] + d, letras[i], H)
    colchetes = _colchetes(ax, t, ordem, pos, hi + (0.10 * faixa if tem_letras else 0.02 * faixa), faixa, H,
                           extras=_colchetes_auto(sp, t, ordem, idioma))
    if t["stats.subtitulo"] and sp.estat:
        ax._estat = _texto_estat(sp.estat, t, idioma)
        ax.annotate(ax._estat, (0, 1), xycoords="axes fraction", xytext=(0, 3), textcoords="offset points",
                    ha="left", va="bottom", fontsize=t["fonte.legenda"], color=t["fonte.cor"], alpha=0.8,
                    annotation_clip=False, gid="estat")
    if t["medias.rotulo_valor"]:
        _rotulos_valor(ax, t, pos + (dx_med if tipo in ("pontos", "meia-caixa", "meio-violino", "beeswarm") else 0),
                       med, err, tipo, H, idioma)
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
        ax.set_yticks(pos, _quebrar([tm.nome_rico(t, o) for o in ordem], 22))
        ax.tick_params(axis="y", length=0)
    else:
        _limites_y(ax, t, lo, hi, folga, zero=zero)
        ax.set_xlim(-0.6, k - 0.4)
        larg_char = max(6, (_largura_ax_mm(ax) * 1.12 / max(k, 1)) / (0.165 * t["fonte.numeros"]))
        nomes = [tm.nome_rico(t, o) for o in ordem]
        _rotulos_categoricos(ax, pos, nomes, larg_char, t)
    _anotacoes(ax, t, float(np.nanmean(med)) if k else None, "x" if H else "y", idioma)
    estilizar_eixo(ax, t, idioma, x_categorico=not H, y_categorico=H)
    if H:
        ax.xaxis.set_major_formatter(_formatador(t, t["eixos.y_decimais"], idioma))
        _rotulos_eixos(ax, t, sp.rotulo_y, sp.rotulo_x)
    else:
        _rotulos_eixos(ax, t, sp.rotulo_x, sp.rotulo_y)
    if t["series.colorir_niveis"] and legenda and t["legenda.posicao"] != "automática":
        hs = [Patch(facecolor=cores[j], label=tm.nome_rico(t, ordem[j])) for j in range(k)]
        _legenda(ax, t, hs, [h.get_label() for h in hs], sp.rotulo_x)
    return ax


def _escurecer(cor, f=0.38):
    r, g, b, a = to_rgba(cor)
    return (r * (1 - f), g * (1 - f), b * (1 - f), 1.0)


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
    ax._nomes_categoricos = list(nomes)


def _partir(n):
    """Quebra um rótulo em duas linhas no espaço mais próximo do meio."""
    n = str(n)
    esp = [i for i, c in enumerate(n) if c == " " and "$" not in n[:i].replace("\\$", "")[-1:]]
    if not esp:
        return n
    i = min(esp, key=lambda k: abs(k - len(n) / 2))
    return n[:i] + "\n" + n[i + 1:]


def _corrigir_sobreposicao(fig):
    """Depois do layout final: se rótulos categóricos de X se sobrepõem, quebra em duas linhas; se ainda
    assim não couberem, inclina 35° (a menos que o usuário tenha fixado a rotação)."""
    eixos = [a for a in fig.axes if getattr(a, "_nomes_categoricos", None)]
    if not eixos:
        return
    try:
        fig.canvas.draw()
    except Exception:
        return
    r = fig.canvas.get_renderer()

    def sobrepoe(ax):
        bbs = [lb.get_window_extent(r) for lb in ax.get_xticklabels() if lb.get_text()]
        return any(bbs[i].x1 > bbs[i + 1].x0 - 1.5 for i in range(len(bbs) - 1))
    mudou = False
    for ax in eixos:
        if ax.get_xticklabels() and ax.get_xticklabels()[0].get_rotation() != 0:
            continue
        if sobrepoe(ax):
            nomes = ax._nomes_categoricos
            meio = [_partir(n) for n in nomes]
            ax.set_xticks(ax.get_xticks(), meio)
            mudou = True
    if mudou:
        fig.canvas.draw()
        for ax in eixos:
            if ax.get_xticklabels() and ax.get_xticklabels()[0].get_rotation() == 0 and sobrepoe(ax):
                ax.set_xticks(ax.get_xticks(), ax._nomes_categoricos)
                plt.setp(ax.get_xticklabels(), rotation=35, ha="right", rotation_mode="anchor")


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


def _rotulos_valor(ax, t, pos, med, err, tipo, H, idioma):
    """Rótulos de dados (valor da média): dentro da barra, perto do topo; nos demais tipos, ao lado do ponto."""
    dec = int(t["medias.rotulo_decimais"])
    for p, m, e in zip(pos, med, np.nan_to_num(err)):
        if not np.isfinite(m):
            continue
        s = (_num(m, t, idioma, 3) if dec < 0 else f"{m:.{dec}f}".replace(".", _sep(t, idioma))).replace("-", "−")
        kw = dict(fontsize=t["fonte.letras"] * 0.92, color=t["fonte.cor"], zorder=6, clip_on=True)
        if tipo == "barras":
            desc = 0 if t["erro.so_superior"] else e
            if H:
                ax.annotate(s, (m - desc, p), xytext=(-2, 0), textcoords="offset points", ha="right", va="center", **kw)
            else:
                ax.annotate(s, (p, m - desc), xytext=(0, -2), textcoords="offset points", ha="center", va="top", **kw)
        elif H:
            ax.text(m, p - 0.18, s, ha="center", va="bottom", **kw)
        else:
            ax.text(p + 0.09, m, s, ha="left", va="center", **kw)


def _texto_estat(e, t, idioma):
    """Linha no estilo ggbetweenstats: F(gl1; gl2) = …; p = …; η²p = …; n = …"""
    pt = idioma == "pt"
    def n(v, d):
        return f"{v:.{d}f}".replace(".", _sep(t, idioma))
    partes = []
    if e.get("f") is not None and np.isfinite(e["f"]):
        gl2 = e.get("gl2")
        gl2s = f"{gl2:.0f}" if gl2 is not None and abs(gl2 - round(gl2)) < 1e-6 else n(gl2 or 0, 1)
        partes.append(f"F({e.get('gl1', 0):.0f}{';' if pt else ','} {gl2s}) = {n(e['f'], 2)}")
    if e.get("p") is not None:
        partes.append("p < 0,001".replace(",", _sep(t, idioma)) if e["p"] < 0.001 else f"p = {n(e['p'], 3)}")
    if e.get("eta2p") is not None and np.isfinite(e["eta2p"]):
        partes.append(f"η²p = {n(e['eta2p'], 2)}")
    if e.get("n"):
        partes.append(f"n = {int(e['n'])}")
    if e.get("metodo"):
        partes.append(str(e["metodo"]))
    return ("; " if pt else ", ").join(partes)


def _colchetes_auto(sp, t, ordem, idioma):
    """Colchetes gerados do teste de médias (significativos ou todos), do par mais próximo ao mais distante."""
    modo = t["stats.colchetes"]
    if modo == "nenhum" or not sp.pares:
        return []
    out = []
    for q in sp.pares:
        a, b = str(q.get("g1")), str(q.get("g2"))
        if a not in ordem or b not in ordem or (modo == "significativos" and not q.get("sig")):
            continue
        p = q.get("p")
        if t["stats.colchete_texto"] == "valor de p" and p is not None and np.isfinite(p):
            txt = ("p < 0,001" if p < 0.001 else f"p = {p:.3f}").replace(",", _sep(t, idioma)).replace(".", _sep(t, idioma))
        elif p is not None and np.isfinite(p):
            txt = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
        else:
            txt = "*" if q.get("sig") else "ns"
        out.append({"de": a, "ate": b, "texto": txt, "_d": abs(ordem.index(a) - ordem.index(b))})
    out.sort(key=lambda c: c["_d"])
    return out[:10]


def _colchetes(ax, t, ordem, pos, y0, faixa, H=False, extras=None):
    itens = [c for c in (t["anot.colchetes"] or []) if str(c.get("de")) in ordem and str(c.get("ate")) in ordem]
    itens = itens + list(extras or [])
    linhas_ocup = []          # intervalos já usados em cada linha (colchetes que não se cruzam dividem a linha)
    for c in itens:
        a, b = sorted((pos[ordem.index(str(c["de"]))], pos[ordem.index(str(c["ate"]))]))
        n = 0
        while n < len(linhas_ocup) and any(not (b < a2 - 0.01 or a > b2 + 0.01) for a2, b2 in linhas_ocup[n]):
            n += 1
        if n == len(linhas_ocup):
            linhas_ocup.append([])
        linhas_ocup[n].append((a, b))
        a, b = a + 0.07, b - 0.07
        y = y0 + n * 0.095 * faixa
        h = 0.02 * faixa
        kw = dict(color=t["eixos.cor"], lw=t["eixos.espessura"], clip_on=False)
        fs = t["fonte.letras"] * (0.9 if len(str(c.get("texto") or "")) > 3 else 1)
        if H:
            ax.plot([y, y + h, y + h, y], [a, a, b, b], **kw)
            ax.text(y + h * 1.6, (a + b) / 2, tm.rico(c.get("texto") or "*"), va="center", ha="left", fontsize=fs)
        else:
            ax.plot([a, a, b, b], [y, y + h, y + h, y], **kw)
            ax.text((a + b) / 2, y + h * 1.1, tm.rico(c.get("texto") or "*"), ha="center", va="bottom", fontsize=fs,
                    linespacing=0.8)
    return len(linhas_ocup)



def _anotacoes(ax, t, media=None, eixo_media="y", idioma="pt"):
    """Linhas de referência, faixas sombreadas, setas/formas e textos livres (coordenadas como no OriginPro:
    linhas e faixas em unidades dos dados; formas e textos em fração do eixo, 0–1)."""
    for f in t.get("anot.faixas") or []:
        try:
            a, b = float(f.get("de")), float(f.get("ate"))
        except (TypeError, ValueError):
            continue
        cor = f.get("cor") or "#D9C9B6"
        alfa = float(f.get("alfa") if f.get("alfa") not in (None, "") else 0.25)
        if f.get("eixo", "y") == "y":
            ax.axhspan(min(a, b), max(a, b), color=cor, alpha=alfa, lw=0, zorder=0)
            if f.get("texto"):
                ax.text(0.01, max(a, b), tm.rico(str(f["texto"])), transform=ax.get_yaxis_transform(), va="top",
                        ha="left", fontsize=t["fonte.legenda"], color=t["fonte.cor"], alpha=0.85, clip_on=True)
        else:
            ax.axvspan(min(a, b), max(a, b), color=cor, alpha=alfa, lw=0, zorder=0)
            if f.get("texto"):
                ax.text((a + b) / 2, 0.99, tm.rico(str(f["texto"])), transform=ax.get_xaxis_transform(), va="top",
                        ha="center", fontsize=t["fonte.legenda"], color=t["fonte.cor"], alpha=0.85, clip_on=True)
    linhas = list(t["anot.linhas"] or [])
    if t.get("eixos.linha_media") and media is not None and np.isfinite(media):
        linhas.append({"eixo": eixo_media, "valor": media, "estilo": "tracejada", "cor": "#7A7A7A",
                       "texto": "média" if idioma == "pt" else "mean"})
    for l in linhas:
        try:
            v = float(l.get("valor"))
        except (TypeError, ValueError):
            continue
        ls = tm.ESTILOS_LINHA.get(l.get("estilo", "tracejada"), "--")
        kw = dict(color=l.get("cor") or "#7A7A7A", lw=float(l.get("esp") or 0.6), ls=ls, zorder=1)
        if l.get("eixo", "y") == "y":
            ax.axhline(v, **kw)
            if l.get("texto"):
                ax.text(1.0, v, " " + tm.rico(str(l["texto"])), transform=ax.get_yaxis_transform(), va="center",
                        ha="left", fontsize=t["fonte.legenda"], color=kw["color"], clip_on=False)
        else:
            ax.axvline(v, **kw)
            if l.get("texto"):
                ax.text(v, 1.0, tm.rico(str(l["texto"])), transform=ax.get_xaxis_transform(), va="bottom",
                        ha="center", fontsize=t["fonte.legenda"], color=kw["color"], clip_on=False)
    for fm in t.get("anot.formas") or []:
        try:
            x0, y0 = float(fm.get("x0")), float(fm.get("y0"))
            x1, y1 = float(fm.get("x1")), float(fm.get("y1"))
        except (TypeError, ValueError):
            continue
        cor = fm.get("cor") or t["eixos.cor"]
        lw = float(fm.get("esp") or t["eixos.espessura"])
        tipo = fm.get("tipo") or "seta"
        if tipo in ("seta", "linha"):
            ax.annotate(tm.rico(str(fm.get("texto") or "")), xy=(x1, y1), xytext=(x0, y0), xycoords="axes fraction",
                        textcoords="axes fraction", fontsize=t["fonte.legenda"], color=t["fonte.cor"],
                        ha="center", va="center", zorder=6,
                        arrowprops=dict(arrowstyle="-|>,head_length=0.4,head_width=0.2" if tipo == "seta" else "-",
                                        color=cor, lw=lw, shrinkA=2, shrinkB=0))
        elif tipo in ("retângulo", "elipse"):
            from matplotlib.patches import Ellipse as _El, Rectangle as _Re
            if tipo == "retângulo":
                patch = _Re((min(x0, x1), min(y0, y1)), abs(x1 - x0), abs(y1 - y0))
            else:
                patch = _El(((x0 + x1) / 2, (y0 + y1) / 2), abs(x1 - x0), abs(y1 - y0))
            patch.set(transform=ax.transAxes, facecolor="none", edgecolor=cor, lw=lw, zorder=6, clip_on=False,
                      ls=tm.ESTILOS_LINHA.get(fm.get("estilo") or "contínua", "-"))
            ax.add_patch(patch)
            if fm.get("texto"):
                ax.text((x0 + x1) / 2, max(y0, y1) + 0.01, tm.rico(str(fm["texto"])), transform=ax.transAxes,
                        ha="center", va="bottom", fontsize=t["fonte.legenda"], color=t["fonte.cor"])
    for tx in t["anot.textos"] or []:
        try:
            ax.text(float(tx.get("x", 0.5)), float(tx.get("y", 0.95)), tm.rico(str(tx.get("texto", ""))),
                    transform=ax.transAxes, fontsize=float(tx.get("tam") or t["fonte.tamanho"]),
                    ha=tx.get("alinhar", "left"), va="top", color=tx.get("cor") or t["fonte.cor"],
                    fontstyle="italic" if tx.get("italico") else "normal")
        except (TypeError, ValueError):
            continue


# ============================================================================
# 2. Interação (x = níveis de A; grupos = níveis de B)
# ============================================================================
def desenhar_grupos(ax, sp: SpecGrupos, t, idioma="pt", legenda=True):
    A = _ordem(sp.A, t)
    B = [b for b in _ordem(sp.B, t)]
    ka, kb = len(A), len(B)
    tipo = t["medias.tipo"] if t["medias.tipo"] in ("pontos", "barras", "box", "linhas") else "pontos"
    conectar = t["medias.conectar"] or tipo == "linhas"
    if tipo == "linhas":
        tipo = "pontos"
    larg = min(t["medias.espaco_grupos"] / max(kb, 1), 0.32)
    ms = t["series.marcador_tam"]
    topo_g, base_g = -np.inf, np.inf
    handles, labels, pontas = [], [], []
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
            auto = t["medias.contorno_auto"]
            ax.bar(x, m, width=larg * 0.92, color=to_rgba(cor, 0.3 * t["medias.barra_alfa"] if not t["medias.hachuras"] else 0.15),
                   edgecolor=_escurecer(cor) if auto else (t["medias.contorno_cor"] if t["medias.contorno_esp"] else "none"),
                   linewidth=t["medias.contorno_esp"] or (0.6 if auto else 0), hatch=hach, zorder=1)
            if t["medias.rotulo_valor"]:
                _rotulos_valor(ax, t, x, m, e, "barras", False, idioma)
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
                        ls=tm.linha_grupo(t, b, j) if conectar else "none",
                        lw=t["series.linha_esp"])
        handles.append(Line2D([], [], color=cor, marker=mk, ms=ms * 0.9, lw=t["series.linha_esp"] if conectar else 0,
                              ls=tm.linha_grupo(t, b, j) if conectar else "none", mfc="white" if t["series.vazados"] else cor,
                              mec=cor if t["series.vazados"] else t["series.marcador_borda_cor"]) if tipo != "barras"
                       else Patch(facecolor=to_rgba(cor, 0.35), edgecolor=cor, hatch=hach, lw=0.5))
        labels.append(tm.nome_rico(t, b))
        pontas.append((x[-1], m[-1]))
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
            ax.text(xx, yy + t["letras.distancia"] * faixa, L, ha="center", va="bottom", fontsize=t["fonte.letras"], gid="letras",
                    clip_on=True, fontstyle="italic" if t["letras.italico"] else "normal",
                    rotation=90 if (len(L) > 3 and kb * ka > 16) else 0)
    _limites_y(ax, t, lo, topo_g, 0.16 if tem else 0.06, zero=tipo == "barras")
    larg_char = max(6, (_largura_ax_mm(ax) * 1.12 / max(ka, 1)) / (0.165 * t["fonte.numeros"]))
    _rotulos_categoricos(ax, np.arange(ka), [tm.nome_rico(t, a) for a in A], larg_char, t)
    ax.set_xlim(-0.6, ka - 0.4)
    _anotacoes(ax, t, float(np.nanmean(sp.medias.to_numpy(float))), "y", idioma)
    estilizar_eixo(ax, t, idioma, x_categorico=True)
    _rotulos_eixos(ax, t, sp.nome_A, sp.rotulo_y)
    if legenda:
        _legenda(ax, t, handles, labels, sp.nome_B, padrao="fora — acima",
                 pontas=pontas if (conectar and tipo == "pontos") else None)
    return ax


# ============================================================================
# 3. Regressão
# ============================================================================
def _banda(mod, xx, nivel=0.95, predicao=False, qm_erro=None):
    """Meia-largura da faixa de confiança (curva média) ou de predição (nova observação), método delta."""
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
    if predicao:
        if qm_erro is None or not np.isfinite(qm_erro):
            return None
        var = var + qm_erro
    gl = mod.gl_erro if mod.gl_erro and np.isfinite(mod.gl_erro) else 30
    return stats.t.ppf(1 - (1 - nivel) / 2, gl) * np.sqrt(np.clip(var, 0, None))


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
    textos, handles, pontas_r = [], [], []
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
                nivel = float(str(t["reg.banda_nivel"]).rstrip("%")) / 100
                if t["reg.banda_tipo"] in ("predição", "ambas"):
                    bp = _banda(mod, xx, nivel, True, c.qm_erro)
                    if bp is not None:
                        ax.fill_between(xx, yy - bp, yy + bp, color=cor, alpha=t["reg.banda_alfa"] * 0.55, lw=0, zorder=1)
                        ys_all += [yy - bp, yy + bp]
                if t["reg.banda_tipo"] in ("confiança", "ambas"):
                    b = _banda(mod, xx, nivel)
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
        if c.sig and mod is not None:
            pontas_r.append((float(xx[-1]), float(mod.prever(xx[-1:])[0])))
        else:
            pontas_r.append((float(c.x.max()), float(np.sum(c.medias * c.n) / np.sum(c.n))))
    ys = np.concatenate([np.ravel(y) for y in ys_all]) if ys_all else np.array([0, 1])
    lo, hi = float(np.nanmin(ys)), float(np.nanmax(ys))
    faixa = (hi - lo) or 1
    ax.set_xticks(np.unique(xs)) if not t["eixos.x_passo"] else None
    xmin = t["eixos.x_min"] if t["eixos.x_min"] is not None else xs.min() - 0.06 * xr
    xmax = t["eixos.x_max"] if t["eixos.x_max"] is not None else xs.max() + 0.06 * xr
    esc_x = _escala(t, "x")
    if esc_x == "raiz quadrada":
        xmin = max(xmin, 0.0)
    elif esc_x != "linear":
        pos_x = xs[xs > 0]
        xmin = xmin if xmin > 0 else (pos_x.min() / 1.6 if len(pos_x) else 0.1)
        xmax = xmax * 1.25 if t["eixos.x_max"] is None else xmax
        ax.set_xticks([v for v in np.unique(xs) if v > 0]) if not t["eixos.x_passo"] else None
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
                        fontsize=t["fonte.equacao"], linespacing=1.35, gid="equacao")
            else:
                xa = 0.03 if "esquerda" in pos else 0.97
                ya, va = (0.98, "top") if pos.startswith("sup") else (0.03, "bottom")
                ax.text(xa, ya, "\n".join(linhas), transform=ax.transAxes, va=va, ha="left" if xa < 0.5 else "right",
                        fontsize=t["fonte.equacao"], linespacing=1.35, gid="equacao")
        elif legenda:
            chars = int(_largura_ax_mm(ax) / (0.19 * t["fonte.equacao"]))
            labs = []
            for r, tx, *_ in textos:
                s = f"{tm.nome_rico(t, r)}: " + "; ".join(tx)
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
        _legenda(ax, t, handles, [tm.nome_rico(t, r) for r, *_ in textos], sp.titulo_legenda, "dentro — inf. direita",
                 pontas=pontas_r)
    _anotacoes(ax, t, float(np.nanmean(np.concatenate([c.medias for c in curvas]))), "y", idioma)
    estilizar_eixo(ax, t, idioma)
    if _escala(t, "x") not in ("linear", "ln") and not t["eixos.x_passo"]:
        ax.set_xticks([v for v in np.unique(xs) if v > 0 or _escala(t, "x") == "raiz quadrada"])
        ax.set_xlim(xmin, xmax)
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
    handles, labels, pontas_p = [], [], []
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
        labels.append(tm.nome_rico(t, s.get("rotulo")))
        pontas_p.append((float(m[-1]), float(pos[-1] + off)))
    ax.set_yticks(pos, [tm.nome_rico(t, c) for c in camadas])
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
    _anotacoes(ax, t, float(np.nanmean(np.concatenate([np.asarray(s_["medias"], float) for s_ in series]))), "x", idioma)
    if multi and legenda:
        _legenda(ax, t, handles, labels, sp.titulo_legenda, "fora — abaixo", pontas=pontas_p, abaixo=True)
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
    nomes = [tm.nome_rico(t, n) for n in sp.nomes]
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
                   marker=mk, label=tm.nome_rico(t, g), zorder=3)
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
            ax.text(x, y, tm.nome_rico(t, nm), fontsize=t["fonte.legenda"], color=t["pca.setas_cor"],
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
    D = h.dendrogram(sp.ligacao, labels=[tm.nome_rico(t, r) for r in sp.rotulos], no_plot=True,
                     orientation="right")
    grupos_obs = sp.clusters
    folhas = D["ivl"]
    # cor de cada folha pelo grupo (critério de Mojena)
    cor_folha = {}
    if grupos_obs is not None:
        nomes = [tm.nome_rico(t, r) for r in sp.rotulos]
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


def desenhar_empilhado(ax, sp: SpecEmpilhado, t, idioma="pt", legenda=True):
    """Barras empilhadas (valores ou 100%), com rótulo de cada segmento e do total."""
    H = bool(t["medias.horizontal"])
    cats = _ordem(sp.categorias, t)
    comps = [c for c in sp.componentes if str(c) not in set(map(str, t["niveis.ocultar"]))]
    ordem_c = [o for o in map(str, t["niveis.ordem"]) if o in map(str, comps)]
    comps = [c for o in ordem_c for c in comps if str(c) == o] + [c for c in comps if str(c) not in ordem_c]
    V = sp.valores.copy()
    V.index = V.index.astype(str)
    V = V.loc[cats, comps].astype(float).clip(lower=0)
    pct = t["emp.modo"].startswith("percentual")
    tot = V.sum(axis=1).to_numpy(float)
    M = (V.div(V.sum(axis=1).replace(0, np.nan), axis=0) * 100) if pct else V
    pos = np.arange(len(cats), dtype=float)
    larg = t["medias.largura"]
    base = np.zeros(len(cats))
    handles = []
    lim = float(np.nanmax(M.sum(axis=1))) or 1.0
    auto = t["medias.contorno_auto"]
    for j, c in enumerate(comps):
        cor = tm.cor_grupo(t, c, j)
        v = np.nan_to_num(M[c].to_numpy(float))
        hach = tm.HACHURAS[j % len(tm.HACHURAS)] if t["medias.hachuras"] else ""
        kw = dict(color=to_rgba(cor, t["medias.barra_alfa"]), hatch=hach, zorder=2,
                  edgecolor=_escurecer(cor) if auto else (t["medias.contorno_cor"] if t["medias.contorno_esp"] else t["tela.fundo"]),
                  linewidth=t["medias.contorno_esp"] or 0.5)
        if H:
            ax.barh(pos, v, left=base, height=larg, **kw)
        else:
            ax.bar(pos, v, bottom=base, width=larg, **kw)
        if t["emp.rotulos"]:
            r, g, b_, _ = to_rgba(cor)
            claro = (0.299 * r + 0.587 * g + 0.114 * b_) > 0.6
            for i in range(len(cats)):
                if v[i] < 0.055 * lim:
                    continue
                txt = (f"{v[i]:.0f}" if pct else _num(v[i], t, idioma, 3)).replace(".", _sep(t, idioma))
                xy = (base[i] + v[i] / 2, pos[i]) if H else (pos[i], base[i] + v[i] / 2)
                ax.text(*xy, txt, ha="center", va="center", fontsize=t["fonte.letras"] * 0.9,
                        color="#1A1A1A" if claro else "white", zorder=4, clip_on=True)
        base = base + v
        handles.append(Patch(facecolor=to_rgba(cor, t["medias.barra_alfa"]), edgecolor="none", hatch=hach,
                             label=tm.nome_rico(t, c)))
    topo = base.copy()
    if not pct and sp.ep_total is not None and t["erro.tipo"] != "nenhuma":
        ep = pd.Series(np.asarray(sp.ep_total, float), index=[str(c) for c in sp.categorias]).loc[cats].to_numpy()
        kw = dict(fmt="none", ecolor=t["eixos.cor"], elinewidth=t["erro.esp"], capsize=t["erro.chapeu"],
                  capthick=t["erro.esp"], zorder=5)
        if H:
            ax.errorbar(base, pos, xerr=[np.zeros_like(ep), ep], **kw)
        else:
            ax.errorbar(pos, base, yerr=[np.zeros_like(ep), ep], **kw)
        topo = base + np.nan_to_num(ep)
    if t["emp.total"] and not pct:
        for i in range(len(cats)):
            txt = _num(tot[i], t, idioma, 3).replace(".", _sep(t, idioma))
            if H:
                ax.annotate(txt, (topo[i], pos[i]), xytext=(3, 0), textcoords="offset points", ha="left", va="center",
                            fontsize=t["fonte.letras"], gid="letras")
            else:
                ax.annotate(txt, (pos[i], topo[i]), xytext=(0, 2), textcoords="offset points", ha="center",
                            va="bottom", fontsize=t["fonte.letras"], gid="letras")
    hi = 100.0 if pct else float(np.nanmax(topo))
    nomes = [tm.nome_rico(t, c) for c in cats]
    ry = sp.rotulo_y if not pct else ("Proporção (%)" if idioma == "pt" else "Proportion (%)")
    if H:
        ax.set_xlim(0, hi * (1.0 if pct else 1.10))
        ax.set_ylim(len(cats) - 0.5, -0.5)
        ax.set_yticks(pos, _quebrar(nomes, 22))
        ax.tick_params(axis="y", length=0)
        estilizar_eixo(ax, t, idioma, y_categorico=True)
        ax.xaxis.set_major_formatter(_formatador(t, t["eixos.y_decimais"], idioma))
        _rotulos_eixos(ax, t, ry, sp.rotulo_x)
    else:
        if pct:
            ax.set_ylim(0, 100)
        else:
            _limites_y(ax, t, 0.0, hi, 0.10 if t["emp.total"] else 0.05, zero=True)
        ax.set_xlim(-0.6, len(cats) - 0.4)
        larg_char = max(6, (_largura_ax_mm(ax) * 1.12 / max(len(cats), 1)) / (0.165 * t["fonte.numeros"]))
        _rotulos_categoricos(ax, pos, nomes, larg_char, t)
        _anotacoes(ax, t, None, "y", idioma)
        estilizar_eixo(ax, t, idioma, x_categorico=True)
        _rotulos_eixos(ax, t, sp.rotulo_x, ry)
    if legenda:
        hs = handles[::-1] if not H else handles
        _legenda(ax, t, hs, [h.get_label() for h in hs], sp.titulo_legenda, padrao="fora — direita")
    return ax


DESENHAR = {"empilhado": desenhar_empilhado, "dendrograma": desenhar_dendrograma, "medias": desenhar_medias, "grupos": desenhar_grupos, "regressao": desenhar_regressao,
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
    if sp.tipo == "empilhado" and t["medias.horizontal"]:
        return max(50, 7.5 * len(sp.categorias) + 24)
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
                ax.set_title(tm.rico(t["tela.titulo"]), loc="left", fontsize=t["fonte.tamanho"],
                             fontweight=t["fonte.peso_titulos"],
                             pad=(t["fonte.legenda"] * 1.5 + 6) if getattr(ax, "_estat", None) else None)
            if not t["eixos.x_rotacao"]:
                _corrigir_sobreposicao(fig)
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


COM_Y_NUMERICO = ("medias", "grupos", "regressao")


def _y_comum(itens, idioma):
    """Faixa de Y que contém todos os painéis (desenho prévio de cada um, como o Merge Graphs do Origin)."""
    lo, hi = np.inf, -np.inf
    for sp, t in itens:
        if sp is None or sp.tipo not in COM_Y_NUMERICO or (sp.tipo == "medias" and t["medias.horizontal"]):
            continue
        with plt.rc_context(rc(t)):
            f, a = plt.subplots(figsize=(t["tela.largura_mm"] * MM, _altura_padrao(sp, t) * MM))
            DESENHAR[sp.tipo](a, sp, t, idioma, legenda=False)
            y0, y1 = a.get_ylim()
            plt.close(f)
        lo, hi = min(lo, y0), max(hi, y1)
    return (lo, hi) if np.isfinite(lo) and np.isfinite(hi) else None


def painel(itens, linhas, colunas, t_painel, idioma="pt", largura_mm=None, altura_mm=None, ordem_rotulos=True):
    """itens: lista de (spec, tema). Monta grade linhas × colunas (itens a mais são ignorados)."""
    itens = list(itens[: linhas * colunas])
    comum = _y_comum(itens, idioma) if t_painel.get("painel.mesma_escala_y") else None
    if comum:
        itens = [(sp, {**t, "eixos.y_min": comum[0], "eixos.y_max": comum[1]}) if sp is not None
                 and sp.tipo in COM_Y_NUMERICO else (sp, t) for sp, t in itens]
    W = largura_mm or t_painel["tela.largura_mm"]
    H = altura_mm or (W / colunas * 0.85 * linhas)
    with plt.rc_context(rc(t_painel)):
        fig = plt.figure(figsize=(W * MM, H * MM), layout="constrained")
        gs = fig.add_gridspec(linhas, colunas, wspace=t_painel["painel.wspace"] * 0.1,
                              hspace=t_painel["painel.hspace"] * 0.1)
        fig.get_layout_engine().set(wspace=t_painel["painel.wspace"] * 0.1, hspace=t_painel["painel.hspace"] * 0.1)
    for k, (sp, t) in enumerate(itens):
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
            if comum and t_painel.get("painel.ocultar_internos") and c_ > 0 and sp.tipo in COM_Y_NUMERICO:
                ax.set_ylabel("")
                ax.tick_params(axis="y", labelleft=False)
            rot = tm.rotulo_painel(t_painel["painel.estilo"], k)
            if rot:
                ax.text(t_painel["painel.dx"] - 0.12, t_painel["painel.dy"], rot, transform=ax.transAxes,
                        fontsize=t_painel["painel.tamanho"], fontweight=t_painel["painel.peso"], ha="left", va="bottom",
                        family=familia(t_painel))
    with plt.rc_context(rc(t_painel)):
        _corrigir_sobreposicao(fig)
    return fig


# ============================================================================
# Exportação
# ============================================================================
def exportar(fig, t, formatos=("png", "svg", "pdf", "tiff")) -> dict:
    """PNG/TIFF na resolução do tema (TIFF com LZW, RGB ou CMYK); SVG/EPS com texto editável ou em
    contornos; PDF com fontes TrueType embutidas."""
    out = {}
    transp = bool(t["tela.transparente"])
    contornos = t.get("tela.svg_texto") == "contornos"
    for fmt in formatos:
        buf = io.BytesIO()
        kw = dict(format=fmt, transparent=transp and fmt != "eps", facecolor="none" if (transp and fmt != "eps")
                  else t["tela.fundo"])
        if fmt in ("png", "tiff"):
            kw["dpi"] = int(t["tela.dpi"])
        cmyk = fmt == "tiff" and t.get("tela.tiff_cor") == "CMYK"
        if fmt == "tiff" and not cmyk:
            kw["pil_kwargs"] = {"compression": "tiff_lzw"}
        if cmyk:
            kw["format"] = "png"
            kw["transparent"] = False
            kw["facecolor"] = t["tela.fundo"]
        with plt.rc_context({"svg.fonttype": "path" if contornos else "none", "pdf.fonttype": 42,
                             "ps.fonttype": 42, "ps.useafm": False}):
            fig.savefig(buf, **kw)
        dados = buf.getvalue()
        if cmyk:
            from PIL import Image
            im = Image.open(io.BytesIO(dados)).convert("RGB").convert("CMYK")
            b2 = io.BytesIO()
            dpi = int(t["tela.dpi"])
            im.save(b2, format="TIFF", compression="tiff_lzw", dpi=(dpi, dpi))
            dados = b2.getvalue()
        out[fmt] = dados
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


ROTULOS_REGIAO = {"dados": "Área do gráfico", "eixo_y": "Eixo Y", "eixo_x": "Eixo X", "titulo_y": "Título do eixo Y",
                  "titulo_x": "Título do eixo X", "legenda": "Legenda", "letras": "Letras e valores",
                  "equacao": "Equação", "estat": "Resumo estatístico", "titulo": "Título", "tela": "Tamanho e fundo"}


def _regioes(fig):
    """Caixas clicáveis da figura (frações da imagem; origem no canto superior esquerdo)."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    W, Hh = fig.bbox.width, fig.bbox.height
    out = []

    def add(rid, bb, folga=2.0):
        if bb is None or bb.width <= 0 or bb.height <= 0:
            return
        x0, y0 = max(bb.x0 - folga, 0), max(bb.y0 - folga, 0)
        x1, y1 = min(bb.x1 + folga, W), min(bb.y1 + folga, Hh)
        if x1 - x0 < 3 or y1 - y0 < 3:
            return
        out.append(dict(id=rid, rot=ROTULOS_REGIAO.get(rid, rid), x=x0 / W, y=1 - y1 / Hh, w=(x1 - x0) / W,
                        h=(y1 - y0) / Hh))

    from matplotlib.transforms import Bbox
    eixos = [a for a in fig.axes if a.get_visible()]
    for ax in eixos[:1] if len(eixos) > 2 else eixos:
        add("dados", ax.get_window_extent(r), 0)
        for nome, axis in (("x", ax.xaxis), ("y", ax.yaxis)):
            try:
                rot = axis.label
                bbl = rot.get_window_extent(r) if rot.get_text().strip() else None
                marcas = [tk.label1.get_window_extent(r) for tk in axis.get_major_ticks()
                          if tk.label1.get_visible() and tk.label1.get_text()] + \
                         [tk.label2.get_window_extent(r) for tk in axis.get_major_ticks()
                          if tk.label2.get_visible() and tk.label2.get_text()]
                marcas = [b for b in marcas if b.width > 0 and b.x1 > 0 and b.y1 > 0 and b.x0 < W and b.y0 < Hh]
                if marcas:
                    add(f"eixo_{nome}", Bbox.union(marcas), 3)
                add(f"titulo_{nome}", bbl, 3)
            except Exception:
                pass
        if ax.get_title(loc="left").strip():
            add("titulo", ax._left_title.get_window_extent(r))
        leg = ax.get_legend()
        if leg is not None:
            add("legenda", leg.get_window_extent(r))
        por_gid = {}
        for tx in ax.texts:
            g = tx.get_gid()
            if g and tx.get_text().strip():
                try:
                    por_gid.setdefault(g, []).append(tx.get_window_extent(r))
                except Exception:
                    pass
        for g, bbs in por_gid.items():
            if g == "letras":
                for bb in bbs:
                    add("letras", bb, 2)
            else:
                add(g, Bbox.union(bbs), 2)
    if getattr(fig, "_suptitle", None) is not None and fig._suptitle.get_text().strip():
        add("titulo", fig._suptitle.get_window_extent(r))
    return out


def gerar_previa_mapa(sp, t, idioma="pt", dpi=150):
    """Prévia em PNG e as regiões clicáveis (eixos, legenda, letras…) para a edição por clique."""
    with _TRAVA:
        fig = figura(sp, t, idioma)
        try:
            try:
                regs = _regioes(fig) if sp.tipo != "diagnostico" else []
            except Exception:
                regs = []
            if not any(r_["id"] == "dados" for r_ in regs):      # sempre há ao menos a área do gráfico
                regs.insert(0, dict(id="dados", rot=ROTULOS_REGIAO["dados"], x=0.0, y=0.0, w=1.0, h=1.0))
            return previa(fig, dpi), regs, (fig.get_figwidth() * 25.4, fig.get_figheight() * 25.4)
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
