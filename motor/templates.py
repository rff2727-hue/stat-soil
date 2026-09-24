"""
Modelos de planilha (templates) para cada delineamento.

Formato exigido: "longo" (tidy) — uma linha por unidade experimental
(ou por subparcela), uma coluna por fator/bloco e uma por variável-resposta.
"""
from __future__ import annotations

import io

import pandas as pd

from .exemplos import exemplo_para
from .modelo import BASES, ESTRUTURAS

CORES = {
    "id": ("#EDEDED", "Identificação (opcional, ignorada na análise)"),
    "bloco": ("#E4D5C7", "Bloco / repetição"),
    "lincol": ("#E4D5C7", "Linha / coluna (quadrado latino)"),
    "trat": ("#F3E3C3", "Nome do tratamento (fatorial + adicional)"),
    "fator1": ("#D6E6F2", "Fator na parcela"),
    "fator2": ("#D8EBD9", "Fator na subparcela"),
    "fator3": ("#E7DCEE", "Fator na sub-subparcela"),
    "resp": ("#FFFFFF", "Variável-resposta (numérica)"),
}


def papeis(spec, respostas):
    """Mapa coluna -> papel, para colorir o modelo e o esquema da interface."""
    out = {}
    if spec.bloco:
        out[spec.bloco] = "bloco"
    if spec.linha:
        out[spec.linha] = "lincol"
    if spec.coluna:
        out[spec.coluna] = "lincol"
    if spec.tratamento:
        out[spec.tratamento] = "trat"
    for f in spec.fatores:
        out[f.coluna] = f"fator{f.estrato}"
    for r in respostas:
        out[r] = "resp"
    return out


def instrucoes(base, estrutura):
    gerais = [
        "Use apenas a primeira aba da planilha; a linha 1 deve conter os nomes das colunas.",
        "Formato longo: cada linha é uma unidade experimental (parcela, vaso ou subparcela). Não use células mescladas, "
        "linhas de totais, médias ou linhas em branco no meio dos dados.",
        "Uma coluna para cada fator, uma para bloco/repetição e uma para cada variável-resposta. Você pode ter quantas "
        "variáveis-resposta quiser; escolha na plataforma quais analisar.",
        "Níveis dos fatores podem ser texto (ex.: 'Superfosfato') ou números (ex.: doses 0, 50, 100). Fatores "
        "quantitativos (doses, épocas) devem conter apenas números — assim a plataforma oferece regressão.",
        "Respostas devem ser numéricas; vírgula ou ponto decimal são aceitos. Parcelas perdidas: deixe a célula vazia "
        "(não use zero, '-' ou 'NA').",
        "A ordem em que os níveis de texto aparecem na planilha é a ordem usada em tabelas e gráficos.",
        "Colunas extras de identificação (nº de laboratório, vaso, parcela) podem ficar; basta não selecioná-las.",
        "Nomes de colunas com unidade ajudam: 'Produtividade (kg/ha)'. Nos gráficos, você pode editar o rótulo do eixo.",
    ]
    esp = {
        "simples": ["Um único fator de tratamento. Em DBC, indique a coluna de blocos."],
        "fatorial": ["Todas as combinações dos níveis dos fatores devem estar presentes (fatorial completo)."],
        "fatorial_adicional": [
            "Inclua uma coluna com o nome de cada tratamento (ex.: 'FNR + Bioinsumo', 'Testemunha').",
            "Nos tratamentos do fatorial, preencha as colunas dos fatores; nos tratamentos adicionais (testemunhas), "
            "deixe as colunas dos fatores VAZIAS — é assim que a plataforma os reconhece.",
        ],
        "subdividida": [
            "Cada linha é uma subparcela. A coluna de bloco (DBC) ou repetição (DIC) identifica a parcela junto com o fator da parcela.",
            "Em parcelas subdivididas no tempo ou no espaço (épocas, camadas de solo), a época/camada é o fator da subparcela.",
            "Dados completos são exigidos: todas as combinações bloco × parcela × subparcela devem ter valor.",
            "Em DIC, numere as repetições de 1 a r dentro de cada tratamento da parcela.",
        ],
        "subsubdividida": ["Cada linha é uma sub-subparcela; dados completos são exigidos."],
        "faixas": ["Cada linha é uma interseção das faixas; dados completos são exigidos."],
    }
    if base == "DQL":
        esp["simples"] = ["Inclua as colunas de linha e de coluna do quadrado; cada tratamento aparece uma vez por linha e por coluna."]
    return gerais, esp.get(estrutura, [])


