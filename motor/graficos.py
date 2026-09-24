"""
Gráficos prontos para publicação.

Diretrizes (Nature/Science/Lancet + preferências do usuário):
* Roboto, corpo 7 pt no tamanho final, sem negrito;
* sem linhas de grade, apenas eixos esquerdo e inferior, marcas para fora;
* médias com erro-padrão; observações individuais semitransparentes;
* larguras de coluna de periódico: 89 mm (1 col.), 120 mm (1,5 col.), 183 mm (2 col.);
* exportação em PNG e TIFF (600 dpi), SVG com texto editável e PDF vetorial.
"""
from __future__ import annotations

import io
import math
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Ellipse  # noqa: E402
import numpy as np  # noqa: E402
from scipy import stats  # noqa: E402

from .regressao import fmt_num  # noqa: E402

# ----------------------------------------------------------------------------
# Identidade visual
# ----------------------------------------------------------------------------
# Paleta categórica "Solos do Cerrado" — validada para daltonismo (ΔE CVD ≥ 8
# entre vizinhos) e distinção em visão normal (ΔE ≥ 15); segunda codificação
# por forma de marcador em todos os gráficos com grupos.
PALETA = ["#A6461E",  # terra roxa / Latossolo Vermelho
          "#2878A8",  # azul (água, Pantanal)
          "#D29A1C",  # ocre (goethita)
          "#3E8A45",  # verde Cerrado
          "#8A4E9E",  # violeta
          "#E0785A",  # terracota claro
          "#1F9A9A",  # verde-azulado
          "#9A5A14"]  # marrom húmico
MARCADORES = ["o", "s", "^", "D", "v", "P", "X", "h"]
COR_UNICA = "#5B3A29"       # marrom escuro (horizonte A)
COR_BARRA = "#E4D5C7"       # preenchimento claro (horizonte E)
COR_TINTA = "#1A1A1A"
COR_SECUNDARIA = "#6B6B6B"
DIVERGENTE = ("#2878A8", "#F4F1EC", "#A6461E")

MM = 1 / 25.4
LARGURAS = {"1 coluna (89 mm)": 89, "1,5 coluna (120 mm)": 120, "2 colunas (183 mm)": 183}

_FONTES_OK = False


def registrar_fontes():
    global _FONTES_OK
    if _FONTES_OK:
        return
    pasta = Path(__file__).resolve().parent.parent / "assets" / "fonts"
    for ttf in pasta.glob("*.ttf"):
        try:
            font_manager.fontManager.addfont(str(ttf))
        except Exception:
            pass
    _FONTES_OK = True


@dataclass
class ConfigGrafico:
    largura_mm: float = 89
    altura_mm: float | None = None
    fonte_pt: float = 7
    idioma: str = "pt"
    estilo: str = "pontos"          # pontos | barras
    mostrar_obs: bool = True
    alfa_obs: float = 0.45
    erro: str = "ep"                # ep | dp | ic95
    mostrar_letras: bool = True
    mostrar_equacao: bool = True
    rotulo_y: str | None = None
    rotulo_x: str | None = None
    paleta: list = field(default_factory=lambda: list(PALETA))
    cor_unica: str = COR_UNICA
    dpi: int = 600
    formatos: tuple = ("png", "svg", "pdf", "tiff")


def estilo(cfg: ConfigGrafico):
    registrar_fontes()
    fs = cfg.fonte_pt
    return {
        "font.family": ["Roboto", "DejaVu Sans"],
        "font.weight": "normal",
        "font.size": fs,
        "axes.titlesize": fs,
        "axes.titleweight": "normal",
        "axes.labelsize": fs,
        "axes.labelweight": "normal",
        "axes.labelcolor": COR_TINTA,
        "axes.edgecolor": COR_TINTA,
        "axes.linewidth": 0.6,
        "axes.grid": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.labelpad": 3,
        "axes.unicode_minus": True,
        "xtick.labelsize": fs,
        "ytick.labelsize": fs,
        "xtick.color": COR_TINTA,
        "ytick.color": COR_TINTA,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.size": 2.8,
        "ytick.major.size": 2.8,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.minor.size": 1.6,
        "ytick.minor.size": 1.6,
        "xtick.major.pad": 2.2,
        "ytick.major.pad": 2.2,
        "legend.frameon": False,
        "legend.fontsize": fs,
        "legend.handlelength": 1.4,
        "legend.handletextpad": 0.4,
        "legend.borderaxespad": 0.2,
        "legend.columnspacing": 1.0,
        "lines.linewidth": 1.0,
        "lines.markersize": 4,
        "errorbar.capsize": 0,
        "figure.dpi": 150,
        "savefig.dpi": cfg.dpi,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "mathtext.default": "regular",
    }


