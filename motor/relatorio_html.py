"""
Relatório em HTML autossuficiente (um único arquivo, figuras embutidas): abre em
qualquer navegador, tem sumário clicável e sai em PDF pelo comando Imprimir.
Mesmo conteúdo e numeração do relatório em Word (motor.relatorio_blocos).
"""
from __future__ import annotations

import base64
import html
import re

from . import figuras as fg, tabelas
from .relatorio_blocos import montar

CSS = """
:root { --tinta:#1a1a1a; --mudo:#6b6b6b; --acento:#b44a12; --linha:#d9d4ca; --fundo:#faf8f4; }
* { box-sizing:border-box; }
html { background:var(--fundo); }
body { margin:0 auto; max-width:820px; padding:44px 40px 60px; background:#fff; color:var(--tinta);
  font:400 10.5pt/1.55 FONTE, 'Helvetica Neue', Arial, sans-serif; box-shadow:0 0 0 1px var(--linha); }
header.capa { border-bottom:1pt solid var(--tinta); padding-bottom:14px; margin-bottom:18px; }
header.capa .marca { font-size:8.5pt; letter-spacing:.14em; text-transform:uppercase; color:var(--acento); font-weight:700; }
h1.titulo { font-size:21pt; line-height:1.2; margin:6px 0 4px; font-weight:700; }
header.capa .sub { color:var(--mudo); font-size:11pt; }
dl.ficha { display:grid; grid-template-columns:150px 1fr; gap:3px 14px; margin:0 0 22px; font-size:9.5pt; }
dl.ficha dt { color:var(--acento); font-weight:700; } dl.ficha dd { margin:0; }
nav { border:1px solid var(--linha); border-radius:4px; padding:10px 16px; margin:0 0 24px; font-size:9.5pt; }
nav b { display:block; font-size:8.5pt; letter-spacing:.1em; text-transform:uppercase; color:var(--mudo); margin-bottom:4px; }
nav a { color:var(--tinta); text-decoration:none; display:block; padding:1px 0; } nav a:hover { color:var(--acento); }
nav a.n2 { padding-left:16px; color:var(--mudo); }
h2 { font-size:13pt; margin:30px 0 8px; padding-top:6px; border-top:0.5pt solid var(--linha); }
h3 { font-size:11pt; margin:22px 0 6px; color:var(--acento); }
p { margin:0 0 9px; text-align:justify; hyphens:auto; }
figure { margin:18px 0 20px; text-align:center; break-inside:avoid; }
figure img { max-width:100%; height:auto; }
figcaption, .tit-tab { font-size:9.5pt; margin:6px 0; }
.tit-tab { text-align:left; margin-top:16px; }
.bloco-tab { break-inside:avoid; margin-bottom:14px; overflow-x:auto; }
table { border-collapse:collapse; margin:0 auto; font-size:9.5pt; font-variant-numeric:tabular-nums; }
table thead th { border-top:1pt solid var(--tinta); border-bottom:0.5pt solid var(--tinta); font-weight:700;
  padding:4px 10px; text-align:center; }
table tbody td { padding:3px 10px; text-align:center; }
table tbody tr:last-child td { border-bottom:1pt solid var(--tinta); }
table th:first-child, table td:first-child { text-align:left; }
.nota-tab { font-size:8.5pt; color:var(--mudo); margin:4px 0 0; text-align:left; }
footer { margin-top:34px; border-top:0.5pt solid var(--linha); padding-top:8px; font-size:8pt; color:var(--mudo); }
.imprimir { position:fixed; right:18px; top:14px; font:600 9pt FONTE, Arial, sans-serif; padding:7px 14px; border-radius:4px;
  border:1px solid var(--acento); background:var(--acento); color:#fff; cursor:pointer; }
@page { size:A4; margin:20mm 18mm; }
@media print { html { background:#fff; } body { box-shadow:none; padding:0; max-width:none; } .imprimir, nav { display:none; }
  h2, h3, .tit-tab { break-after:avoid; } }
"""


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _tabela(df, idioma, indice):
    cab, corpo = tabelas.celulas_texto(df, idioma, indice)
    e = html.escape
    return ("<table><thead><tr>" + "".join(f"<th>{e(str(c))}</th>" for c in cab) + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{e(str(c))}</td>" for c in l) + "</tr>" for l in corpo) + "</tbody></table>")


def gerar_relatorio_html(resultados, opcoes, itens_fig, tema_de, idioma="pt", fonte="Roboto", titulo=None,
                         incluir_figuras=True, com_ep=True, extras=None) -> bytes:
    pt = idioma == "pt"
    e = html.escape
    blocos = montar(resultados, opcoes, itens_fig, idioma, titulo, incluir_figuras, com_ep, extras)
    corpo, indice_nav = [], []
    for b in blocos:
        tipo = b[0]
        if tipo == "capa":
            _, tit, sub, ficha = b
            corpo.append(f"<header class='capa'><div class='marca'>Stat-Soil</div><h1 class='titulo'>{e(tit)}</h1>"
                         f"<div class='sub'>{e(sub)}</div></header><dl class='ficha'>"
                         + "".join(f"<dt>{e(k)}</dt><dd>{e(str(v))}</dd>" for k, v in ficha) + "</dl>@@NAV@@")
        elif tipo in ("h1", "h2"):
            ident = _slug(b[1])
            indice_nav.append((tipo, ident, b[1]))
            corpo.append(f"<{'h2' if tipo == 'h1' else 'h3'} id='{ident}'>{e(b[1])}</{'h2' if tipo == 'h1' else 'h3'}>")
        elif tipo == "p":
            corpo += [f"<p>{e(par.strip())}</p>" for par in str(b[1]).split("\n") if par.strip()]
        elif tipo == "tabela":
            _, df, tit, nota, ind = b
            corpo.append(f"<div class='bloco-tab'><div class='tit-tab'>{e(tit or '')}</div>{_tabela(df, idioma, ind)}"
                         + (f"<div class='nota-tab'>{e(nota)}</div>" if nota else "") + "</div>")
        elif tipo == "figura":
            _, it, leg = b
            t = tema_de(it)
            png = fg.gerar_arquivo(it.spec, {**t, "tela.dpi": 200, "tela.transparente": False}, "png", idioma)
            larg = min(float(t["tela.largura_mm"]), 165.0)
            corpo.append(f"<figure><img style='width:{larg:.0f}mm' alt='{e(leg)}' "
                         f"src='data:image/png;base64,{base64.b64encode(png).decode()}'><figcaption>{e(leg)}</figcaption></figure>")
        elif tipo == "nota":
            corpo.append(f"<footer>{e(b[1])}</footer>")
    nav = ("<nav><b>" + ("Sumário" if pt else "Contents") + "</b>"
           + "".join(f"<a class='{'n1' if t == 'h1' else 'n2'}' href='#{i}'>{e(x)}</a>" for t, i, x in indice_nav) + "</nav>")
    fam = tabelas.FONTE_OFFICE.get(fonte, fonte)
    doc = (f"<!DOCTYPE html><html lang='{'pt-BR' if pt else 'en'}'><head><meta charset='utf-8'>"
           f"<meta name='viewport' content='width=device-width, initial-scale=1'><title>{e(blocos[0][1])}</title>"
           f"<style>{CSS.replace('FONTE', repr(fam))}</style></head><body>"
           f"<button class='imprimir' onclick='window.print()'>{'Imprimir ou salvar em PDF' if pt else 'Print or save as PDF'}</button>"
           + "".join(corpo).replace("@@NAV@@", nav) + "</body></html>")
    return doc.encode("utf-8")
