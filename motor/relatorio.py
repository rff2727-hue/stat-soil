"""
Orquestração: decide quais figuras cada resultado merece (como especificações
de dados, motor.figuras.Spec*) e empacota figuras para download.
"""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import figuras as fg
from . import tema as tm

PALAVRAS_CAMADA = ("prof", "camada", "depth", "layer", "horizonte")


def parece_camada(nome: str) -> bool:
    n = str(nome).lower()
    return any(p in n for p in PALAVRAS_CAMADA)


def _slug(s):
    s = re.sub(r"[^\w\-]+", "_", str(s), flags=re.UNICODE).strip("_")
    return s[:60] or "fig"


def _rot_x(f):
    return f.rotulo + (f" ({f.unidade})" if getattr(f, "unidade", "") else "")


@dataclass
class ItemFigura:
    id: str          # identificador estável (usado para guardar ajustes)
    nome: str        # nome de arquivo
    titulo: str      # rótulo legível
    spec: object
    variavel: str = ""
    grupo: str | None = None


def _curva(f, rotulo, alfa, modelo=None):
    reg = f.regressao
    return fg.Curva(rotulo=rotulo, x=reg.x, medias=reg.medias, ep=f.ep_dados, dp=f.dp_dados, n=f.n,
                    obs_x=reg.obs_x, obs_y=reg.obs_y, modelo=modelo or reg.melhor,
                    sig=f.p is not None and f.p < alfa, qm_erro=getattr(reg, "qm_erro", None),
                    ajustes=[a for a in reg.ajustes if a.convergiu],
                    chave=(f.fator, tuple(sorted(f.condicao.items()))))