def _fig(cfg, altura_padrao_mm=None, ncols=1, nrows=1, **kw):
    alt = cfg.altura_mm or altura_padrao_mm or cfg.largura_mm * 0.72
    with plt.rc_context(estilo(cfg)):
        fig, ax = plt.subplots(nrows, ncols, figsize=(cfg.largura_mm * MM, alt * MM), **kw)
    return fig, ax


def _erro(ep, dp, n, cfg):
    if cfg.erro == "dp":
        return dp
    if cfg.erro == "ic95":
        return ep * stats.t.ppf(0.975, np.maximum(n - 1, 1))
    return ep


def rotulo_erro(cfg):
    return {"ep": ("erro-padrão", "standard error"), "dp": ("desvio-padrão", "standard deviation"),
            "ic95": ("IC 95%", "95% CI")}[cfg.erro][0 if cfg.idioma == "pt" else 1]


def _quebrar(rotulos, largura_char):
    return ["\n".join(textwrap.wrap(str(r), max(largura_char, 4), break_long_words=False)) or str(r) for r in rotulos]


def _jitter(n, largura=0.12, semente=0):
    if n <= 1:
        return np.zeros(n)
    rng = np.random.default_rng(semente)
    base = np.linspace(-largura, largura, n)
    rng.shuffle(base)
    return base


def _dec(v, cfg):
    return fmt_num(v, 3, cfg.idioma)


def _formatar_eixos_decimais(ax, cfg):
    if cfg.idioma == "pt":
        from matplotlib.ticker import FuncFormatter

        def fmt(v, pos):
            s = f"{v:g}" if abs(v) < 1e5 else f"{v:.2g}"
            return s.replace(".", ",").replace("-", "−")
        ax.yaxis.set_major_formatter(FuncFormatter(fmt))
        if ax.get_xscale() == "linear" and not getattr(ax, "_categ", False):
            ax.xaxis.set_major_formatter(FuncFormatter(fmt))


# ----------------------------------------------------------------------------
# 1. Médias de um fator (com letras)
# ----------------------------------------------------------------------------
def fig_medias(niveis, medias, ep, dp, n, obs=None, letras=None, cfg=None, titulo=None, rotulo_x=None,
               rotulo_y=None, controle=None):
    cfg = cfg or ConfigGrafico()
    k = len(niveis)
    horizontal = k > 10
    with plt.rc_context(estilo(cfg)):
        alt = cfg.altura_mm or (max(55, 6.5 * k + 20) if horizontal else cfg.largura_mm * 0.72)
        fig, ax = plt.subplots(figsize=(cfg.largura_mm * MM, alt * MM))
        pos = np.arange(k)
        barra = _erro(np.asarray(ep, float), np.asarray(dp, float), np.asarray(n, float), cfg)
        medias = np.asarray(medias, float)
        topo = medias + np.nan_to_num(barra)
        if cfg.estilo == "barras":
            if horizontal:
                ax.barh(pos, medias, height=0.62, color=COR_BARRA, edgecolor="none", zorder=1)
            else:
                ax.bar(pos, medias, width=0.62, color=COR_BARRA, edgecolor="none", zorder=1)
        if cfg.mostrar_obs and obs is not None and len(obs):
            for i, nv in enumerate(niveis):
                vals = obs.loc[obs["nivel"] == nv, "y_orig"].to_numpy(float)
                jit = _jitter(len(vals), 0.14 if cfg.estilo == "pontos" else 0.18, i)
                if horizontal:
                    ax.scatter(vals, pos[i] + jit, s=7, color=cfg.cor_unica, alpha=cfg.alfa_obs, lw=0, zorder=2)
                else:
                    ax.scatter(pos[i] + jit, vals, s=7, color=cfg.cor_unica, alpha=cfg.alfa_obs, lw=0, zorder=2)
                if len(vals):
                    topo[i] = max(topo[i], np.nanmax(vals))
        dx = 0.28 if (cfg.estilo == "pontos" and cfg.mostrar_obs) else 0.0
        if horizontal:
            ax.errorbar(medias, pos + (dx if cfg.estilo == "pontos" else 0), xerr=barra, fmt="o" if cfg.estilo == "pontos" else "none",
                        color=cfg.cor_unica, ms=4, elinewidth=0.8, zorder=3, markeredgewidth=0)
        else:
            ax.errorbar(pos + dx, medias, yerr=barra, fmt="o" if cfg.estilo == "pontos" else "none",
                        color=cfg.cor_unica, ms=4, elinewidth=0.8, zorder=3, markeredgewidth=0)
        # limites e letras
        base_min = min(np.nanmin(medias - np.nan_to_num(barra)),
                       np.nanmin(obs["y_orig"]) if (cfg.mostrar_obs and obs is not None and len(obs)) else np.inf)
        vmax = np.nanmax(topo)
        faixa = vmax - (0 if cfg.estilo == "barras" else base_min)
        faixa = faixa if faixa > 0 else abs(vmax) or 1
        if letras is not None and cfg.mostrar_letras:
            for i, L in enumerate(letras):
                if not L:
                    continue
                if horizontal:
                    ax.text(topo[i] + 0.03 * faixa, pos[i], L, va="center", ha="left", color=COR_TINTA)
                else:
                    ax.text(pos[i] + dx, topo[i] + 0.035 * faixa, L, ha="center", va="bottom", color=COR_TINTA)
        lo = 0 if cfg.estilo == "barras" else base_min - 0.06 * faixa
        hi = vmax + (0.14 if letras is not None else 0.05) * faixa
        largura_char = int(max(6, (cfg.largura_mm / max(k, 1)) / 1.6))
        rot = _quebrar(niveis, largura_char)
        if horizontal:
            ax.set_xlim(lo if cfg.estilo == "pontos" else 0, hi)
            ax.set_yticks(pos, rot)
            ax.set_ylim(k - 0.5, -0.5)
            ax.spines["left"].set_visible(False)
            ax.tick_params(axis="y", length=0)
            ax.set_xlabel(rotulo_y or cfg.rotulo_y or "")
            if rotulo_x:
                ax.set_ylabel(rotulo_x)
        else:
            ax.set_ylim(lo, hi)
            ax.set_xticks(pos, rot)
            ax.set_xlim(-0.6, k - 0.4)
            ax.tick_params(axis="x", length=0)
            ax._categ = True
            if max(len(str(r)) for r in niveis) > largura_char * 2:
                plt.setp(ax.get_xticklabels(), rotation=35, ha="right", rotation_mode="anchor")
            ax.set_ylabel(rotulo_y or cfg.rotulo_y or "")
            if rotulo_x:
                ax.set_xlabel(rotulo_x)
        if titulo:
            ax.set_title(titulo, loc="left", pad=4)
        _formatar_eixos_decimais(ax, cfg)
        fig.tight_layout(pad=0.3)
    return fig


