"""Versão 3.0: novos tipos de gráfico, mapa de regiões clicáveis, testes de pressupostos e relatórios."""
import io
import zipfile

import numpy as np
import pandas as pd
import pytest

from motor import exemplos, figuras as fg, relatorio, relatorio_blocos, relatorio_docx, relatorio_html, tema as tm
from motor.anova import Opcoes, analisar


@pytest.fixture(scope="module")
def fatorial():
    df, spec, resp = exemplos.exemplo_para("DBC", "fatorial")
    op = Opcoes()
    rs = [analisar(df, spec, v, op) for v in resp]
    itens = [i for r in rs for i in relatorio.specs_para(r, r.variavel, None)]
    return df, rs, itens, op


def _medias(itens):
    return next(i for i in itens if i.spec.tipo == "medias")


def test_paletas_e_grupos():
    assert len(tm.PALETAS) >= 20
    nomes = [n for g in tm.GRUPOS_PALETAS.values() for n in g]
    assert set(nomes) <= set(tm.PALETAS) and len(nomes) == len(set(nomes))
    assert {"Okabe-Ito", "Viridis"} <= tm.DALTONICOS
    assert set(tm.POR_CHAVE["series.paleta"].opcoes) >= set(nomes)


@pytest.mark.parametrize("ajuste", [
    {"medias.tipo": "pirulito", "medias.ordenar": "decrescente"},
    {"medias.tipo": "violino", "stats.subtitulo": True, "stats.colchetes": "significativos"},
    {"medias.tipo": "barras", "stats.colchetes": "todos", "stats.colchete_texto": "valor de p"},
    {"medias.tipo": "pontos", "medias.ordenar": "crescente", "medias.horizontal": True},
])
def test_novos_estilos_de_medias(fatorial, ajuste):
    it = _medias(fatorial[2])
    png = fg.gerar_previa(it.spec, tm.resolver(ajuste), "pt", 60)
    assert png[:4] == b"\x89PNG"


def test_mapa_de_regioes(fatorial):
    it = _medias(fatorial[2])
    png, regs, (larg, alt) = fg.gerar_previa_mapa(it.spec, tm.resolver({"stats.subtitulo": True}), "pt", 80)
    ids = {r["id"] for r in regs}
    assert {"dados", "eixo_x", "eixo_y", "titulo_y", "estat"} <= ids
    for r in regs:
        assert 0 <= r["x"] <= 1 and 0 <= r["y"] <= 1 and r["w"] > 0 and r["h"] > 0
        assert r["x"] + r["w"] <= 1.02 and r["y"] + r["h"] <= 1.02
    assert larg > 0 and alt > 0 and png[:4] == b"\x89PNG"


def test_mapa_em_todos_os_tipos(fatorial):
    for it in fatorial[2]:
        _, regs, _ = fg.gerar_previa_mapa(it.spec, tm.resolver(), "pt", 60)
        assert any(r["id"] == "dados" for r in regs), it.id


def test_rotulos_diretos():
    df, spec, resp = exemplos.exemplo_para("DBC", "subdividida")
    r = analisar(df, spec, resp[0], Opcoes())
    for it in relatorio.specs_para(r, resp[0], None):
        if it.spec.tipo in ("grupos", "perfil", "regressao"):
            t = tm.resolver({"legenda.direta": True, "medias.tipo": "linhas"})
            assert fg.gerar_previa(it.spec, t, "pt", 60)[:4] == b"\x89PNG"


@pytest.mark.parametrize("modo,horizontal", [("valores", False), ("percentual (100%)", False), ("valores", True)])
def test_empilhado(modo, horizontal):
    v = pd.DataFrame({"P lábil": [12.0, 18, 25], "P mod. lábil": [40.0, 44, 52], "P residual": [210.0, 205, 198]},
                     index=["Controle", "SFT", "Organomineral"])
    sp = fg.SpecEmpilhado(list(v.index), list(v.columns), v, np.array([4.0, 5, 6]), "Fonte", "P (mg kg^-1)")
    t = tm.resolver({"emp.modo": modo, "medias.horizontal": horizontal, "emp.rotulos": True, "emp.total": True})
    assert fg.gerar_previa(sp, t, "pt", 60)[:4] == b"\x89PNG"
    _, regs, _ = fg.gerar_previa_mapa(sp, t, "pt", 60)
    assert {"dados", "legenda"} <= {r["id"] for r in regs}
    assert fg.gerar_arquivo(sp, t, "svg", "pt").lstrip()[:5] in (b"<?xml", b"<svg ")


def test_novos_testes_de_pressupostos(fatorial):
    nomes = " | ".join(t.nome for t in fatorial[1][0].pressupostos.testes)
    for esperado in ("Lilliefors", "D'Agostino", "Fligner", "Cochran"):
        assert esperado in nomes
    for t in fatorial[1][0].pressupostos.testes:
        if t.p is not None:
            assert 0 <= t.p <= 1


def test_efeitos_e_resumo(fatorial):
    efs = relatorio_blocos.efeitos_testados(fatorial[1][0])
    nomes = [e["nome"] for e in efs]
    assert any(e["local"] for e in efs) and any("×" in n for n in nomes)
    assert all(0 <= e["p"] <= 1 for e in efs)
    colunas, linhas = relatorio_blocos.resumo_geral(fatorial[1])
    assert len(linhas) == len(fatorial[1]) and colunas and not any(c.lower().startswith("bloco") for c in colunas)


def test_relatorio_word(fatorial):
    _, rs, itens, op = fatorial
    t = tm.resolver()
    doc = relatorio_docx.gerar_relatorio(rs, op, itens, lambda i: t, "pt")
    with zipfile.ZipFile(io.BytesIO(doc)) as z:
        xml = z.read("word/document.xml").decode("utf-8")
        nomes = z.namelist()
    assert "Resumo dos resultados" in xml and "Material e Métodos" in xml and "pressupostos" in xml
    assert any(n.startswith("word/footer") for n in nomes) and any(n.startswith("word/media/") for n in nomes)


@pytest.mark.parametrize("idioma", ["pt", "en"])
def test_relatorio_html(fatorial, idioma):
    _, rs, itens, op = fatorial
    t = tm.resolver()
    h = relatorio_html.gerar_relatorio_html(rs, op, itens, lambda i: t, idioma).decode("utf-8")
    assert h.startswith("<!DOCTYPE html>") and "data:image/png;base64," in h and "<nav>" in h
    assert h.count("<table>") >= 2 * len(rs) and "window.print()" in h
    assert ("Sumário" in h) == (idioma == "pt")