def gerar_template(base, estrutura) -> tuple[bytes, pd.DataFrame, dict]:
    import xlsxwriter
    df, spec, resp = exemplo_para(base, estrutura)
    cols_ordem = []
    for c in [spec.bloco, spec.linha, spec.coluna, spec.tratamento] + [f.coluna for f in spec.fatores] + resp:
        if c and c not in cols_ordem:
            cols_ordem.append(c)
    df = df[cols_ordem]
    pap = papeis(spec, resp)
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    fn = dict(font_name="Roboto", font_size=10)
    ws = wb.add_worksheet("Dados")
    for j, c in enumerate(df.columns):
        cor = CORES[pap.get(c, "resp")][0]
        ws.write(0, j, c, wb.add_format(dict(fn, bg_color=cor, bottom=1, top=1, text_wrap=True, valign="vcenter")))
        ws.write_comment(0, j, CORES[pap.get(c, "resp")][1], {"x_scale": 1.6, "y_scale": 0.6})
        ws.set_column(j, j, max(12, min(26, len(str(c)) + 3)))
    corpo = wb.add_format(fn)
    for i, row in enumerate(df.itertuples(index=False), start=1):
        for j, v in enumerate(row):
            if v == "" or v is None:
                ws.write_blank(i, j, None, corpo)
            elif isinstance(v, (int, float)):
                ws.write_number(i, j, v, corpo)
            else:
                ws.write(i, j, v, corpo)
    ws.freeze_panes(1, 0)
    ws.set_row(0, 30)
    # aba de instruções
    ins = wb.add_worksheet("LEIA-ME")
    ins.hide_gridlines(2)
    ins.set_column(0, 0, 4)
    ins.set_column(1, 1, 110)
    tit = wb.add_format(dict(fn, font_size=14, font_color="#5B3A29"))
    sub = wb.add_format(dict(fn, font_size=11, font_color="#5B3A29"))
    txt = wb.add_format(dict(fn, text_wrap=True, valign="top"))
    ins.write(0, 1, f"Modelo de planilha — {BASES[base]}, {ESTRUTURAS[estrutura].lower()}", tit)
    ins.write(1, 1, "A aba 'Dados' traz um exemplo preenchido (valores simulados). Substitua pelos seus dados mantendo a estrutura.",
              wb.add_format(dict(fn, font_color="#6B6B6B")))
    lin = 3
    gerais, esp = instrucoes(base, estrutura)
    ins.write(lin, 1, "Regras gerais", sub)
    lin += 1
    for g in gerais:
        ins.write(lin, 0, "•", txt)
        ins.write(lin, 1, g, txt)
        ins.set_row(lin, 28 if len(g) > 110 else 15)
        lin += 1
    lin += 1
    ins.write(lin, 1, "Específico deste delineamento", sub)
    lin += 1
    for g in esp:
        ins.write(lin, 0, "•", txt)
        ins.write(lin, 1, g, txt)
        ins.set_row(lin, 28 if len(g) > 110 else 15)
        lin += 1
    lin += 1
    ins.write(lin, 1, "Legenda de cores do cabeçalho", sub)
    lin += 1
    usados = sorted(set(pap.values()), key=list(CORES).index)
    for p in usados:
        ins.write(lin, 0, "", wb.add_format(dict(fn, bg_color=CORES[p][0], border=1, border_color="#BDBDBD")))
        ins.write(lin, 1, CORES[p][1], txt)
        lin += 1
    ins.activate() if False else ws.activate()
    wb.close()
    return buf.getvalue(), df, pap