# ----------------------------------------------------------------------------
# 2. Interação entre dois fatores qualitativos (barras/pontos agrupados)
# ----------------------------------------------------------------------------
def fig_interacao(tab, cfg=None, obs=None, rotulo_y=None, nome_linhas="", nome_colunas=""):
    """tab: dict de tabelas_duplas (medias, ep, letras: DataFrame linhas=A, colunas=B).
    Eixo x = níveis de A; grupos (cor+marcador) = níveis de B."""
    cfg = cfg or ConfigGrafico()
    med, ep, let = tab["medias"], tab["ep"], tab["letras"]
    A, B = list(med.index), list(med.columns)
    ka, kb = len(A), len(B)
    largura = max(cfg.largura_mm, min(183, 9 * ka * kb + 25))   # alarga automaticamente quando há muitos grupos
    with plt.rc_context(estilo(cfg)):
        fig, ax = plt.subplots(figsize=(largura * MM, (cfg.altura_mm or min(cfg.largura_mm * 0.8, 95)) * MM))
        larg = min(0.8 / kb, 0.28)
        topo_glob, base_glob = -np.inf, np.inf
        for j, b in enumerate(B):
            cor = cfg.paleta[j % len(cfg.paleta)]
            mk = MARCADORES[j % len(MARCADORES)]
            x = np.arange(ka) + (j - (kb - 1) / 2) * larg
            m = med[b].to_numpy(float)
            e = np.nan_to_num(ep[b].to_numpy(float))
            topo = m + e
            if cfg.estilo == "barras":
                ax.bar(x, m, width=larg * 0.9, color=cor, alpha=0.28, edgecolor="none", zorder=1)
            if cfg.mostrar_obs and obs is not None:
                for i, a in enumerate(A):
                    vals = obs.loc[(obs["A"] == a) & (obs["B"] == b), "y"].to_numpy(float)
                    ax.scatter(x[i] + _jitter(len(vals), larg * 0.18, i + 7 * j), vals, s=5, color=cor,
                               alpha=cfg.alfa_obs, lw=0, zorder=2, marker=mk)
                    if len(vals):
                        topo[i] = max(topo[i], vals.max())
                        base_glob = min(base_glob, vals.min())
            ax.errorbar(x, m, yerr=e, fmt=mk, color=cor, ms=3.6, elinewidth=0.8, zorder=3, markeredgewidth=0,
                        label=str(b), mfc=cor if cfg.estilo == "pontos" else cor)
            topo_glob = max(topo_glob, np.nanmax(topo))
            base_glob = min(base_glob, np.nanmin(m - e))
            if cfg.mostrar_letras:
                for i, a in enumerate(A):
                    L = let.loc[a, b].replace(" ", "").strip()
                    ax.text(x[i], topo[i], "\n" if False else L, ha="center", va="bottom", color=COR_TINTA,
                            fontsize=cfg.fonte_pt - 0.5, rotation=90 if kb * ka > 16 and len(L) > 2 else 0)
        faixa = topo_glob - (0 if cfg.estilo == "barras" else base_glob)
        for t in ax.texts:
            t.set_y(t.get_position()[1] + 0.03 * faixa)
        ax.set_ylim(0 if cfg.estilo == "barras" else base_glob - 0.06 * faixa, topo_glob + 0.16 * faixa)
        largura_char = int(max(6, (largura / max(ka, 1)) / 1.6))
        ax.set_xticks(np.arange(ka), _quebrar(A, largura_char))
        ax.tick_params(axis="x", length=0)
        ax._categ = True
        ax.set_xlim(-0.6, ka - 0.4)
        ax.set_ylabel(rotulo_y or cfg.rotulo_y or "")
        if nome_linhas:
            ax.set_xlabel(nome_linhas)
        hs = [Line2D([], [], color=cfg.paleta[j % len(cfg.paleta)], marker=MARCADORES[j % len(MARCADORES)], ms=3.8,
                     lw=0) for j in range(kb)]
        ax.legend(hs, [str(b) for b in B], title=nome_colunas or None, ncol=min(kb, 5), loc="lower left",
                  bbox_to_anchor=(0, 1.0), alignment="left", title_fontsize=cfg.fonte_pt, handletextpad=0.1)
        _formatar_eixos_decimais(ax, cfg)
        fig.tight_layout(pad=0.3)
    return fig


