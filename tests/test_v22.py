"""
v2.2: texto formatado, escalas e formatação de eixos, novos tipos de gráfico, faixas
de predição, painel com escala comum, exportação (EPS, TIFF CMYK, SVG em contornos)
e o vínculo entre curvas e modelos alternativos.
"""
import io
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from motor import exemplos as ex
from motor import figuras as fg, relatorio, tema as tm
from motor.anova import analisar
from motor.modelo import Especificacao, Fator

warnings.filterwarnings("ignore")
REF = Path(__file__).resolve().parent.parent / "exemplos" / "dados_ref.xlsx"


def _medias():
    df, s, rs = ex.dbc()
    r = analisar(df, s, rs[0])
    return [it for it in relatorio.specs_para(r) if it.spec.tipo == "medias"][0].spec


def _regressao():
    df, s, rs = ex.exemplo_para("DBC", "fatorial")
    r = analisar(df, s, rs[0])
    return [it for it in relatorio.specs_para(r) if it.spec.tipo == "regressao"][0].spec


def test_texto_rico():
    assert tm.rico("kg ha^-1") == "kg ha⁻¹"
    assert tm.rico("P_{2}O_{5}") == "P₂O₅"
    assert tm.rico("Al^{3+}") == "Al³⁺"
    assert tm.rico("\\alpha = 0,05") == "α = 0,05"
    assert tm.rico("*Crotalaria*") == "$\\mathit{Crotalaria}$"
    assert tm.rico("R$ 10 e R$ 20") == "R\\$ 10 e R\\$ 20"      # cifrões não viram fórmula
    assert tm.rico("teor **") == "teor **"
    assert tm.rico("Dose_1") == "Dose_1"                      # subscrito só com chaves


def test_formatador_fator_e_milhar():
    t = tm.resolver({"eixos.milhar": True})
    f = fg._formatador(t, -1, "pt")
    assert f(2500.0) == "2.500" and f(1234.5) == "1.234,5"
    g = fg._formatador(tm.resolver(), -1, "pt", fator=3)
    assert g(2500.0) == "2,5"


def test_novos_tipos_e_opcoes_desenham():
    sp = _medias()
    for tipo in ("meia-caixa", "meio-violino", "linhas", "barras"):
        png = fg.gerar_previa(sp, tm.resolver({"medias.tipo": tipo, "medias.rotulo_valor": True,
                                                 "medias.contorno_auto": True, "eixos.linha_media": True}), "pt", 80)
        assert png[:4] == b"\x89PNG"
    t = tm.resolver({"eixos.y_escala": "log10", "eixos.y_fator": 3,
                     "anot.faixas": [{"eixo": "y", "de": 3000, "ate": 3500, "texto": "faixa"}],
                     "anot.formas": [{"tipo": "seta", "x0": .3, "y0": .9, "x1": .2, "y1": .6, "texto": "a"},
                                     {"tipo": "elipse", "x0": .1, "y0": .1, "x1": .3, "y1": .3}],
                     "niveis.renomear": {str(sp.niveis[0]): "P_{2}O_{5} *ab*"}})
    assert fg.gerar_previa(sp, t, "pt", 80)[:4] == b"\x89PNG"


def test_obs_desligadas_nas_barras():
    sp = _medias()
    import matplotlib.pyplot as plt
    with plt.rc_context(fg.rc(tm.resolver())):
        fig, ax = plt.subplots()
        fg.desenhar_medias(ax, sp, tm.resolver({"medias.tipo": "barras", "medias.obs": False}))
        assert not ax.collections or all(len(c.get_offsets()) == 0 for c in ax.collections
                                         if c.__class__.__name__ == "PathCollection")
        plt.close(fig)


def test_faixa_predicao_mais_larga_que_confianca():
    sp = _regressao()
    c = sp.curvas[0]
    xx = np.linspace(c.x.min(), c.x.max(), 50)
    bc = fg._banda(c.modelo, xx, 0.95)
    bp = fg._banda(c.modelo, xx, 0.95, True, c.qm_erro)
    assert bc is not None and bp is not None and np.all(bp > bc)
    assert c.ajustes and c.chave is not None
    assert c.modelo.codigo in [a.codigo for a in c.ajustes]


def test_painel_mesma_escala_y():
    sp = _medias()
    itens = [(sp, tm.resolver()), (sp, tm.resolver({"medias.tipo": "barras"}))]
    comum = fg._y_comum(itens, "pt")
    assert comum[0] <= 0 and comum[1] > 3000           # barras começam no zero
    png = fg.gerar_painel(itens, 1, 2, tm.resolver({"painel.mesma_escala_y": True, "painel.ocultar_internos": True}),
                          "pt", 160)
    assert png[:4] == b"\x89PNG"


def test_exportacao_eps_cmyk_contornos():
    sp = _medias()
    t = tm.resolver({"tela.tiff_cor": "CMYK", "tela.svg_texto": "contornos", "tela.dpi": 300})
    assert fg.gerar_arquivo(sp, t, "eps")[:4] == b"%!PS"
    im = Image.open(io.BytesIO(fg.gerar_arquivo(sp, t, "tiff")))
    assert im.mode == "CMYK" and abs(im.size[0] - round(89 / 25.4 * 300)) <= 2
    svg = fg.gerar_arquivo(sp, t, "svg").decode("utf-8")
    assert "<text" not in svg                          # texto convertido em contornos
    svg2 = fg.gerar_arquivo(sp, tm.resolver(), "svg").decode("utf-8")
    assert "<text" in svg2                             # padrão: texto editável
