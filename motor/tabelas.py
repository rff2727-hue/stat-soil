"""
Exportação de tabelas avulsas no padrão de periódico:
filete de 1,0 pt acima e abaixo da tabela, 0,5 pt sob o cabeçalho,
sem linhas verticais, somente o cabeçalho em negrito.

* Excel: o formato só oferece espessuras fixas — usamos "média" (≈1 pt) e
  "fina" (≈0,5 pt).
* Word (.docx): espessuras exatas (1,0 e 0,5 pt), pronto para o manuscrito.
"""
from __future__ import annotations

import io
import math

import numpy as np
import pandas as pd

# nomes de fonte no Office correspondentes às fontes da plataforma
FONTE_OFFICE = {
    "Roboto": "Roboto", "Liberation Sans": "Arial", "Liberation Serif": "Times New Roman",
    "Source Sans 3": "Source Sans 3", "IBM Plex Sans": "IBM Plex Sans", "Lato": "Lato", "Inter": "Inter",
    "Open Sans": "Open Sans",
}


def _decimais(v):
    if v is None or not np.isfinite(v) or v == 0:
        return 2
    return int(min(4, max(0, 2 - math.floor(math.log10(abs(v))))))


def _texto(v, idioma="pt", dec=None, inteiro=False):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return ""
    if isinstance(v, (bool, np.bool_)):
        return ("sim" if v else "não") if idioma == "pt" else ("yes" if v else "no")
    if isinstance(v, (int, np.integer)) or inteiro:
        try:
            return f"{int(round(float(v)))}"
        except (TypeError, ValueError):
            return str(v)
    if isinstance(v, (float, np.floating)):
        d = _decimais(v) if dec is None else dec
        s = f"{v:,.{d}f}"
        if idioma == "pt":
            s = s.replace(",", "§").replace(".", ",").replace("§", ".")
        return s.replace("-", "−")
    return str(v)


def _colunas_inteiras(df):
    out = set()
    for c in df.columns:
        if str(c).strip() in ("GL", "df", "n", "#", "Posição", "Linha na planilha"):
            out.add(c)
    return out


def _colunas_p(df):
    return {c for c in df.columns if str(c).strip() in ("p", "P", "p-valor", "Valor p") or str(c).startswith("p ")}


def _fmt_p(v, idioma):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return ""
    if isinstance(v, str):
        return v
    if v < 0.001:
        return "< 0,001" if idioma == "pt" else "< 0.001"
    s = f"{v:.3f}"
    return s.replace(".", ",") if idioma == "pt" else s


def celulas_texto(df: pd.DataFrame, idioma="pt", indice=True):
    """Converte a tabela em matriz de textos (cabeçalho + corpo)."""
    ints, ps = _colunas_inteiras(df), _colunas_p(df)
    cab = ([str(df.index.name or "")] if indice else []) + [str(c) for c in df.columns]
    corpo = []
    for idx, row in df.iterrows():
        linha = [str(idx)] if indice else []
        for c in df.columns:
            v = row[c]
            if c in ps:
                linha.append(_fmt_p(v, idioma))
            else:
                linha.append(_texto(v, idioma, inteiro=c in ints))
        corpo.append(linha)
    return cab, corpo


# ----------------------------------------------------------------------------
def tabela_xlsx(df: pd.DataFrame, titulo=None, nota=None, idioma="pt", fonte="Roboto", indice=True,
                numeros_como_texto=False) -> bytes:
    import xlsxwriter
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True, "nan_inf_to_errors": True})
    ws = wb.add_worksheet("Tabela")
    ws.hide_gridlines(2)
    fn = FONTE_OFFICE.get(fonte, fonte)
    base = dict(font_name=fn, font_size=10, valign="vcenter")
    cache = {}

    def F(**kw):
        k = tuple(sorted({**base, **kw}.items()))
        if k not in cache:
            cache[k] = wb.add_format({**base, **kw})
        return cache[k]

    lin = 0
    if titulo:
        ws.write(lin, 0, titulo, F())
        lin += 1
    cab, corpo = celulas_texto(df, idioma, indice)
    ints, ps = _colunas_inteiras(df), _colunas_p(df)
    for j, c in enumerate(cab):
        ws.write(lin, j, c, F(bold=True, top=2, bottom=1, align="left" if j == 0 else "center"))
    n = len(corpo)
    cols = list(df.columns)
    for i, linha in enumerate(corpo):
        ult = i == n - 1
        r = lin + 1 + i
        for j, txt in enumerate(linha):
            kw = dict(bottom=2 if ult else 0, align="left" if j == 0 else "center")
            jc = j - (1 if indice else 0)
            v = df.iloc[i, jc] if jc >= 0 else None
            numerico = (jc >= 0 and isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool)
                        and np.isfinite(v) and cols[jc] not in ps and not numeros_como_texto)
            if numerico:
                d = 0 if cols[jc] in ints else _decimais(float(v))
                ws.write_number(r, j, float(v), F(num_format="#,##0" + ("." + "0" * d if d else ""), **kw))
            elif txt == "":
                ws.write_blank(r, j, None, F(**kw))
            else:
                ws.write(r, j, txt, F(**kw))
    lin += 1 + n
    if nota:
        ws.write(lin, 0, nota, F(font_size=9, font_color="#555555"))
    larg = [max(len(str(c)), *(len(l[j]) for l in corpo)) if corpo else len(str(c)) for j, c in enumerate(cab)]
    for j, w in enumerate(larg):
        ws.set_column(j, j, min(max(w * 1.1 + 2, 8), 60))
    wb.close()
    return buf.getvalue()