# ----------------------------------------------------------------------------
# 3. Regressão (uma ou várias curvas)
# ----------------------------------------------------------------------------
def fig_regressao(curvas, cfg=None, rotulo_x=None, rotulo_y=None, titulo_legenda=None, mostrar_ns=True):
    """curvas: lista de dicts {rotulo, reg: ResultadoRegressao, ep, dp, n, sig: bool, modelo: AjusteModelo|None}"""
    cfg = cfg or ConfigGrafico()
    multi = len(curvas) > 1
    with plt.rc_context(estilo(cfg)):
        fig, ax = plt.subplots(figsize=(cfg.largura_mm * MM, (cfg.altura_mm or cfg.largura_mm * 0.75) * MM))
        textos = []
        xs_all = np.concatenate([c["reg"].x for c in curvas])
        xr = xs_all.max() - xs_all.min()
        for j, c in enumerate(curvas):
            reg = c["reg"]
            cor = cfg.paleta[j % len(cfg.paleta)] if multi else cfg.cor_unica
            mk = MARCADORES[j % len(MARCADORES)] if multi else "o"
            off = (j - (len(curvas) - 1) / 2) * 0.012 * xr if multi else 0
            if cfg.mostrar_obs and reg.obs_x is not None:
                ax.scatter(reg.obs_x + off + _jitter(len(reg.obs_x), 0.006 * xr, j), reg.obs_y, s=6, color=cor,
                           alpha=cfg.alfa_obs * (0.8 if multi else 1), lw=0, marker=mk, zorder=2)
            e = _erro(np.asarray(c["ep"], float), np.asarray(c["dp"], float), np.asarray(c["n"], float), cfg)
            ax.errorbar(reg.x + off, reg.medias, yerr=e, fmt=mk, color=cor, ms=3.8, elinewidth=0.8, zorder=4,
                        markeredgewidth=0.5, mec="white")
            mod = c.get("modelo") or reg.melhor
            xx = np.linspace(reg.x.min(), reg.x.max(), 300)
            if c.get("sig", True) and mod is not None:
                ax.plot(xx, mod.prever(xx), color=cor, lw=1.0, zorder=3,
                        ls=["-", "--", "-.", ":"][j % 4] if multi else "-")
                txt = f"{mod.equacao(cfg.idioma, 4)}   R² = {_dec(mod.r2, cfg)}"
            else:
                ybar = float(np.sum(reg.medias * reg.n) / np.sum(reg.n))
                if mostrar_ns:
                    ax.plot(xx, np.full_like(xx, ybar), color=cor, lw=0.8, ls=(0, (2, 2)), zorder=3)
                txt = f"ȳ = {_dec(ybar, cfg)} (ns)"
            textos.append((c.get("rotulo"), txt, cor, mk))
        ax.set_xlabel(rotulo_x or cfg.rotulo_x or "")
        ax.set_ylabel(rotulo_y or cfg.rotulo_y or "")
        ax.set_xticks(np.unique(xs_all))
        ax.set_xlim(xs_all.min() - 0.06 * xr, xs_all.max() + 0.06 * xr)
        y0, y1 = ax.get_ylim()
        chars = int(cfg.largura_mm / (0.2 * cfg.fonte_pt))   # ~caracteres por linha na largura da figura
        if cfg.mostrar_equacao and not multi:
            r_, t_, cor, mk = textos[0]
            linhas = t_.split("   ")
            eq = linhas[0].split("; ")
            bloco = "\n".join(eq + linhas[1:])
            nl = bloco.count("\n") + 1
            ax.set_ylim(y0, y1 + (y1 - y0) * (0.05 + 0.085 * nl))
            reg = curvas[0]["reg"]
            meio = len(reg.x) // 2
            crescente = np.mean(reg.medias[:max(meio, 1)]) <= np.mean(reg.medias[-max(meio, 1):])
            ax.text(0.03 if crescente else 0.97, 0.98, bloco, transform=ax.transAxes, va="top",
                    ha="left" if crescente else "right", fontsize=cfg.fonte_pt - 0.5, color=COR_TINTA,
                    linespacing=1.35)
        elif multi:
            handles = [Line2D([], [], color=cor, marker=mk, ms=3.5, lw=1.0, ls=["-", "--", "-.", ":"][i % 4])
                       for i, (_, _, cor, mk) in enumerate(textos)]
            if cfg.mostrar_equacao:
                labels = ["\n".join(textwrap.wrap(f"{r}: {t.replace('   ', '; ')}" if r else t, chars - 6,
                                                   break_long_words=False)) for r, t, _, _ in textos]
                ax.legend(handles, labels, loc="upper left", bbox_to_anchor=(-0.02, -0.16),
                          fontsize=cfg.fonte_pt - 0.5, handlelength=2.4, title=titulo_legenda,
                          title_fontsize=cfg.fonte_pt - 0.5, alignment="left", labelspacing=0.5)
            else:
                ax.legend(handles, [r for r, _, _, _ in textos], title=titulo_legenda, loc="best",
                          handlelength=2.4)
        _formatar_eixos_decimais(ax, cfg)
        fig.tight_layout(pad=0.3)
    return fig


