"""
Relatório completo em Word: capa com a ficha da análise, resumo de todas as
variáveis, Material e Métodos e, para cada variável, texto, ANOVA, médias,
regressões, pressupostos e figuras com legenda numerada. Tabelas no padrão de
periódico (1,0 / 0,5 pt); cabeçalho e rodapé com número de página.
"""
from __future__ import annotations

import io

from . import figuras as fg, tabelas
from .relatorio_blocos import montar


def _campo(par, codigo):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    r = par.add_run()
    for tipo, texto in (("begin", None), (None, codigo), ("end", None)):
        if tipo:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), tipo)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = texto
        r._r.append(el)
    return r


def gerar_relatorio(resultados, opcoes, itens_fig, tema_de, idioma="pt", fonte="Roboto", titulo=None,
                    incluir_figuras=True, com_ep=True, extras=None):
    """resultados: lista de ResultadoVariavel; itens_fig: lista de ItemFigura (relatorio.specs_para);
    tema_de: função item -> tema resolvido."""
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Mm, Pt, RGBColor

    pt = idioma == "pt"
    blocos = montar(resultados, opcoes, itens_fig, idioma, titulo, incluir_figuras, com_ep, extras)
    doc = tabelas.novo_documento(fonte, 10)
    fn = tabelas.FONTE_OFFICE.get(fonte, fonte)
    escuro, mudo, acento = RGBColor(0x1A, 0x1A, 0x1A), RGBColor(0x6B, 0x6B, 0x6B), RGBColor(0xB4, 0x4A, 0x12)
    for nome, tam, antes, depois in (("Heading 1", 13, 16, 6), ("Heading 2", 11, 12, 4), ("Title", 20, 0, 4)):
        stl = doc.styles[nome]
        stl.font.name, stl.font.size, stl.font.bold = fn, Pt(tam), True
        stl.font.color.rgb = escuro
        stl.element.rPr.rFonts.set(qn("w:eastAsia"), fn)
        stl.element.rPr.rFonts.set(qn("w:ascii"), fn)
        stl.element.rPr.rFonts.set(qn("w:hAnsi"), fn)
        stl.paragraph_format.space_before, stl.paragraph_format.space_after = Pt(antes), Pt(depois)
        stl.paragraph_format.keep_with_next = True
    doc.styles["Normal"].paragraph_format.space_after = Pt(6)
    doc.styles["Normal"].paragraph_format.line_spacing = 1.15

    def filete(par, lado="bottom", pt_=1.0, cor="1A1A1A"):
        pPr = par._p.get_or_add_pPr()
        b = OxmlElement("w:pBdr")
        el = OxmlElement(f"w:{lado}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(int(pt_ * 8)))
        el.set(qn("w:space"), "4")
        el.set(qn("w:color"), cor)
        b.append(el)
        pPr.append(b)

    sec = doc.sections[0]
    cab = sec.header.paragraphs[0]
    r_ = cab.add_run("Stat-Soil  ·  " + (blocos[0][1]))
    r_.font.size, r_.font.color.rgb = Pt(8), mudo
    filete(cab, "bottom", 0.5, "9A9A9A")
    rod = sec.footer.paragraphs[0]
    rod.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for parte in (("Página " if pt else "Page "), "PAGE", (" de " if pt else " of "), "NUMPAGES"):
        rr = _campo(rod, parte) if parte in ("PAGE", "NUMPAGES") else rod.add_run(parte)
        rr.font.size, rr.font.color.rgb = Pt(8), mudo

    for b in blocos:
        tipo = b[0]
        if tipo == "capa":
            _, tit, sub, ficha = b
            p = doc.add_paragraph(tit, style="Title")
            filete(p, "bottom", 1.0)
            ps = doc.add_paragraph()
            rs = ps.add_run(sub)
            rs.font.size, rs.font.color.rgb = Pt(11), mudo
            tab = doc.add_table(rows=len(ficha), cols=2)
            tab.alignment = WD_TABLE_ALIGNMENT.LEFT
            for i, (k, v) in enumerate(ficha):
                c0, c1 = tab.rows[i].cells
                c0.width, c1.width = Mm(42), Mm(128)
                r0 = c0.paragraphs[0].add_run(k)
                r0.font.size, r0.font.color.rgb, r0.font.bold = Pt(9), acento, True
                r1 = c1.paragraphs[0].add_run(str(v))
                r1.font.size = Pt(9.5)
                for c in (c0, c1):
                    c.paragraphs[0].paragraph_format.space_after = Pt(2)
            doc.add_paragraph()
        elif tipo == "h1":
            doc.add_heading(b[1], level=1)
        elif tipo == "h2":
            h = doc.add_heading(b[1], level=2)
            for r in h.runs:
                r.font.color.rgb = acento
        elif tipo == "p":
            for par in str(b[1]).split("\n"):
                if par.strip():
                    p = doc.add_paragraph(par.strip())
                    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        elif tipo == "tabela":
            _, df, tit, nota, indice = b
            tabelas.adicionar_tabela(doc, df, tit, nota, idioma, fonte, indice=indice)
            doc.add_paragraph()
        elif tipo == "figura":
            _, it, leg = b
            t = tema_de(it)
            png = fg.gerar_arquivo(it.spec, {**t, "tela.dpi": 300}, "png", idioma)
            larg = min(float(t["tela.largura_mm"]), 165.0)
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.keep_with_next = True
            p.add_run().add_picture(io.BytesIO(png), width=Mm(larg))
            pl = doc.add_paragraph(leg)
            pl.alignment = WD_ALIGN_PARAGRAPH.CENTER
            pl.paragraph_format.space_after = Pt(12)
            for r in pl.runs:
                r.font.size = Pt(9)
        elif tipo == "nota":
            p = doc.add_paragraph(b[1])
            filete(p, "top", 0.5, "9A9A9A")
            for r in p.runs:
                r.font.size, r.font.color.rgb = Pt(8), mudo
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
