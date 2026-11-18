"""
Componentes interativos próprios (st.components.v2, sem instalação extra):

* figura_clicavel — a prévia da figura com regiões sensíveis ao mouse: passar o
  cursor destaca o elemento (eixo, legenda, letras…) e clicar abre os ajustes dele.
* seletor_paleta — lista de paletas com as cores à mostra; clicar escolhe.
"""

from __future__ import annotations

REVISAO = "3.0.0"   # conferida pelo app.py para descartar módulos antigos em memória

import base64
import json

import streamlit as st

try:
    from streamlit.components import v2 as _v2
    DISPONIVEL = True
except Exception:          # Streamlit antigo: a interface cai nos controles comuns
    _v2 = None
    DISPONIVEL = False

# ----------------------------------------------------------------------------
# Figura clicável
# ----------------------------------------------------------------------------
_CSS_FIG = """
.palco { position: relative; display: inline-block; max-width: 100%; line-height: 0; background: #fff;
  border-radius: 2px; box-shadow: 0 1px 0 rgba(0,0,0,.18), 0 10px 22px rgba(0,0,0,.22); padding: 10px; }
.palco img { display: block; max-width: 100%; height: auto; user-select: none; -webkit-user-drag: none; }
.cam { position: absolute; left: 10px; top: 10px; right: 10px; bottom: 10px; cursor: pointer; }
.reg { position: absolute; border-radius: 3px; outline: 1.5px solid transparent; cursor: pointer;
  transition: outline-color .08s, background-color .08s; }
.reg:hover { outline-color: #F07A22; background: rgba(240,122,34,.10); }
.reg.sel { outline: 2px solid #F07A22; background: rgba(240,122,34,.07); }
.reg.dados:hover, .reg.dados.sel { background: rgba(240,122,34,.035); }
.dica { position: absolute; z-index: 30; pointer-events: none; white-space: nowrap; line-height: 1.2;
  font: 600 11.5px/1.2 'Archivo', 'SS Archivo', 'Helvetica Neue', Arial, sans-serif; color: #1F1C19;
  background: #F07A22; padding: 3px 8px 3px; border-radius: 3px; box-shadow: 0 2px 0 #8C3A10; display: none; }
.centro { text-align: center; }
"""

_JS_FIG = """
export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  let raiz = parentElement.querySelector('.centro');
  if (!raiz) { raiz = document.createElement('div'); raiz.className = 'centro'; parentElement.appendChild(raiz); }
  raiz.innerHTML = '';
  if (!data || !data.img) return;
  const palco = document.createElement('div'); palco.className = 'palco';
  const img = document.createElement('img'); img.src = data.img; img.alt = data.alt || 'Prévia da figura';
  if (data.largura) img.style.width = data.largura + 'px';
  palco.appendChild(img);
  const cam = document.createElement('div'); cam.className = 'cam'; palco.appendChild(cam);
  const dica = document.createElement('div'); dica.className = 'dica'; palco.appendChild(dica);
  const enviar = (id) => setTriggerValue('clique', id + '|' + Date.now());
  cam.addEventListener('click', (e) => { if (e.target === cam) enviar('tela'); });
  const regs = (data.regioes || []).slice().sort((a, b) => b.w * b.h - a.w * a.h);
  regs.forEach((r) => {
    const d = document.createElement('div');
    d.className = 'reg ' + r.id + (r.id === data.sel ? ' sel' : '');
    d.style.left = (r.x * 100) + '%'; d.style.top = (r.y * 100) + '%';
    d.style.width = (r.w * 100) + '%'; d.style.height = (r.h * 100) + '%';
    d.setAttribute('role', 'button'); d.setAttribute('aria-label', 'Ajustar ' + r.rot); d.tabIndex = 0;
    d.addEventListener('mousemove', (e) => {
      const b = palco.getBoundingClientRect();
      dica.textContent = r.rot + ' · clique para ajustar';
      dica.style.display = 'block';
      let x = e.clientX - b.left + 12, y = e.clientY - b.top + 14;
      if (x + dica.offsetWidth > b.width - 4) x = b.width - dica.offsetWidth - 4;
      dica.style.left = x + 'px'; dica.style.top = y + 'px';
    });
    d.addEventListener('mouseleave', () => { dica.style.display = 'none'; });
    d.addEventListener('click', (e) => { e.stopPropagation(); enviar(r.id); });
    d.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); enviar(r.id); } });
    cam.appendChild(d);
  });
  raiz.appendChild(palco);
}
"""

