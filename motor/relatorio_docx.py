"""
Relatório completo em Word: Material e Métodos, e para cada variável o texto
de resultados, a ANOVA, as médias com letras e as figuras com legenda.
Tabelas no padrão de periódico (1,0 / 0,5 pt); figuras na largura do tema.
"""
from __future__ import annotations

import datetime as dt
import io

import numpy as np
import pandas as pd

from . import exportar, figuras as fg, tabelas, textos
from .comparacoes import METODOS, METODOS_EN


def gerar_relatorio(resultados, opcoes, itens_fig, tema_de, idioma="pt", fonte="Roboto", titulo=None,
                    incluir_figuras=True, com_ep=True, extras=None):
    """resultados: lista de ResultadoVariavel; itens_fig: lista de ItemFigura (relatorio.specs_para);
    tema_de: função id -> tema resolvido."""
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Mm, Pt, RGBColor

    pt = idioma == "pt"
    ok = [r for r in resultados if not isinstance(r, Exception)]
    if not ok:
        raise ValueError("Nenhum resultado para o relatório.")
    doc = tabelas.novo_documento(fonte, 10)
    spec = ok[0].spec
    titulo = titulo or ("Relatório de análise estatística" if pt else "Statistical analysis report")
    h = doc.add_heading(titulo, level=0)
    for r_ in h.runs:
        r_.font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)
    doc.add_paragraph(f"{spec.descricao(idioma)} · {dt.datetime.now().strftime('%d/%m/%Y')}")

    doc.add_heading("Material e Métodos — análise estatística" if pt else "Statistical analysis", level=1)
    doc.add_paragraph(textos.metodos(spec, opcoes, ok, idioma))

    n_tab, n_fig = 1, 1
    metodo_nome = (METODOS if pt else METODOS_EN)[opcoes.metodo]
    alfa_txt = f"{opcoes.alfa:g}".replace(".", ",") if pt else f"{opcoes.alfa:g}"
    for r in ok:
        doc.add_heading(r.variavel, level=1)
        doc.add_paragraph(textos.interpretar(r, idioma))
        # ANOVA
        ta = exportar._tabela_anova(r, idioma, efeito=False)
        nota = "; ".join(f"{k} = {exportar._fmt_str(v, 2, idioma)}" for k, v in r.cv.items())
        nota += (". ns: não significativo; * p < 0,05; ** p < 0,01; *** p < 0,001." if pt else
                 ". ns: not significant; * P < 0.05; ** P < 0.01; *** P < 0.001.")
        tabelas.adicionar_tabela(doc, ta, f"{'Tabela' if pt else 'Table'} {n_tab}. "
                                 + (f"Análise de variância de {r.variavel}." if pt else f"Analysis of variance of {r.variavel}."),
                                 nota, idioma, fonte)
        n_tab += 1
        doc.add_paragraph()
        # médias
        for td in r.tabelas_duplas:
            med, ep, let = td["medias"], td["ep"], td["letras"]
            dec = exportar._decimais(np.nanmean(np.abs(med.to_numpy(float))))
            tab = pd.DataFrame({b: [exportar._celula_media(med.loc[a, b], ep.loc[a, b], let.loc[a, b].replace(" ", ""),
                                                           idioma, com_ep, dec) for a in med.index]
                                for b in med.columns}, index=med.index)
            tab.index.name = f"{td['linhas']} \\ {td['colunas']}"
            nota_m = (f"Médias seguidas pela mesma letra minúscula na coluna e maiúscula na linha não diferem pelo teste "
                      f"{metodo_nome} (p < {alfa_txt})." if pt else
                      f"Means followed by the same lowercase letter in the column and uppercase letter in the row do not "
                      f"differ by {metodo_nome} test (P < {alfa_txt}).")
            tabelas.adicionar_tabela(doc, tab, f"{'Tabela' if pt else 'Table'} {n_tab}. {r.variavel}: "
                                     + (f"interação {td['linhas']} × {td['colunas']}" if pt else
                                        f"{td['linhas']} × {td['colunas']} interaction")
                                     + (" (média ± erro-padrão)." if (pt and com_ep) else "."), nota_m, idioma, fonte)
            n_tab += 1
            doc.add_paragraph()
        principais = [f for f in r.fatias if not f.condicao and f.comparacao is not None]
        usados = {i for td in r.tabelas_duplas for i in td["fatores"]}
        for fa in principais:
            if fa.fator in usados:
                continue
            sig = fa.p is not None and fa.p < r.alfa
            dec = exportar._decimais(np.nanmean(np.abs(fa.medias_orig)))
            linhas = [exportar._celula_media(fa.medias_orig[i], fa.ep_dados[i],
                                             fa.comparacao.letras[i] if sig and fa.comparacao.metodo != "dunnett" else "",
                                             idioma, com_ep, dec) for i in range(len(fa.niveis))]
            tab = pd.DataFrame({r.variavel: linhas}, index=fa.niveis)
            tab.index.name = r.spec.fatores[fa.fator].rotulo
            nota_m = ((f"Médias seguidas pela mesma letra não diferem pelo teste {metodo_nome} (p < {alfa_txt})."
                       if sig else "Efeito não significativo pelo teste F.") if pt else
                      (f"Means followed by the same letter do not differ by {metodo_nome} test (P < {alfa_txt})."
                       if sig else "Not significant by the F test."))
            tabelas.adicionar_tabela(doc, tab, f"{'Tabela' if pt else 'Table'} {n_tab}. "
                                     + (f"Médias de {r.variavel} por {tab.index.name}." if pt else
                                        f"Means of {r.variavel} by {tab.index.name}."), nota_m, idioma, fonte)
            n_tab += 1
            doc.add_paragraph()
        # figuras
        if incluir_figuras:
            for it in [i for i in itens_fig if i.variavel == r.variavel and i.spec.tipo != "diagnostico"]:
                t = tema_de(it)
                png = fg.gerar_arquivo(it.spec, {**t, "tela.dpi": 300}, "png", idioma)
                larg = min(float(t["tela.largura_mm"]), 165.0)
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.add_run().add_picture(io.BytesIO(png), width=Mm(larg))
                leg = doc.add_paragraph(f"{'Figura' if pt else 'Figure'} {n_fig}. {r.variavel} — {it.titulo}. "
                                        + ("Barras: erro-padrão da média." if pt else "Bars: standard error of the mean."))
                leg.paragraph_format.space_after = Pt(10)
                n_fig += 1
    tabs_extra = (extras or {}).get("tabelas") or []
    if tabs_extra:
        doc.add_heading("Análises complementares" if pt else "Additional analyses", level=1)
        for item in tabs_extra:
            tb = item["df"]
            tabelas.adicionar_tabela(doc, tb, f"{'Tabela' if pt else 'Table'} {n_tab}. {item.get('titulo') or ''}",
                                     item.get("nota") or "", idioma, fonte, indice=True)
            n_tab += 1
            doc.add_paragraph()
    doc.add_paragraph()
    nota = doc.add_paragraph("Relatório gerado automaticamente pela plataforma Estatística Experimental; "
                             "revise textos e legendas antes de usar." if pt else
                             "Automatically generated by the Estatística Experimental platform; review before use.")
    for r_ in nota.runs:
        r_.font.size = Pt(8)
        r_.font.color.rgb = RGBColor(0x6B, 0x6B, 0x6B)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