# ----------------------------------------------------------------------------
# 4. Perfil em profundidade (fator camada no eixo vertical)
# ----------------------------------------------------------------------------
def fig_perfil(series, camadas, cfg=None, rotulo_x=None, rotulo_camada=None, titulo_legenda=None):
    """series: lista de dicts {rotulo, medias (por camada), ep, dp, n, letras (por camada, opcional)}.
    As camadas seguem a ordem dada (superfície no topo)."""
    cfg = cfg or ConfigGrafico()
    kc = len(camadas)
    multi = len(series) > 1
    with plt.rc_context(estilo(cfg)):
        alt = cfg.altura_mm or max(cfg.largura_mm * 0.9, 18 * kc + 25)
        fig, ax = plt.subplots(figsize=(cfg.largura_mm * MM, alt * MM))
        pos = np.arange(kc)
        for j, s in enumerate(series):
            cor = cfg.paleta[j % len(cfg.paleta)] if multi else cfg.cor_unica
            mk = MARCADORES[j % len(MARCADORES)] if multi else "o"
            off = (j - (len(series) - 1) / 2) * min(0.05, 0.3 / max(len(series), 1)) if multi else 0
            m = np.asarray(s["medias"], float)
            e = _erro(np.asarray(s["ep"], float), np.asarray(s["dp"], float), np.asarray(s["n"], float), cfg)
            ax.plot(m, pos + off, color=cor, lw=0.9, zorder=2, ls=["-", "--", "-.", ":"][j % 4] if multi else "-")
            ax.errorbar(m, pos + off, xerr=e, fmt=mk, color=cor, ms=3.6, elinewidth=0.8, zorder=3,
                        markeredgewidth=0.5, mec="white", label=s.get("rotulo"))
        ax.set_yticks(pos, [str(c) for c in camadas])
        ax.set_ylim(kc - 0.6, -0.4)
        ax.spines["bottom"].set_visible(False)
        ax.spines["top"].set_visible(True)
        ax.xaxis.set_ticks_position("top")
        ax.xaxis.set_label_position("top")
        ax.set_xlabel(rotulo_x or cfg.rotulo_x or "")
        ax.set_ylabel(rotulo_camada or "")
        if multi:
            hs = [Line2D([], [], color=cfg.paleta[j % len(cfg.paleta)], marker=MARCADORES[j % len(MARCADORES)],
                         ms=3.6, lw=0.9, ls=["-", "--", "-.", ":"][j % 4], mec="white", mew=0.5)
                  for j in range(len(series))]
            ax.legend(hs, [s.get("rotulo") for s in series], title=titulo_legenda, loc="upper left",
                      bbox_to_anchor=(0, -0.02), fontsize=cfg.fonte_pt - 0.5,
                      title_fontsize=cfg.fonte_pt - 0.5, alignment="left", ncol=min(len(series), 3),
                      handlelength=2.4)
        _formatar_eixos_decimais(ax, cfg)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FixedFormatter([str(c) for c in camadas]))
        fig.tight_layout(pad=0.3)
    return fig