# ----------------------------------------------------------------------------
# Seletor de paletas
# ----------------------------------------------------------------------------
_CSS_PAL = """
.grupo { font: 600 11.5px/1.3 'Archivo', 'SS Archivo', Arial, sans-serif; letter-spacing: .04em; margin: 10px 0 5px;
  color: var(--st-text-color); opacity: .7; }
.grupo:first-child { margin-top: 0; }
.grade { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 6px; }
.pal { display: flex; flex-direction: column; gap: 4px; padding: 6px 8px 7px; border-radius: 5px; cursor: pointer;
  border: 1px solid var(--st-border-color); background: var(--st-secondary-background-color); text-align: left; }
.pal:hover { border-color: #F07A22; }
.pal.sel { border-color: #F07A22; box-shadow: inset 0 0 0 1px #F07A22; }
.nome { font: 500 12px/1.2 'Archivo', 'SS Archivo', Arial, sans-serif; color: var(--st-text-color); display: flex;
  justify-content: space-between; gap: 6px; }
.selo { font-size: 10px; opacity: .65; white-space: nowrap; }
.faixa { display: flex; height: 16px; border-radius: 2px; overflow: hidden; }
.faixa i { flex: 1; }
"""

_JS_PAL = """
export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  let raiz = parentElement.querySelector('.raiz');
  if (!raiz) { raiz = document.createElement('div'); raiz.className = 'raiz'; parentElement.appendChild(raiz); }
  raiz.innerHTML = '';
  (data.grupos || []).forEach((g) => {
    const h = document.createElement('div'); h.className = 'grupo'; h.textContent = g.nome; raiz.appendChild(h);
    const grade = document.createElement('div'); grade.className = 'grade';
    g.paletas.forEach((p) => {
      const b = document.createElement('button'); b.type = 'button';
      b.className = 'pal' + (p.nome === data.sel ? ' sel' : '');
      b.setAttribute('aria-pressed', p.nome === data.sel ? 'true' : 'false');
      const n = document.createElement('div'); n.className = 'nome';
      const s1 = document.createElement('span'); s1.textContent = p.nome; n.appendChild(s1);
      if (p.selo) { const s2 = document.createElement('span'); s2.className = 'selo'; s2.textContent = p.selo; n.appendChild(s2); }
      const f = document.createElement('div'); f.className = 'faixa';
      p.cores.forEach((c) => { const i = document.createElement('i'); i.style.background = c; f.appendChild(i); });
      b.appendChild(n); b.appendChild(f);
      b.addEventListener('click', () => setTriggerValue('escolha', p.nome + '|' + Date.now()));
      grade.appendChild(b);
    });
    raiz.appendChild(grade);
  });
}
"""

if DISPONIVEL:
    _fig = _v2.component("statsoil_figura_clicavel", css=_CSS_FIG, js=_JS_FIG)
    _pal = _v2.component("statsoil_seletor_paleta", css=_CSS_PAL, js=_JS_PAL)


def _valor(res, nome):
    v = getattr(res, nome, None)
    if v is None and isinstance(res, dict):
        v = res.get(nome)
    return str(v).rsplit("|", 1)[0] if v else None


def figura_clicavel(png: bytes, regioes: list, selecionada=None, largura_px=None, key="fig", ao_clicar=None):
    """Mostra a figura; devolve o id da região clicada nesta execução (ou None)."""
    if not DISPONIVEL:
        st.image(png, width="content")
        return None
    dados = dict(img="data:image/png;base64," + base64.b64encode(png).decode(), regioes=regioes, sel=selecionada,
                 largura=largura_px)
    res = _fig(data=dados, key=key, on_clique_change=ao_clicar or (lambda: None))
    return _valor(res, "clique")


def seletor_paleta(grupos: list, selecionada=None, key="pal", ao_escolher=None):
    """grupos: [{nome, paletas: [{nome, cores, selo}]}]; devolve o nome escolhido nesta execução (ou None)."""
    if not DISPONIVEL:
        return None
    res = _pal(data=dict(grupos=grupos, sel=selecionada), key=key, on_escolha_change=ao_escolher or (lambda: None))
    return _valor(res, "escolha")
