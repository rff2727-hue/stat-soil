"""
Orquestração: escolhe os gráficos adequados para cada resultado e empacota
figuras e planilhas para download.
"""
from __future__ import annotations

import io
import re
import zipfile

import matplotlib.pyplot as plt
import numpy as np

from . import graficos as gr

PALAVRAS_CAMADA = ("prof", "camada", "depth", "layer", "horizonte")


def parece_camada(nome: str) -> bool:
    n = str(nome).lower()
    return any(p in n for p in PALAVRAS_CAMADA)


def _slug(s):
    s = re.sub(r"[^\w\-]+", "_", str(s), flags=re.UNICODE).strip("_")
    return s[:60] or "fig"


def _rot_x(f):
    return f.rotulo + (f" ({f.unidade})" if getattr(f, "unidade", "") else "")


def figuras_para(res, cfg: gr.ConfigGrafico, rotulo_y=None, perfil=None):
    """Lista de (nome, título, figura) para um ResultadoVariavel.

    perfil: índice do fator que representa camadas de solo (gráfico em perfil), ou None.
    """
    spec = res.spec
    ry = rotulo_y or res.variavel
    figs = []
    usados = set()
    alfa = res.alfa
    # interações duplas
    for td in res.tabelas_duplas:
        a, b = td["fatores"]
        fa, fb = spec.fatores[a], spec.fatores[b]
        usados |= {a, b}
        nome = f"{_slug(res.variavel)}_{_slug(fa.rotulo)}_x_{_slug(fb.rotulo)}"
        if perfil in (a, b):
            cam, outro = (a, b) if perfil == a else (b, a)
            series = []
            for nv in res.dados.niveis[outro]:
                fat = [f for f in res.fatias if f.fator == cam and f.condicao == {outro: nv}]
                if not fat:
                    continue
                f = fat[0]
                series.append(dict(rotulo=nv, medias=f.medias_orig, ep=f.ep_dados, dp=f.dp_dados, n=f.n))
            fig = gr.fig_perfil(series, res.dados.niveis[cam], cfg, rotulo_x=ry, rotulo_camada=_rot_x(spec.fatores[cam]),
                                titulo_legenda=spec.fatores[outro].rotulo)
            figs.append((nome + "_perfil", f"Perfil: {spec.fatores[outro].rotulo} × {spec.fatores[cam].rotulo}", fig))
        if fa.quantitativo != fb.quantitativo:
            q, o = (a, b) if fa.quantitativo else (b, a)
            curvas = []
            for nv in res.dados.niveis[o]:
                fat = [f for f in res.fatias if f.fator == q and f.condicao == {o: nv}]
                if fat and fat[0].regressao:
                    f = fat[0]
                    curvas.append(dict(rotulo=nv, reg=f.regressao, ep=f.ep_dados, dp=f.dp_dados, n=f.n,
                                       sig=f.p is not None and f.p < alfa))
            if curvas:
                fig = gr.fig_regressao(curvas, cfg, rotulo_x=_rot_x(spec.fatores[q]), rotulo_y=ry,
                                       titulo_legenda=spec.fatores[o].rotulo)
                figs.append((nome + "_regressao", f"Regressão: {spec.fatores[q].rotulo} em cada {spec.fatores[o].rotulo}", fig))
        elif not (fa.quantitativo and fb.quantitativo):
            d = res.dados.d
            obs = d[["F%d" % a, "F%d" % b, "y_orig"]].rename(columns={"F%d" % a: "A", "F%d" % b: "B", "y_orig": "y"})
            fig = gr.fig_interacao(td, cfg, obs=obs, rotulo_y=ry, nome_linhas=fa.rotulo, nome_colunas=fb.rotulo)
            figs.append((nome, f"Interação {fa.rotulo} × {fb.rotulo}", fig))
        elif fa.quantitativo and fb.quantitativo:
            # superfície: curvas de a em cada nível de b
            curvas = []
            for nv in res.dados.niveis[b]:
                fat = [f for f in res.fatias if f.fator == a and f.condicao == {b: nv}]
                if fat and fat[0].regressao:
                    f = fat[0]
                    curvas.append(dict(rotulo=nv, reg=f.regressao, ep=f.ep_dados, dp=f.dp_dados, n=f.n,
                                       sig=f.p is not None and f.p < alfa))
            if curvas:
                fig = gr.fig_regressao(curvas, cfg, rotulo_x=_rot_x(fa), rotulo_y=ry, titulo_legenda=fb.rotulo)
                figs.append((nome + "_regressao", f"Regressão: {fa.rotulo} em cada {fb.rotulo}", fig))
    # efeitos simples / principais
    for f in res.fatias:
        fat = spec.fatores[f.fator]
        if f.condicao and f.fator in usados:
            continue
        cond = ", ".join(f"{spec.fatores[k].rotulo} = {v}" for k, v in f.condicao.items())
        nome = f"{_slug(res.variavel)}_{_slug(fat.rotulo)}" + (f"_{_slug(cond)}" if cond else "")
        titulo = fat.rotulo + (f" ({cond})" if cond else "")
        sig = f.p is not None and f.p < alfa
        if f.regressao is not None and not f.comparacao:
            fig = gr.fig_regressao([dict(rotulo=None, reg=f.regressao, ep=f.ep_dados, dp=f.dp_dados, n=f.n, sig=sig)],
                                   cfg, rotulo_x=_rot_x(fat), rotulo_y=ry)
            figs.append((nome + "_regressao", "Regressão: " + titulo, fig))
            continue
        if perfil == f.fator and not f.condicao:
            fig = gr.fig_perfil([dict(rotulo=None, medias=f.medias_orig, ep=f.ep_dados, dp=f.dp_dados, n=f.n)],
                                f.niveis, cfg, rotulo_x=ry, rotulo_camada=_rot_x(fat))
            figs.append((nome + "_perfil", "Perfil: " + titulo, fig))
            continue
        letras = None
        if f.comparacao is not None and sig:
            letras = f.comparacao.letras if f.comparacao.metodo != "dunnett" else \
                [{"*": "*", "ns": "", "(controle)": ""}.get(L, "") for L in f.comparacao.letras]
        fig = gr.fig_medias(f.niveis, f.medias_orig, f.ep_dados, f.dp_dados, f.n, f.obs, letras, cfg,
                            rotulo_x=_rot_x(fat), rotulo_y=ry,
                            titulo=(cond if cond else None))
        figs.append((nome, titulo, fig))
    # fatorial + adicional: todos os tratamentos
    ex = res.extras.get("todos_tratamentos")
    if ex:
        c = ex["comparacao"]
        trat_p = [l.p for l in res.anova if l.fonte == "Tratamentos"]
        sig = bool(trat_p and trat_p[0] is not None and trat_p[0] < alfa)
        d = res.dados.d
        obs = d[["CEL", "y_orig"]].rename(columns={"CEL": "nivel"})
        fig = gr.fig_medias(res.dados.celulas, ex["medias_orig"], ex["ep"], ex["ep"] * np.sqrt(ex["n"]), ex["n"], obs,
                            c.letras if sig else None, cfg, rotulo_x="Tratamento" if cfg.idioma == "pt" else "Treatment",
                            rotulo_y=ry)
        figs.append((f"{_slug(res.variavel)}_todos_tratamentos", "Todos os tratamentos", fig))
    return figs


def fig_diagnostico(res, cfg):
    c = gr.ConfigGrafico(**{**cfg.__dict__, "largura_mm": 183, "altura_mm": None})
    return gr.fig_diagnostico(res.residuos, res.ajustados, res.residuos_std, res.dados.d["CEL"], c)


def zip_figuras(itens, cfg, formatos=None, fechar=True) -> bytes:
    """itens: lista de (pasta, nome, figura)."""
    formatos = formatos or cfg.formatos
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for pasta, nome, fig in itens:
            arquivos = gr.exportar(fig, cfg, formatos)
            for ext, dados in arquivos.items():
                caminho = f"{_slug(pasta)}/{ext}/{nome}.{ext}" if pasta else f"{ext}/{nome}.{ext}"
                z.writestr(caminho, dados)
            if fechar:
                plt.close(fig)
    return buf.getvalue()