def specs_para(res, rotulo_y=None, perfil=None, grupo=None, idioma="pt"):
    """Lista de ItemFigura para um ResultadoVariavel."""
    spec = res.spec
    ry = rotulo_y or res.variavel
    alfa = res.alfa
    itens = []
    usados = set()
    base = f"{_slug(res.variavel)}" + (f"__{_slug(grupo)}" if grupo else "")

    def add(sufixo, titulo, sp):
        itens.append(ItemFigura(id=f"{base}::{sufixo}", nome=f"{base}_{_slug(sufixo)}", titulo=titulo, spec=sp,
                                variavel=res.variavel, grupo=grupo))

    d = res.dados.d
    for td in res.tabelas_duplas:
        a, b = td["fatores"]
        fa, fb = spec.fatores[a], spec.fatores[b]
        usados |= {a, b}
        chave = f"{_slug(fa.rotulo)}_x_{_slug(fb.rotulo)}"
        if perfil in (a, b):
            cam, outro = (a, b) if perfil == a else (b, a)
            series = []
            for nv in res.dados.niveis[outro]:
                fat = [f for f in res.fatias if f.fator == cam and f.condicao == {outro: nv}]
                if fat:
                    f = fat[0]
                    series.append(dict(rotulo=nv, medias=f.medias_orig, ep=f.ep_dados, dp=f.dp_dados, n=f.n))
            add(chave + "_perfil", f"Perfil — {spec.fatores[outro].rotulo} × {spec.fatores[cam].rotulo}",
                fg.SpecPerfil(res.dados.niveis[cam], series, ry, _rot_x(spec.fatores[cam]), spec.fatores[outro].rotulo))
        if fa.quantitativo != fb.quantitativo or (fa.quantitativo and fb.quantitativo):
            q, o = ((a, b) if fa.quantitativo else (b, a)) if fa.quantitativo != fb.quantitativo else (a, b)
            curvas = []
            for nv in res.dados.niveis[o]:
                fat = [f for f in res.fatias if f.fator == q and f.condicao == {o: nv}]
                if fat and fat[0].regressao:
                    curvas.append(_curva(fat[0], nv, alfa))
            if curvas:
                add(chave + "_regressao", f"Regressão — {spec.fatores[q].rotulo} em cada {spec.fatores[o].rotulo}",
                    fg.SpecRegressao(curvas, _rot_x(spec.fatores[q]), ry, spec.fatores[o].rotulo))
        else:
            obs = d[[f"F{a}", f"F{b}", "y_orig"]].rename(columns={f"F{a}": "A", f"F{b}": "B", "y_orig": "y"})
            med = td["medias"]
            dp = pd.DataFrame(index=med.index, columns=med.columns, dtype=float)
            nn = pd.DataFrame(index=med.index, columns=med.columns, dtype=float)
            g = obs.groupby(["A", "B"])["y"]
            for (aa, bb), v in g:
                if aa in dp.index and bb in dp.columns:
                    dp.loc[aa, bb] = v.std(ddof=1)
                    nn.loc[aa, bb] = len(v)
            add(chave, f"Interação — {fa.rotulo} × {fb.rotulo}",
                fg.SpecGrupos(list(med.index), list(med.columns), med, td["ep"], dp, nn, td["letras"], obs,
                              fa.rotulo, fb.rotulo, ry))
    for f in res.fatias:
        fat = spec.fatores[f.fator]
        if f.condicao and f.fator in usados:
            continue
        cond = ", ".join(f"{spec.fatores[k].rotulo} = {v}" for k, v in f.condicao.items())
        chave = _slug(fat.rotulo) + (f"_{_slug(cond)}" if cond else "")
        titulo = fat.rotulo + (f" ({cond})" if cond else "")
        sig = f.p is not None and f.p < alfa
        if f.regressao is not None and not f.comparacao:
            add(chave + "_regressao", "Regressão — " + titulo,
                fg.SpecRegressao([_curva(f, None, alfa)], _rot_x(fat), ry))
            continue
        if perfil == f.fator and not f.condicao:
            add(chave + "_perfil", "Perfil — " + titulo,
                fg.SpecPerfil(f.niveis, [dict(rotulo=None, medias=f.medias_orig, ep=f.ep_dados, dp=f.dp_dados, n=f.n)],
                              ry, _rot_x(fat)))
        letras = None
        if f.comparacao is not None:
            letras = f.comparacao.letras if f.comparacao.metodo != "dunnett" else \
                [{"*": "*", "ns": "", "(controle)": ""}.get(L, "") for L in f.comparacao.letras]
        obs = f.obs[["nivel", "y_orig"]].rename(columns={"y_orig": "y"}) if f.obs is not None else None
        add(chave, "Médias — " + titulo,
            fg.SpecMedias(f.niveis, f.medias_orig, f.ep_dados, f.dp_dados, f.n, obs, letras, sig, _rot_x(fat), ry,
                          titulo=cond))
    ex = res.extras.get("todos_tratamentos")
    if ex:
        c = ex["comparacao"]
        trat_p = [l.p for l in res.anova if l.fonte == "Tratamentos"]
        sig = bool(trat_p and trat_p[0] is not None and trat_p[0] < alfa)
        obs = d[["CEL", "y_orig"]].rename(columns={"CEL": "nivel", "y_orig": "y"})
        add("todos_tratamentos", "Médias — todos os tratamentos",
            fg.SpecMedias(res.dados.celulas, ex["medias_orig"], ex["ep"], ex["ep"] * np.sqrt(ex["n"]), ex["n"], obs,
                          c.letras, sig, "Tratamento" if idioma == "pt" else "Treatment", ry))
    add("diagnostico", "Diagnóstico dos resíduos",
        fg.SpecDiagnostico(res.residuos, res.ajustados, res.residuos_std, res.dados.d["CEL"].to_numpy()))
    return itens


# ----------------------------------------------------------------------------
# compatibilidade: figuras prontas com um tema
# ----------------------------------------------------------------------------
def figuras_para(res, tema=None, rotulo_y=None, perfil=None, idioma="pt", incluir_diagnostico=False):
    t = tema if isinstance(tema, dict) else tm.resolver()
    out = []
    for it in specs_para(res, rotulo_y, perfil, idioma=idioma):
        if it.spec.tipo == "diagnostico" and not incluir_diagnostico:
            continue
        tt = {**t, "tela.largura_mm": max(t["tela.largura_mm"], 183)} if it.spec.tipo == "diagnostico" else t
        out.append((it.nome, it.titulo, fg.figura(it.spec, tt, idioma)))
    return out


def zip_figuras(itens, temas, formatos=("png", "svg"), idioma="pt") -> bytes:
    """itens: lista de (pasta, nome, spec_ou_figura); temas: dict nome -> tema (ou tema único)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for pasta, nome, obj in itens:
            t = temas.get(nome, temas.get("__padrao__")) if isinstance(temas, dict) and "__padrao__" in temas else temas
            fig = obj if hasattr(obj, "savefig") else fg.figura(obj, t, idioma)
            for ext, dados in fg.exportar(fig, t, formatos).items():
                caminho = f"{_slug(pasta)}/{ext}/{nome}.{ext}" if pasta else f"{ext}/{nome}.{ext}"
                z.writestr(caminho, dados)
            plt.close(fig)
    return buf.getvalue()
