"""
Conjuntos de dados de exemplo (simulados, com semente fixa) para cada
delineamento. Servem de modelo de planilha, de demonstração na interface e de
casos de teste.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from .modelo import Especificacao, Fator

SEMENTE = 2026


def _rng(k=0):
    return np.random.default_rng(SEMENTE + k)


def dic():
    rng = _rng(1)
    trats = ["Controle", "Calcário", "Gesso", "Calcário + Gesso", "Silicato"]
    ef = [0, 420, 180, 610, 350]
    linhas = []
    for t, e in zip(trats, ef):
        for r in range(1, 5):
            linhas.append({"Tratamento": t, "Repetição": r,
                           "Produtividade (kg/ha)": round(3200 + e + rng.normal(0, 160), 1),
                           "Altura (cm)": round(68 + e / 60 + rng.normal(0, 2.5), 1)})
    spec = Especificacao("DIC", "simples", [Fator("Tratamento", "Tratamento")], bloco="Repetição")
    return pd.DataFrame(linhas), spec, ["Produtividade (kg/ha)", "Altura (cm)"]


def dbc():
    rng = _rng(2)
    trats = ["BRS 1001", "BRS 1003", "BRS 2020", "BRS 3050", "BRS 4001", "BRS 5601"]
    ef = [0, 210, -150, 380, 90, 520]
    blocos = rng.normal(0, 140, 4)
    linhas = []
    for b in range(4):
        for t, e in zip(trats, ef):
            linhas.append({"Bloco": b + 1, "Cultivar": t,
                           "Produtividade (kg/ha)": round(3500 + e + blocos[b] + rng.normal(0, 150), 1),
                           "Massa de 100 grãos (g)": round(15.5 + e / 400 + rng.normal(0, 0.45), 2),
                           "Altura (cm)": round(82 + e / 50 + rng.normal(0, 3), 1)})
    spec = Especificacao("DBC", "simples", [Fator("Cultivar", "Cultivar")], bloco="Bloco")
    return pd.DataFrame(linhas), spec, ["Produtividade (kg/ha)", "Massa de 100 grãos (g)", "Altura (cm)"]


def dql():
    rng = _rng(3)
    trats = ["A", "B", "C", "D", "E"]
    ef = dict(zip(trats, [0, 12, 25, 8, 30]))
    linhas = []
    for i in range(5):
        for j in range(5):
            t = trats[(i + j) % 5]
            linhas.append({"Linha": i + 1, "Coluna": j + 1, "Tratamento": t,
                           "Massa seca (g/vaso)": round(100 + ef[t] + 4 * i - 3 * j + rng.normal(0, 5), 1)})
    spec = Especificacao("DQL", "simples", [Fator("Tratamento")], linha="Linha", coluna="Coluna")
    return pd.DataFrame(linhas), spec, ["Massa seca (g/vaso)"]


def fatorial():
    rng = _rng(4)
    fontes = ["Superfosfato triplo", "Fosfato natural reativo", "Organomineral"]
    doses = [0, 50, 100, 150, 200]
    efeito_fonte = {"Superfosfato triplo": 1.0, "Fosfato natural reativo": 0.75, "Organomineral": 0.9}
    blocos = rng.normal(0, 90, 4)
    linhas = []
    for b in range(4):
        for f in fontes:
            for d in doses:
                resp = 1400 * efeito_fonte[f] * (1 - np.exp(-0.018 * d))
                linhas.append({"Bloco": b + 1, "Fonte": f, "Dose P2O5 (kg/ha)": d,
                               "Produtividade (kg/ha)": round(2600 + resp + blocos[b] + rng.normal(0, 110), 1),
                               "P foliar (g/kg)": round(2.2 + 0.006 * d * efeito_fonte[f] - 1.1e-5 * d ** 2
                                                        + rng.normal(0, 0.12), 3)})
    spec = Especificacao("DBC", "fatorial", [Fator("Fonte", "Fonte"),
                                             Fator("Dose P2O5 (kg/ha)", "Dose de P₂O₅", quantitativo=True,
                                                   unidade="kg ha⁻¹")], bloco="Bloco")
    return pd.DataFrame(linhas), spec, ["Produtividade (kg/ha)", "P foliar (g/kg)"]


def fatorial_adicional():
    rng = _rng(5)
    fontes = ["FNR", "HiPhós", "Superfosfato triplo"]
    bio = ["Sem", "Com"]
    ef = {"FNR": 8, "HiPhós": 12, "Superfosfato triplo": 16}
    blocos = rng.normal(0, 1.2, 5)
    linhas = []
    for b in range(5):
        for f in fontes:
            for i in bio:
                v = 30 + ef[f] + (4 if i == "Com" and f != "Superfosfato triplo" else 0.5 if i == "Com" else 0)
                linhas.append({"Bloco": b + 1, "Tratamento": f"{f} {'+ Bioinsumo' if i == 'Com' else ''}".strip(),
                               "Fonte P": f, "Bioinsumo": i,
                               "Massa seca (g/vaso)": round(v + blocos[b] + rng.normal(0, 1.6), 2),
                               "P acumulado (mg/vaso)": round(0.9 * v + blocos[b] + rng.normal(0, 1.9), 2)})
        for t, v in [("Testemunha sem P", 22), ("Testemunha P incorporado", 44)]:
            linhas.append({"Bloco": b + 1, "Tratamento": t, "Fonte P": "", "Bioinsumo": "",
                           "Massa seca (g/vaso)": round(v + blocos[b] + rng.normal(0, 1.6), 2),
                           "P acumulado (mg/vaso)": round(0.9 * v + blocos[b] + rng.normal(0, 1.9), 2)})
    spec = Especificacao("DBC", "fatorial_adicional",
                         [Fator("Fonte P", "Fonte de P"), Fator("Bioinsumo", "Bioinsumo")],
                         bloco="Bloco", tratamento="Tratamento")
    return pd.DataFrame(linhas), spec, ["Massa seca (g/vaso)", "P acumulado (mg/vaso)"]


def subdividida():
    rng = _rng(6)
    manejos = ["Plantio direto", "Preparo convencional", "Escarificação"]
    profs = ["0–10", "10–20", "20–40"]
    em = {"Plantio direto": 0.0, "Preparo convencional": -0.35, "Escarificação": -0.15}
    ep = {"0–10": 0.0, "10–20": -0.45, "20–40": -0.8}
    blocos = rng.normal(0, 0.1, 4)
    linhas = []
    for b in range(4):
        for m in manejos:
            erro_parcela = rng.normal(0, 0.12)
            for p in profs:
                inter = 0.3 if (m == "Plantio direto" and p == "0–10") else 0.0
                linhas.append({"Bloco": b + 1, "Manejo": m, "Camada (cm)": p,
                               "pH CaCl2": round(5.3 + em[m] + ep[p] + inter + blocos[b] + erro_parcela
                                                 + rng.normal(0, 0.08), 2),
                               "Carbono orgânico (g/kg)": round(18 + 6 * em[m] + 9 * ep[p] + 5 * inter
                                                                + 10 * erro_parcela + rng.normal(0, 0.9), 2)})
    spec = Especificacao("DBC", "subdividida", [Fator("Manejo", "Manejo", 1), Fator("Camada (cm)", "Camada", 2)],
                         bloco="Bloco")
    return pd.DataFrame(linhas), spec, ["pH CaCl2", "Carbono orgânico (g/kg)"]


def subsubdividida():
    rng = _rng(7)
    A = ["Crotalária", "Braquiária"]
    B = [0, 60, 120, 180]
    C = ["2025", "2026"]
    linhas = []
    for bl in range(4):
        for a in A:
            ea = rng.normal(0, 150)
            for b in B:
                eb = rng.normal(0, 120)
                for c in C:
                    v = 5200 + (250 if a == "Crotalária" else 0) + 9 * b - 0.025 * b ** 2 + (300 if c == "2026" else 0)
                    linhas.append({"Bloco": bl + 1, "Cobertura": a, "Dose N (kg/ha)": b, "Safra": c,
                                   "Produtividade (kg/ha)": round(v + ea + eb + rng.normal(0, 140), 1)})
    spec = Especificacao("DBC", "subsubdividida",
                         [Fator("Cobertura", "Planta de cobertura", 1),
                          Fator("Dose N (kg/ha)", "Dose de N", 2, quantitativo=True, unidade="kg ha⁻¹"),
                          Fator("Safra", "Safra", 3)], bloco="Bloco")
    return pd.DataFrame(linhas), spec, ["Produtividade (kg/ha)"]


def faixas():
    rng = _rng(8)
    A = ["Grade", "Escarificador", "Plantio direto"]
    B = [0, 1.5, 3.0, 4.5]
    linhas = []
    for bl in range(4):
        ea = {a: rng.normal(0, 90) for a in A}
        eb = {b: rng.normal(0, 90) for b in B}
        for a in A:
            for b in B:
                v = 3000 + {"Grade": 0, "Escarificador": 150, "Plantio direto": 260}[a] + 280 * b - 30 * b ** 2
                linhas.append({"Bloco": bl + 1, "Preparo": a, "Calcário (t/ha)": b,
                               "Produtividade (kg/ha)": round(v + ea[a] + eb[b] + rng.normal(0, 100), 1)})
    spec = Especificacao("DBC", "faixas", [Fator("Preparo", "Preparo do solo", 1),
                                           Fator("Calcário (t/ha)", "Dose de calcário", 2, quantitativo=True,
                                                 unidade="t ha⁻¹")], bloco="Bloco")
    return pd.DataFrame(linhas), spec, ["Produtividade (kg/ha)"]


EXEMPLOS = {
    ("DIC", "simples"): dic,
    ("DBC", "simples"): dbc,
    ("DQL", "simples"): dql,
    ("DBC", "fatorial"): fatorial,
    ("DBC", "fatorial_adicional"): fatorial_adicional,
    ("DBC", "subdividida"): subdividida,
    ("DBC", "subsubdividida"): subsubdividida,
    ("DBC", "faixas"): faixas,
}


def exemplo_para(base, estrutura):
    """Retorna (df, spec, respostas) — adapta o exemplo DBC para DIC quando preciso."""
    if (base, estrutura) in EXEMPLOS:
        return EXEMPLOS[(base, estrutura)]()
    df, spec, resp = EXEMPLOS[("DBC", estrutura)]() if ("DBC", estrutura) in EXEMPLOS else dic()
    if base == "DIC" and spec.bloco:
        df = df.rename(columns={spec.bloco: "Repetição"})
        spec.bloco = "Repetição"
        spec.base = "DIC"
    return df, spec, resp