# ----------------------------------------------------------------------------
# 5. Diagnóstico dos resíduos
# ----------------------------------------------------------------------------
def fig_diagnostico(res, ajust, rstd, grupos, cfg=None, titulo=None):
    cfg = cfg or ConfigGrafico(largura_mm=183)
    pt = cfg.idioma == "pt"
    r = np.asarray(res, float)
    with plt.rc_context(estilo(cfg)):
        fig, axs = plt.subplots(1, 4, figsize=(cfg.largura_mm * MM, (cfg.altura_mm or 52) * MM))
        cor = cfg.cor_unica
        a = cfg.alfa_obs
        # (a) resíduos x ajustados
        ax = axs[0]
        ax.scatter(ajust, rstd, s=8, color=cor, alpha=a, lw=0)
        ax.axhline(0, color=COR_SECUNDARIA, lw=0.5, ls=(0, (2, 2)))
        for lim in (-3, 3):
            ax.axhline(lim, color=PALETA[0], lw=0.5, ls=(0, (1, 2)))
        ax.set_xlabel("Valores ajustados" if pt else "Fitted values")
        ax.set_ylabel("Resíduo studentizado" if pt else "Studentized residual")
        # (b) Q-Q normal com envelope
        ax = axs[1]
        n = len(r)
        z = (r - r.mean()) / (r.std(ddof=1) if r.std(ddof=1) > 0 else 1)
        zs = np.sort(z)
        pp = (np.arange(1, n + 1) - 0.375) / (n + 0.25)
        teo = stats.norm.ppf(pp)
        # envelope pontual 95% (estatísticas de ordem)
        lo = stats.norm.ppf(stats.beta.ppf(0.025, np.arange(1, n + 1), n - np.arange(1, n + 1) + 1))
        hi = stats.norm.ppf(stats.beta.ppf(0.975, np.arange(1, n + 1), n - np.arange(1, n + 1) + 1))
        ax.fill_between(teo, lo, hi, color=COR_BARRA, lw=0, zorder=1)
        ax.plot(teo, teo, color=COR_SECUNDARIA, lw=0.6, zorder=2)
        ax.scatter(teo, zs, s=8, color=cor, alpha=a, lw=0, zorder=3)
        ax.set_xlabel("Quantis teóricos" if pt else "Theoretical quantiles")
        ax.set_ylabel("Quantis amostrais" if pt else "Sample quantiles")
        # (c) histograma + densidade normal
        ax = axs[2]
        nb = max(5, min(20, int(np.sqrt(n)) + 2))
        ax.hist(r, bins=nb, color=COR_BARRA, edgecolor="white", lw=0.5, density=True)
        xx = np.linspace(r.min(), r.max(), 200)
        ax.plot(xx, stats.norm.pdf(xx, r.mean(), r.std(ddof=1) or 1), color=cor, lw=0.9)
        ax.set_xlabel("Resíduo" if pt else "Residual")
        ax.set_ylabel("Densidade" if pt else "Density")
        # (d) resíduos por tratamento
        ax = axs[3]
        grupos = np.asarray(grupos)
        ordem = list(dict.fromkeys(grupos))
        for i, g in enumerate(ordem):
            v = r[grupos == g]
            ax.scatter(np.full(len(v), i) + _jitter(len(v), 0.15, i), v, s=6, color=cor, alpha=a, lw=0)
            if len(v) > 1:
                ax.plot([i - 0.25, i + 0.25], [np.median(v)] * 2, color=COR_TINTA, lw=0.8)
        ax.axhline(0, color=COR_SECUNDARIA, lw=0.5, ls=(0, (2, 2)))
        if len(ordem) > 8:
            passo = int(np.ceil(len(ordem) / 8))
            ax.set_xticks(range(0, len(ordem), passo), [str(i + 1) for i in range(0, len(ordem), passo)])
        else:
            ax.set_xticks(range(len(ordem)), _quebrar(ordem, 8))
        if len(ordem) > 4 and len(ordem) <= 8:
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor",
                     fontsize=cfg.fonte_pt - 1)
        ax.tick_params(axis="x", length=0)
        ax.set_xlabel("Tratamento" if pt else "Treatment")
        ax.set_ylabel("Resíduo" if pt else "Residual")
        for i, ax in enumerate(axs):
            ax.text(-0.02, 1.04, "abcd"[i], transform=ax.transAxes, fontsize=cfg.fonte_pt + 1, va="bottom",
                    ha="right")
            if i != 3:
                _formatar_eixos_decimais(ax, cfg)
        if titulo:
            fig.suptitle(titulo, x=0.01, ha="left", fontsize=cfg.fonte_pt)
        fig.tight_layout(pad=0.3, w_pad=1.0)
    return fig


