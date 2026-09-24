"""
Especificação do delineamento e preparação dos dados.
"""
from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

BASES = {
    "DIC": "Inteiramente casualizado (DIC)",
    "DBC": "Blocos casualizados (DBC)",
    "DQL": "Quadrado latino (DQL)",
}

ESTRUTURAS = {
    "simples": "Um fator",
    "fatorial": "Fatorial (2 ou 3 fatores)",
    "fatorial_adicional": "Fatorial + tratamento(s) adicional(is)",
    "subdividida": "Parcelas subdivididas (tempo ou espaço)",
    "subsubdividida": "Parcelas sub-subdivididas",
    "faixas": "Faixas (strip-plot)",
}

NOME_ESTRATO = {1: "parcela", 2: "subparcela", 3: "sub-subparcela"}
ERRO_ROTULO = {1: "Erro (a)", 2: "Erro (b)", 3: "Erro (c)"}


class ErroDelineamento(Exception):
    """Erro de validação apresentado ao usuário (mensagem em português)."""


@dataclass
class Fator:
    coluna: str
    rotulo: str | None = None
    estrato: int = 1            # 1 parcela, 2 subparcela, 3 sub-subparcela (faixas: 1 = horizontal, 2 = vertical)
    quantitativo: bool = False
    unidade: str = ""           # ex.: "kg ha⁻¹" (usado em eixos de regressão)

    def __post_init__(self):
        if not self.rotulo:
            self.rotulo = str(self.coluna)


@dataclass
class Especificacao:
    base: str = "DBC"
    estrutura: str = "simples"
    fatores: list = field(default_factory=list)
    bloco: str | None = None        # DBC: bloco | DIC: repetição (obrigatória em parcelas subdivididas)
    linha: str | None = None        # DQL
    coluna: str | None = None       # DQL
    tratamento: str | None = None   # fatorial + adicional: coluna com o nome de cada tratamento

    # ------------------------------------------------------------------
    @property
    def multiestrato(self) -> bool:
        return self.estrutura in ("subdividida", "subsubdividida", "faixas")

    @property
    def n_niveis_estrato(self) -> int:
        return max((f.estrato for f in self.fatores), default=1)

    def descricao(self, idioma="pt") -> str:
        nomes = " × ".join(f.rotulo for f in self.fatores)
        if idioma == "en":
            b = {"DIC": "completely randomized design (CRD)", "DBC": "randomized complete block design (RCBD)",
                 "DQL": "Latin square design"}[self.base]
            e = {"simples": "", "fatorial": "factorial ", "fatorial_adicional": "factorial plus additional treatment(s) ",
                 "subdividida": "split-plot ", "subsubdividida": "split-split-plot ", "faixas": "strip-plot "}[self.estrutura]
            return f"{e}{b} ({nomes})".strip()
        e = {"simples": "", "fatorial": "esquema fatorial, ", "fatorial_adicional": "esquema fatorial com tratamento(s) adicional(is), ",
             "subdividida": "parcelas subdivididas, ", "subsubdividida": "parcelas sub-subdivididas, ",
             "faixas": "faixas, "}[self.estrutura]
        return f"{BASES[self.base]} — {e}{nomes}".replace(", —", " —")

    def validar(self, df: pd.DataFrame):
        cols = set(df.columns)
        if not self.fatores:
            raise ErroDelineamento("Indique ao menos um fator (tratamento).")
        for f in self.fatores:
            if f.coluna not in cols:
                raise ErroDelineamento(f"Coluna do fator '{f.coluna}' não encontrada na planilha.")
        if len({f.coluna for f in self.fatores}) != len(self.fatores):
            raise ErroDelineamento("O mesmo fator foi indicado mais de uma vez.")
        if self.base == "DBC" and not self.bloco:
            raise ErroDelineamento("Em blocos casualizados (DBC) é preciso indicar a coluna de blocos.")
        if self.base == "DQL" and (not self.linha or not self.coluna):
            raise ErroDelineamento("No quadrado latino indique as colunas de linha e de coluna.")
        if self.multiestrato and not self.bloco:
            raise ErroDelineamento(
                "Em parcelas subdivididas e faixas é preciso indicar a coluna de blocos (DBC) "
                "ou de repetição (DIC), que identifica cada parcela.")
        if self.base == "DQL" and self.multiestrato:
            raise ErroDelineamento("Parcelas subdivididas em quadrado latino ainda não são suportadas.")
        n = len(self.fatores)
        est = self.estrutura
        if est == "simples" and n != 1:
            raise ErroDelineamento("A estrutura 'Um fator' deve ter exatamente um fator.")
        if est in ("fatorial", "fatorial_adicional") and n < 2:
            raise ErroDelineamento("Um fatorial precisa de pelo menos dois fatores.")
        if est == "fatorial_adicional" and not self.tratamento:
            raise ErroDelineamento("Indique a coluna que nomeia cada tratamento (inclusive os adicionais).")
        if est == "subdividida":
            niveis = sorted({f.estrato for f in self.fatores})
            if niveis != [1, 2]:
                raise ErroDelineamento("Em parcelas subdivididas, atribua fatores à parcela (1) e à subparcela (2).")
        if est == "subsubdividida":
            niveis = sorted({f.estrato for f in self.fatores})
            if niveis != [1, 2, 3]:
                raise ErroDelineamento("Em parcelas sub-subdivididas, atribua fatores aos níveis 1, 2 e 3.")
        if est == "faixas":
            if self.base != "DBC":
                raise ErroDelineamento("O delineamento em faixas requer blocos (DBC).")
            if n != 2 or sorted(f.estrato for f in self.fatores) != [1, 2]:
                raise ErroDelineamento("Em faixas, indique um fator na faixa horizontal (1) e outro na vertical (2).")
        if est in ("simples", "fatorial", "fatorial_adicional"):
            for f in self.fatores:
                f.estrato = 1


