"""
Análise conjunta de experimentos (vários locais, safras ou anos) com o mesmo
delineamento de um estrato (DIC/DBC, um fator ou fatorial).

Procedimento usual (Pimentel-Gomes; Banzatto & Kronka):
1. análises individuais e razão entre o maior e o menor QM do resíduo
   (Hartley; < 7 indica homogeneidade suficiente para a análise conjunta);
2. modelo conjunto com o ambiente como fator, blocos dentro de ambientes;
3. ambiente testado contra blocos/ambiente; se os ambientes forem
   considerados aleatórios, os tratamentos são testados contra a interação
   tratamentos × ambientes.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from .anova import Opcoes, analisar
from .modelo import ErroDelineamento, Especificacao, Fator


@dataclass
class ResultadoConjunta:
    individuais: pd.DataFrame       # ambiente, QM resíduo, GL, CV, média
    hartley: float
    homogeneo: bool
    resultado: object               # ResultadoVariavel do modelo conjunto
    anova: pd.DataFrame             # ANOVA conjunta com testes ajustados
    nota: str


def analise_conjunta(df, spec: Especificacao, variavel, coluna_amb, opcoes: Opcoes | None = None,
                     ambientes_aleatorios=False, rotulo_amb=None):
    if spec.multiestrato or spec.estrutura == "fatorial_adicional" or spec.base == "DQL":
        raise ErroDelineamento("A análise conjunta está disponível para DIC e DBC com um fator ou fatorial.")
    op = opcoes or Opcoes()
    indiv = []
    for amb, d in df.groupby(coluna_amb, sort=False):
        r = analisar(d, spec, variavel, op)
        e = [l for l in r.anova if l.tipo == "erro"][0]
        indiv.append({"Ambiente": str(amb), "QM resíduo": e.qm, "GL resíduo": e.gl,
                      "CV (%)": list(r.cv.values())[0], "Média": r.media_geral})
    ind = pd.DataFrame(indiv)
    hartley = float(ind["QM resíduo"].max() / ind["QM resíduo"].min())
    d = df.copy()
    sp = copy.deepcopy(spec)
    sp.fatores = list(sp.fatores) + [Fator(coluna_amb, rotulo_amb or str(coluna_amb), 1, False)]
    sp.estrutura = "fatorial"
    if spec.base == "DBC":
        d["_BLOCO_AMB"] = d[coluna_amb].astype(str) + " · " + d[spec.bloco].astype(str)
        sp.bloco = "_BLOCO_AMB"
        sp.aninhar_bloco = coluna_amb
    res = analisar(d, sp, variavel, op)
    ia = len(sp.fatores) - 1
    linhas = []
    erro = [l for l in res.anova if l.tipo == "erro"][0]
    blocos = [l for l in res.anova if l.tipo == "bloco"]
    inter_amb = {l.termo: l for l in res.anova if l.termo and isinstance(l.termo[0], int) and ia in l.termo}
    for l in res.anova:
        F, p, contra = l.f, l.p, l.erro
        if l.termo == (ia,) and blocos:
            b = blocos[0]
            F = l.qm / b.qm
            p = float(stats.f.sf(F, l.gl, b.gl))
            contra = "Blocos/Ambientes"
        elif ambientes_aleatorios and l.termo and isinstance(l.termo[0], int) and ia not in l.termo:
            alvo = inter_amb.get(tuple(sorted(l.termo + (ia,))))
            if alvo is not None and alvo.qm:
                F = l.qm / alvo.qm
                p = float(stats.f.sf(F, l.gl, alvo.gl))
                contra = alvo.fonte
        nome = "Blocos/Ambientes" if l.tipo == "bloco" else l.fonte
        linhas.append({"Fonte de variação": nome, "GL": l.gl, "SQ": l.sq, "QM": l.qm, "F": F, "p": p,
                       "Testado contra": contra if l.tipo not in ("erro", "total") else ""})
    nota = (f"Razão entre o maior e o menor QM do resíduo (Hartley) = {hartley:.2f}".replace(".", ",")
            + (" — variâncias homogêneas o suficiente para a análise conjunta (< 7)." if hartley < 7 else
               " — heterogeneidade elevada (≥ 7); interprete a análise conjunta com cautela ou ajuste os GL."))
    if ambientes_aleatorios:
        nota += " Ambientes considerados aleatórios: tratamentos testados contra a interação com ambientes."
    return ResultadoConjunta(ind, hartley, hartley < 7, res, pd.DataFrame(linhas), nota)