# ----------------------------------------------------------------------------
# 6. Matriz de correlação
# ----------------------------------------------------------------------------
def fig_correlacao(R, P, nomes, cfg=None, metodo="Pearson"):
    from matplotlib.colors import LinearSegmentedColormap
    cfg = cfg or ConfigGrafico()
    k = len(nomes)
    cmap = LinearSegmentedColormap.from_list("div_solo", DIVERGENTE)
    with plt.rc_context(estilo(cfg)):
        lado = cfg.largura_mm
        fig, ax = plt.subplots(figsize=(lado * MM, lado * 0.86 * MM))
        mask = np.triu(np.ones((k, k), bool), 0)
        for i in range(k):
            for j in range(k):
                if j >= i:
                    continue
                v = R[i, j]
                ax.add_patch(matplotlib.patches.Rectangle((j - 0.5 + 0.03, i - 0.5 + 0.03), 0.94, 0.94,
                                                          color=cmap((v + 1) / 2), lw=0))
                est = "***" if P[i, j] < 0.001 else "**" if P[i, j] < 0.01 else "*" if P[i, j] < 0.05 else ""
                txt = f"{v:.2f}".replace("-", "−")
                txt = txt.replace(".", ",") if cfg.idioma == "pt" else txt
                cor_txt = "white" if abs(v) > 0.6 else COR_TINTA
                fs = max(cfg.fonte_pt - 0.5 - max(0, k - 8) * 0.35, 4.5)
                ax.text(j, i - 0.08, txt, ha="center", va="center", color=cor_txt, fontsize=fs)
                if est:
                    ax.text(j, i + 0.24, est, ha="center", va="center", color=cor_txt, fontsize=fs - 0.5)
        ax.set_xlim(-0.5, k - 1.5)
        ax.set_ylim(k - 0.5, 0.5)
        ax.set_xticks(range(k - 1), _quebrar(nomes[:-1], 12))
        ax.set_yticks(range(1, k), _quebrar(nomes[1:], 18))
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(length=0)
        sm = matplotlib.cm.ScalarMappable(cmap=cmap, norm=matplotlib.colors.Normalize(-1, 1))
        cb = fig.colorbar(sm, ax=ax, fraction=0.035, pad=0.02, ticks=[-1, -0.5, 0, 0.5, 1])
        cb.outline.set_visible(False)
        cb.ax.tick_params(length=2, width=0.5)
        cb.set_label(f"r ({metodo})" if cfg.idioma == "en" else f"r de {metodo}")
        if cfg.idioma == "pt":
            cb.ax.set_yticklabels(["−1", "−0,5", "0", "0,5", "1"])
        ax.set_aspect("equal")
        nota = "* p < 0,05; ** p < 0,01; *** p < 0,001" if cfg.idioma == "pt" else "* P < 0.05; ** P < 0.01; *** P < 0.001"
        ax.text(1.0, 1.0, nota, transform=ax.transAxes, ha="right", va="top", fontsize=cfg.fonte_pt - 1,
                color=COR_SECUNDARIA)
        fig.tight_layout(pad=0.3)
    return fig


# ----------------------------------------------------------------------------
# 7. PCA (biplot)
# ----------------------------------------------------------------------------
def fig_pca(escores, cargas, nomes_var, grupos, explicada, cfg=None, elipses=None, titulo_legenda=None,
            rotulos_pontos=None):
    cfg = cfg or ConfigGrafico()
    grupos = np.asarray(grupos)
    ordem = list(dict.fromkeys(grupos))
    pt = cfg.idioma == "pt"
    if elipses is None:
        elipses = len(ordem) <= 5
    with plt.rc_context(estilo(cfg)):
        fig, ax = plt.subplots(figsize=(cfg.largura_mm * MM, (cfg.altura_mm or cfg.largura_mm * 0.82) * MM))
        ax.axhline(0, color="#BDBDBD", lw=0.4, zorder=0)
        ax.axvline(0, color="#BDBDBD", lw=0.4, zorder=0)
        for j, g in enumerate(ordem):
            sel = grupos == g
            cor = cfg.paleta[j % len(cfg.paleta)]
            mk = MARCADORES[j % len(MARCADORES)]
            ax.scatter(escores[sel, 0], escores[sel, 1], s=14, color=cor, alpha=0.7 if sel.sum() > 3 else 0.9,
                       lw=0, marker=mk, label=str(g), zorder=3)
            if elipses and sel.sum() >= 3:
                _elipse(ax, escores[sel, :2], cor)
        # cargas escaladas ao alcance dos escores
        esc = np.abs(escores[:, :2]).max() / max(np.abs(cargas[:, :2]).max(), 1e-9) * 0.85
        pos_txt = []
        for i, nm in enumerate(nomes_var):
            x, y = cargas[i, 0] * esc, cargas[i, 1] * esc
            ax.annotate("", xy=(x, y), xytext=(0, 0),
                        arrowprops=dict(arrowstyle="-|>,head_length=0.35,head_width=0.18", color="#4A4A4A", lw=0.6),
                        zorder=4)
            pos_txt.append([x * 1.1, y * 1.1])
        pos_txt = _repelir(np.array(pos_txt), escala=np.abs(escores[:, :2]).max() * 0.07)
        for (x, y), nm, c in zip(pos_txt, nomes_var, cargas):
            ax.text(x, y, nm, fontsize=cfg.fonte_pt - 0.5, color="#333333", ha="left" if c[0] >= 0 else "right",
                    va="center", zorder=5)
        tudo = np.vstack([escores[:, :2], pos_txt])
        lo, hi = tudo.min(axis=0), tudo.max(axis=0)
        mg = (hi - lo) * 0.08
        ax.set_xlim(lo[0] - mg[0], hi[0] + mg[0] * 2.2)
        ax.set_ylim(lo[1] - mg[1], hi[1] + mg[1])
        if rotulos_pontos is not None:
            for (x, y), rt in zip(escores[:, :2], rotulos_pontos):
                ax.text(x, y, " " + str(rt), fontsize=cfg.fonte_pt - 1, color=COR_SECUNDARIA, va="center")
        ax.set_xlabel(f"{'CP' if pt else 'PC'}1 ({_dec(explicada[0] * 100, cfg)}%)")
        ax.set_ylabel(f"{'CP' if pt else 'PC'}2 ({_dec(explicada[1] * 100, cfg)}%)")
        if len(ordem) > 1:
            ax.legend(title=titulo_legenda, loc="upper left", bbox_to_anchor=(1.0, 1.0), fontsize=cfg.fonte_pt - 0.5,
                      title_fontsize=cfg.fonte_pt - 0.5, alignment="left", markerscale=0.9, handletextpad=0.2)
        _formatar_eixos_decimais(ax, cfg)
        fig.tight_layout(pad=0.3)
    return fig