# ----------------------------------------------------------------------------
# Utilidades de níveis
# ----------------------------------------------------------------------------
def _parece_numero(s) -> bool:
    try:
        float(str(s).replace(",", "."))
        return True
    except ValueError:
        return False


def _num(s):
    return float(str(s).replace(",", "."))


def rotulo_nivel(v) -> str:
    """Converte valores para rótulo limpo: 1.0 -> '1', ' FNR ' -> 'FNR'."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        return str(int(v)) if float(v).is_integer() else f"{v:g}"
    return str(v).strip()


def ordenar_niveis(valores: pd.Series, quantitativo=False) -> list:
    """Numéricos em ordem crescente; texto na ordem de aparição na planilha."""
    vistos = []
    for v in valores:
        r = rotulo_nivel(v)
        if r and r not in vistos:
            vistos.append(r)
    if quantitativo or (vistos and all(_parece_numero(v) for v in vistos)):
        if all(_parece_numero(v) for v in vistos):
            return sorted(vistos, key=_num)
    return vistos


VAZIOS = {"", "-", "–", "—", "nan", "none", "na", "n/a"}


# ----------------------------------------------------------------------------
# Dados preparados
# ----------------------------------------------------------------------------
@dataclass
class DadosPreparados:
    d: pd.DataFrame                 # colunas internas: y, y_orig, F0..Fk, BL, LIN, COL, TRAT, CEL, _linha
    spec: Especificacao
    niveis: list                    # níveis de cada fator (listas de str)
    celulas: list                   # lista de tuplas (níveis) ou nomes de tratamento (fatorial+adicional)
    celulas_fatoriais: list         # tuplas das células do fatorial (fatorial+adicional) ou = celulas
    adicionais: list                # nomes dos tratamentos adicionais
    avisos: list
    balanceado: bool
    r: float                        # repetições por célula (média harmônica)

    @property
    def fatores(self):
        return self.spec.fatores

    def valores_quant(self, i) -> np.ndarray:
        return np.array([_num(v) for v in self.niveis[i]])


def preparar(df: pd.DataFrame, spec: Especificacao, variavel: str, transformacao=None) -> DadosPreparados:
    spec.validar(df)
    avisos = []
    d = pd.DataFrame(index=df.index)
    d["_linha"] = df.index + 2  # linha na planilha (cabeçalho = 1)
    y = pd.to_numeric(df[variavel].astype(str).str.replace(",", ".", regex=False).str.strip()
                      .replace({"": np.nan, "nan": np.nan, "-": np.nan}), errors="coerce")
    n_nao_num = int(y.isna().sum() - df[variavel].isna().sum())
    if n_nao_num > 0:
        avisos.append(f"{n_nao_num} valor(es) não numérico(s) em '{variavel}' foram tratados como ausentes.")
    d["y_orig"] = y
    for i, f in enumerate(spec.fatores):
        d[f"F{i}"] = df[f.coluna].map(rotulo_nivel)
        if f.quantitativo:
            ruins = [v for v in d[f"F{i}"].unique() if v and v.lower() not in VAZIOS and not _parece_numero(v)]
            if ruins:
                raise ErroDelineamento(
                    f"O fator '{f.rotulo}' foi marcado como quantitativo, mas tem níveis não numéricos: {ruins[:5]}")
    if spec.bloco:
        d["BL"] = df[spec.bloco].map(rotulo_nivel)
    if spec.base == "DQL":
        d["LIN"] = df[spec.linha].map(rotulo_nivel)
        d["COL"] = df[spec.coluna].map(rotulo_nivel)
    if spec.estrutura == "fatorial_adicional":
        d["TRAT"] = df[spec.tratamento].map(rotulo_nivel)

    # ------------------------------------------------------------------ ausentes
    n0 = len(d)
    d = d[d["y_orig"].notna()].copy()
    if len(d) < n0:
        avisos.append(f"{n0 - len(d)} observação(ões) sem valor de resposta foram excluídas.")
    for c in ["BL", "LIN", "COL"]:
        if c in d and (d[c].str.lower().isin(VAZIOS)).any():
            raise ErroDelineamento(f"Há linhas sem identificação de {'bloco/repetição' if c == 'BL' else c.lower()}.")

    # ------------------------------------------------------------------ transformação
    d["y"] = aplicar_transformacao(d["y_orig"].to_numpy(float), transformacao)
    if not np.all(np.isfinite(d["y"])):
        raise ErroDelineamento(f"A transformação '{transformacao}' gerou valores inválidos (zeros ou negativos?).")

    fk = [f"F{i}" for i in range(len(spec.fatores))]
    adicionais = []
    if spec.estrutura == "fatorial_adicional":
        vazio = d[fk].apply(lambda s: s.str.lower().isin(VAZIOS)).all(axis=1)
        parcial = d[fk].apply(lambda s: s.str.lower().isin(VAZIOS)).any(axis=1) & ~vazio
        if parcial.any():
            raise ErroDelineamento(
                "Algumas linhas têm apenas parte dos fatores preenchida. Nos tratamentos adicionais deixe "
                "todas as colunas de fatores vazias (ou '-'); nos fatoriais preencha todas.")
        d["ADIC"] = vazio
        adicionais = ordenar_niveis(d.loc[vazio, "TRAT"])
        if not adicionais:
            raise ErroDelineamento("Nenhum tratamento adicional encontrado (linhas com fatores vazios).")
        # rótulo dos tratamentos fatoriais é a combinação dos níveis
        dfat = d.loc[~vazio]
        niveis = [ordenar_niveis(dfat[c], f.quantitativo) for c, f in zip(fk, spec.fatores)]
        celulas_fat = list(itertools.product(*niveis))
        presentes = set(map(tuple, dfat[fk].to_numpy()))
        faltam = [c for c in celulas_fat if c not in presentes]
        if faltam:
            raise ErroDelineamento(f"Combinações fatoriais ausentes: {[' / '.join(c) for c in faltam[:5]]}")
        d["CEL"] = np.where(vazio, d["TRAT"], d[fk].agg(" / ".join, axis=1))
        celulas = [" / ".join(c) for c in celulas_fat] + adicionais
    else:
        for c, f in zip(fk, spec.fatores):
            if d[c].str.lower().isin(VAZIOS).any():
                raise ErroDelineamento(f"Há linhas sem nível do fator '{f.rotulo}'.")
        niveis = [ordenar_niveis(d[c], f.quantitativo) for c, f in zip(fk, spec.fatores)]
        celulas_fat = list(itertools.product(*niveis))
        presentes = set(map(tuple, d[fk].to_numpy()))
        faltam = [c for c in celulas_fat if c not in presentes]
        if faltam:
            raise ErroDelineamento(
                "Há combinações de tratamentos sem nenhuma observação (células vazias): "
                + "; ".join(" / ".join(c) for c in faltam[:6]) + (" …" if len(faltam) > 6 else ""))
        d["CEL"] = d[fk].agg(" / ".join, axis=1) if len(fk) > 1 else d[fk[0]]
        celulas = [" / ".join(c) for c in celulas_fat]

    for i, lv in enumerate(niveis):
        if len(lv) < 2:
            raise ErroDelineamento(f"O fator '{spec.fatores[i].rotulo}' tem apenas um nível.")

    # ------------------------------------------------------------------ balanceamento
    cont = d.groupby("CEL").size().reindex(celulas)
    balanceado = cont.nunique() == 1
    if spec.bloco and not spec.multiestrato:
        tab = d.groupby(["BL", "CEL"]).size()
        if (tab > 1).any() and spec.base == "DBC":
            avisos.append("Há tratamentos repetidos dentro do mesmo bloco; o modelo trata-os como repetições dentro do bloco.")
        nb = d["BL"].nunique()
        if spec.base == "DBC" and tab.unstack().notna().sum().sum() < nb * len(celulas):
            avisos.append("Blocos incompletos (parcelas perdidas): usadas médias ajustadas (mínimos quadrados) e SQ tipo III.")
    r = float(len(cont) / np.sum(1.0 / cont.to_numpy())) if (cont > 0).all() else 0.0
    if not balanceado and not spec.multiestrato:
        avisos.append("Número de repetições desigual entre tratamentos: médias ajustadas e teste de Tukey-Kramer.")

    # ------------------------------------------------------------------ multiestrato: subamostras
    if spec.multiestrato:
        chave = ["BL"] + fk
        rep = d.groupby(chave).size()
        if (rep > 1).any():
            avisos.append("Mais de uma observação por unidade experimental: os valores foram substituídos pela média "
                          "(as subamostras não são repetições verdadeiras).")
            agg = {"y": "mean", "y_orig": "mean", "_linha": "min", "CEL": "first"}
            d = d.groupby(chave, as_index=False).agg(agg)
        blocos = ordenar_niveis(d["BL"])
        esperado = set(itertools.product(blocos, *niveis))
        presentes = set(map(tuple, d[chave].to_numpy()))
        faltam = sorted(esperado - presentes)
        if faltam:
            raise ErroDelineamento(
                "Parcelas subdivididas/faixas exigem dados completos (balanceados). Faltam "
                f"{len(faltam)} unidade(s), por exemplo: "
                + "; ".join(f"bloco/rep {c[0]} – " + " / ".join(c[1:]) for c in faltam[:4])
                + ". Preencha ou estime as parcelas perdidas antes da análise.")
        balanceado = True
        r = float(len(blocos))

    d = d.reset_index(drop=True)
    return DadosPreparados(d=d, spec=spec, niveis=niveis, celulas=celulas, celulas_fatoriais=celulas_fat,
                           adicionais=adicionais, avisos=avisos, balanceado=bool(balanceado), r=r)


# ----------------------------------------------------------------------------
# Transformações
# ----------------------------------------------------------------------------
TRANSFORMACOES = {
    None: "Nenhuma",
    "log": "log(y)",
    "log1": "log(y + 1)",
    "sqrt": "√y",
    "sqrt05": "√(y + 0,5)",
    "arcsen": "arcsen √(y/100) (percentagens)",
    "arcsen01": "arcsen √y (proporções 0–1)",
    "inv": "1/y",
}


def aplicar_transformacao(y: np.ndarray, t):
    if t is None or t == "nenhuma":
        return y
    with np.errstate(all="ignore"):
        if t == "log":
            return np.log(y)
        if t == "log1":
            return np.log(y + 1)
        if t == "sqrt":
            return np.sqrt(y)
        if t == "sqrt05":
            return np.sqrt(y + 0.5)
        if t == "arcsen":
            return np.arcsin(np.sqrt(y / 100.0))
        if t == "arcsen01":
            return np.arcsin(np.sqrt(y))
        if t == "inv":
            return 1.0 / y
        if isinstance(t, str) and t.startswith("boxcox:"):
            lam = float(t.split(":")[1])
            return np.log(y) if abs(lam) < 1e-9 else (y ** lam - 1) / lam
    raise ValueError(f"Transformação desconhecida: {t}")


def rotulo_transformacao(t):
    if isinstance(t, str) and t.startswith("boxcox:"):
        return f"Box-Cox (λ = {float(t.split(':')[1]):g})"
    return TRANSFORMACOES.get(t, str(t))


def sugerir_colunas(df: pd.DataFrame) -> dict:
    """Heurística para pré-selecionar colunas pelo nome."""
    sug = {"bloco": None, "fatores": [], "respostas": [], "linha": None, "coluna": None, "tratamento": None}
    padroes_bloco = r"^(bloco|block|bl|rep|repeti|repetição|repeticao|r)$"
    for c in df.columns:
        nome = str(c).strip().lower()
        if re.match(padroes_bloco, nome) or nome.startswith("bloco") or nome.startswith("rep"):
            sug["bloco"] = sug["bloco"] or c
        elif nome in ("linha", "row"):
            sug["linha"] = c
        elif nome in ("coluna", "col", "column"):
            sug["coluna"] = c
    for c in df.columns:
        if c in (sug["bloco"], sug["linha"], sug["coluna"]):
            continue
        s = df[c]
        nome = str(c).strip().lower()
        ident = bool(re.match(r"^(n[º°o.]|nº|lab|id\b|amostra|vaso|parcela|plot|experimento|c[óo]digo|ordem|unidade)",
                              nome))
        if ident:
            continue
        num = pd.to_numeric(s.astype(str).str.replace(",", "."), errors="coerce")
        n_unicos = s.nunique(dropna=True)
        if n_unicos < 2:
            continue
        if num.notna().mean() < 0.9:          # texto
            if n_unicos <= 50:
                sug["fatores"].append(c)
            continue
        cont = s.value_counts()
        inteiro = bool(np.all(np.isclose(num.dropna(), np.round(num.dropna()))))
        equilibrado = cont.min() >= 2 and cont.max() / cont.min() <= 1.5
        if n_unicos <= 20 and equilibrado and (inteiro or n_unicos <= 8):
            sug["fatores"].append(c)
        else:
            sug["respostas"].append(c)
    for c in df.columns:
        if "trat" in str(c).lower():
            sug["tratamento"] = c
            break
    # remove fatores equivalentes (mesma partição dos dados, ex.: código e nome do tratamento)
    unicos = []
    for c in sug["fatores"]:
        eq = False
        for u in unicos:
            par = df[[c, u]].astype(str).drop_duplicates()
            if par[c].nunique() == len(par) == par[u].nunique():
                eq = True
                break
        if not eq:
            unicos.append(c)
    # camadas/épocas por último (costumam ir na subparcela)
    tempo = ("prof", "camada", "depth", "época", "epoca", "tempo", "dias", "data", "safra", "ano", "coleta")
    sug["fatores"] = sorted(unicos, key=lambda c: any(t in str(c).lower() for t in tempo))
    return sug