# ----------------------------------------------------------------------------
def novo_documento(fonte="Roboto", tamanho_pt=10, paisagem=False):
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.oxml.ns import qn
    from docx.shared import Pt, Cm
    fn = FONTE_OFFICE.get(fonte, fonte)
    doc = Document()
    sec = doc.sections[0]
    if paisagem:
        sec.orientation = WD_ORIENT.LANDSCAPE
        sec.page_width, sec.page_height = sec.page_height, sec.page_width
    for m in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, m, Cm(2))
    st = doc.styles["Normal"]
    st.font.name = fn
    st.font.size = Pt(tamanho_pt)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), fn)
    return doc


def adicionar_tabela(doc, df: pd.DataFrame, titulo=None, nota=None, idioma="pt", fonte="Roboto", indice=True,
                     tamanho_pt=10):
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt

    fn = FONTE_OFFICE.get(fonte, fonte)
    sec = doc.sections[-1]
    cab, corpo = celulas_texto(df, idioma, indice)
    if titulo:
        p = doc.add_paragraph(titulo)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
    tab = doc.add_table(rows=1 + len(corpo), cols=len(cab))
    tab.alignment = WD_TABLE_ALIGNMENT.CENTER
    tab.autofit = True

    def borda(celula, **lados):
        tcPr = celula._tc.get_or_add_tcPr()
        bordas = tcPr.find(qn("w:tcBorders"))
        if bordas is None:
            bordas = OxmlElement("w:tcBorders")
            tcPr.append(bordas)
        for lado, pt in lados.items():
            el = OxmlElement(f"w:{lado}")
            if pt:
                el.set(qn("w:val"), "single")
                el.set(qn("w:sz"), str(int(round(pt * 8))))   # oitavos de ponto
                el.set(qn("w:space"), "0")
                el.set(qn("w:color"), "000000")
            else:
                el.set(qn("w:val"), "nil")
            bordas.append(el)

    # remove bordas do estilo de tabela
    tblPr = tab._tbl.tblPr
    tb = OxmlElement("w:tblBorders")
    for lado in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{lado}")
        e.set(qn("w:val"), "nil")
        tb.append(e)
    tblPr.append(tb)

    # tamanho de fonte que cabe na largura útil sem quebrar palavras
    util = sec.page_width - sec.left_margin - sec.right_margin
    maior_palavra = lambda t: max([len(w) for w in str(t).split()] or [0])
    minimos = [max([maior_palavra(c)] + [len(l[j]) for l in corpo]) + 1.5 for j, c in enumerate(cab)]
    desej = [max([len(c)] + [len(l[j]) for l in corpo]) + 2 for j, c in enumerate(cab)]
    minimos[0] = max(minimos[0], 8)
    desej[0] = max(desej[0], 12)
    tot_min, tot_des = sum(minimos), sum(desej)
    while tamanho_pt > 7 and tot_min * Pt(0.56 * tamanho_pt) > util:
        tamanho_pt -= 0.5
    cw = Pt(0.56 * tamanho_pt)          # largura média de um caractere
    if tot_min * cw > util:             # ainda não cabe: aceita quebra
        minimos = [m_ * util / (tot_min * cw) for m_ in minimos]
        tot_min = sum(minimos)

    def escrever(celula, texto, negrito=False, alinhar="center"):
        celula.text = ""
        par = celula.paragraphs[0]
        par.alignment = WD_ALIGN_PARAGRAPH.LEFT if alinhar == "left" else WD_ALIGN_PARAGRAPH.CENTER
        par.paragraph_format.space_after = Pt(1)
        par.paragraph_format.space_before = Pt(1)
        run = par.add_run(texto)
        run.bold = negrito
        run.font.name = fn
        run.font.size = Pt(tamanho_pt)

    for j, c in enumerate(cab):
        cel = tab.cell(0, j)
        escrever(cel, c, True, "left" if j == 0 else "center")
        borda(cel, top=1.0, bottom=0.5)
    n = len(corpo)
    for i, linha in enumerate(corpo):
        for j, txt in enumerate(linha):
            cel = tab.cell(i + 1, j)
            escrever(cel, txt, False, "left" if j == 0 else "center")
            if i == n - 1:
                borda(cel, bottom=1.0)
    # larguras: nenhuma palavra quebrada; o que sobra vai para as colunas que mais precisam
    tab.autofit = False
    if tot_des * cw <= util:
        larguras = [util * d_ / tot_des for d_ in desej]
    else:
        folga = util - tot_min * cw
        extra = [d_ - m_ for d_, m_ in zip(desej, minimos)]
        te = sum(extra) or 1
        larguras = [m_ * cw + folga * e_ / te for m_, e_ in zip(minimos, extra)]
    for j, larg in enumerate(larguras):
        tab.columns[j].width = int(larg)            # w:gridCol (LibreOffice/Word respeitam a grade)
        for cel in tab.columns[j].cells:
            cel.width = int(larg)
    lay = OxmlElement("w:tblLayout")
    lay.set(qn("w:type"), "fixed")
    tab._tbl.tblPr.append(lay)
    if nota:
        p = doc.add_paragraph(nota)
        p.paragraph_format.space_before = Pt(3)
        for r in p.runs:
            r.font.size = Pt(tamanho_pt - 1)
    return doc


def tabela_docx(df: pd.DataFrame, titulo=None, nota=None, idioma="pt", fonte="Roboto", indice=True,
                tamanho_pt=10, paisagem=None) -> bytes:
    cab, _ = celulas_texto(df, idioma, indice)
    doc = novo_documento(fonte, tamanho_pt, len(cab) > 7 if paisagem is None else paisagem)
    adicionar_tabela(doc, df, titulo, nota, idioma, fonte, indice, tamanho_pt)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