def _repelir(p, escala, iter_=200):
    """Afasta rótulos sobrepostos (repulsão simples)."""
    p = p.astype(float).copy()
    for _ in range(iter_):
        mov = False
        for i in range(len(p)):
            for j in range(i + 1, len(p)):
                d = p[i] - p[j]
                dist = np.hypot(*d)
                if dist < escala:
                    if dist < 1e-9:
                        d = np.array([0.0, 1.0])
                        dist = 1.0
                    ajuste = (escala - dist) / 2 * d / dist
                    ajuste[1] *= 1.6
                    p[i] += ajuste
                    p[j] -= ajuste
                    mov = True
        if not mov:
            break
    return p


def _elipse(ax, pts, cor, conf=0.95):
    cov = np.cov(pts, rowvar=False)
    if not np.all(np.isfinite(cov)) or np.linalg.det(cov) <= 0:
        return
    vals, vecs = np.linalg.eigh(cov)
    ordem = vals.argsort()[::-1]
    vals, vecs = vals[ordem], vecs[:, ordem]
    ang = math.degrees(math.atan2(vecs[1, 0], vecs[0, 0]))
    k = math.sqrt(stats.chi2.ppf(conf, 2))
    w, h = 2 * k * np.sqrt(vals)
    ax.add_patch(Ellipse(pts.mean(axis=0), w, h, angle=ang, facecolor=cor, alpha=0.10, edgecolor=cor, lw=0.6,
                         zorder=1))


# ----------------------------------------------------------------------------
# 8. Box-Cox (perfil de verossimilhança)
# ----------------------------------------------------------------------------
def fig_boxcox(bc, cfg=None):
    cfg = cfg or ConfigGrafico()
    with plt.rc_context(estilo(cfg)):
        fig, ax = plt.subplots(figsize=(cfg.largura_mm * MM, cfg.largura_mm * 0.6 * MM))
        ax.plot(bc["lambdas"], bc["loglik"], color=cfg.cor_unica, lw=1)
        corte = bc["loglik"].max() - stats.chi2.ppf(0.95, 1) / 2
        ax.axhline(corte, color=COR_SECUNDARIA, lw=0.5, ls=(0, (2, 2)))
        for v in bc["ic95"]:
            ax.axvline(v, color=COR_SECUNDARIA, lw=0.5, ls=(0, (1, 2)))
        ax.axvline(bc["lambda_hat"], color=PALETA[0], lw=0.8)
        ax.set_xlabel("λ")
        ax.set_ylabel("Log-verossimilhança" if cfg.idioma == "pt" else "Log-likelihood")
        _formatar_eixos_decimais(ax, cfg)
        fig.tight_layout(pad=0.3)
    return fig


# ----------------------------------------------------------------------------
# Exportação
# ----------------------------------------------------------------------------
def exportar(fig, cfg=None, formatos=None) -> dict:
    cfg = cfg or ConfigGrafico()
    formatos = formatos or cfg.formatos
    out = {}
    with plt.rc_context(estilo(cfg)):
        for fmt in formatos:
            buf = io.BytesIO()
            if fmt == "tiff":
                fig.savefig(buf, format="tiff", dpi=cfg.dpi, pil_kwargs={"compression": "tiff_lzw"})
            elif fmt == "png":
                fig.savefig(buf, format="png", dpi=cfg.dpi)
            else:
                fig.savefig(buf, format=fmt)
            out[fmt] = buf.getvalue()
    return out


def png_preview(fig, dpi=220) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", pad_inches=0.02)
    return buf.getvalue()
