"""
Identidade visual Stat-Soil: instrumento de laboratório analógico.

* Dois temas (painel grafite / bancada bege), alternados pelo menu do Streamlit;
  um pequeno script marca <html data-tema> para que os elementos próprios
  (mostradores, teclas, etiquetas) acompanhem o tema escolhido.
* Uma família tipográfica (Archivo, larguras normal e expandida) para tudo;
  mostradores de cristal líquido (DSEG14) só para os números de destaque.
* Padronagem "horizonte do solo" tirada das logos.
"""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).resolve().parent
ASSETS = RAIZ / "assets"


@lru_cache(maxsize=None)
def img64(nome: str) -> str:
    p = ASSETS / nome
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


# ----------------------------------------------------------------------------
# Padronagens (SVG embutido)
# ----------------------------------------------------------------------------
_HORIZONTE = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='240' height='30' viewBox='0 0 240 30'>"
    "<rect width='240' height='30' fill='%231F1C19'/>"
    "<path d='M0 9 C40 3 80 15 120 9 S200 3 240 9 V30 H0Z' fill='%23F3E6C8'/>"
    "<path d='M0 11 C40 5 80 17 120 11 S200 5 240 11 V30 H0Z' fill='%23F07A22'/>"
    "<path d='M0 19 C40 24 80 14 120 19 S200 24 240 19 V30 H0Z' fill='%23F3E6C8'/>"
    "<path d='M0 21 C40 26 80 16 120 21 S200 26 240 21 V30 H0Z' fill='%23C2501E'/>"
    "<g fill='%23F07A22'><circle cx='18' cy='4' r='1.6'/><circle cx='71' cy='6' r='1.2'/>"
    "<circle cx='132' cy='4' r='1.8'/><circle cx='190' cy='3' r='1.1'/></g>"
    "<g fill='%23F3E6C8'><circle cx='46' cy='5' r='1'/><circle cx='162' cy='6' r='1.2'/></g>"
    "<g fill='%231F1C19'><circle cx='30' cy='16' r='1.3'/><circle cx='95' cy='13' r='1'/>"
    "<circle cx='150' cy='15' r='1.5'/><circle cx='214' cy='16' r='1.1'/>"
    "<circle cx='60' cy='26' r='1.4'/><circle cx='120' cy='27' r='1'/><circle cx='200' cy='26' r='1.6'/></g>"
    "</svg>")
_GRAO = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='180' height='180'>"
    "<filter id='g'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/>"
    "<feColorMatrix values='0 0 0 0 0.5  0 0 0 0 0.45  0 0 0 0 0.4  0 0 0 0.55 0'/></filter>"
    "<rect width='180' height='180' filter='url(%23g)'/></svg>")
_PONTOS = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='46' height='46'>"
    "<g fill='%23F07A22' fill-opacity='0.16'><circle cx='6' cy='8' r='2'/><circle cx='30' cy='20' r='1.4'/>"
    "<circle cx='17' cy='38' r='1.7'/></g><g fill='%23C2501E' fill-opacity='0.14'><circle cx='40' cy='40' r='1.2'/>"
    "<circle cx='22' cy='12' r='1'/></g></svg>")


def _url(svg: str) -> str:
    return 'url("data:image/svg+xml;utf8,' + svg.replace('"', "'").replace("#", "%23") + '")'


# ----------------------------------------------------------------------------
# CSS
# ----------------------------------------------------------------------------
_VARS_ESCURO = """
  --fundo:#36322D; --painel:#3E3A34; --painel-2:#47423B; --borda:#5E574C; --texto:#F3E6C8; --mudo:#B9AD96;
  --laranja:#F07A22; --ferrugem:#C2501E; --carvao:#1F1C19; --creme:#F3E6C8;
  --tecla:#4A453E; --tecla-ativa:#3A3631; --tecla-borda:#211E1A; --tecla-sombra:#1C1916; --tecla-luz:rgba(255,236,205,.10);
  --tecla-texto:#F3E6C8; --primaria-borda:#8C3A10;
  --lcd-fundo:#1C1713; --lcd-texto:#FF8B2E; --lcd-fantasma:rgba(255,139,46,.075); --lcd-brilho:0 0 7px rgba(255,139,46,.45);
  --led-ok:#8EDB6A; --led-alerta:#FF8B2E; --led-off:#2A2622; --parafuso:#2A2622;
  --cartao-sombra:0 1px 0 #24211D, 0 8px 18px rgba(0,0,0,.28); --grao-opacidade:.10;
"""
_VARS_CLARO = """
  --fundo:#E8E0CF; --painel:#F1EADB; --painel-2:#F8F3E8; --borda:#B9AD97; --texto:#2A2520; --mudo:#6B6152;
  --laranja:#D2621A; --ferrugem:#A84A14; --carvao:#1F1C19; --creme:#F3E6C8;
  --tecla:#F5EFE3; --tecla-ativa:#E2D9C6; --tecla-borda:#9C907A; --tecla-sombra:#A79A82; --tecla-luz:rgba(255,255,255,.85);
  --tecla-texto:#2A2520; --primaria-borda:#8C3A10;
  --lcd-fundo:#B9C0A1; --lcd-texto:#23271C; --lcd-fantasma:rgba(35,39,28,.075); --lcd-brilho:none;
  --led-ok:#3E8F2B; --led-alerta:#D2621A; --led-off:#BFB39C; --parafuso:#A99C84;
  --cartao-sombra:0 1px 0 #CFC4AE, 0 8px 18px rgba(60,45,25,.14); --grao-opacidade:.07;
"""

CSS = f"""
<style>
@font-face {{ font-family:'Archivo X'; src:url('app/static/fonts/archivo-var-latin.woff2') format('woff2-variations');
  font-weight:100 900; font-stretch:62% 125%; font-display:swap; }}
@font-face {{ font-family:'DSEG14'; src:url('app/static/fonts/DSEG14Classic-Regular.woff2') format('woff2');
  font-display:block; }}
:root {{ {_VARS_ESCURO} }}
@media (prefers-color-scheme: light) {{ :root:not([data-tema]) {{ {_VARS_CLARO} }} }}
html[data-tema="escuro"] {{ {_VARS_ESCURO} }}
html[data-tema="claro"] {{ {_VARS_CLARO} }}

/* ---------- base: grão de papel e largura de leitura ---------- */
.stApp::before {{ content:""; position:fixed; inset:0; pointer-events:none; z-index:0; opacity:var(--grao-opacidade);
  background-image:{_url(_GRAO)}; }}
.stMainBlockContainer {{ max-width:1480px; padding-top:1.4rem; padding-bottom:4rem; }}
header[data-testid="stHeader"] {{ background:transparent; }}
div[data-testid="stDecoration"] {{ display:none; }}
.stMarkdown p, .stCaption, label, li {{ font-feature-settings:"tnum" 1; }}
h1, h2, h3, h4 {{ font-family:'Archivo X', 'Archivo', sans-serif !important; font-stretch:115%; letter-spacing:.005em; }}
h4 {{ font-size:1.08rem !important; }}

/* ---------- cabeçalho ---------- */
.ss-topo {{ display:flex; align-items:center; gap:18px; flex-wrap:wrap; }}
.ss-selo {{ width:62px; height:62px; filter:drop-shadow(0 2px 0 rgba(0,0,0,.25)); }}
.ss-marca img {{ height:40px; display:block; }}
.ss-marca p {{ margin:6px 0 0 2px; color:var(--mudo); font-size:14px; }}
.ss-etapas {{ margin-left:auto; display:flex; gap:6px; flex-wrap:wrap; }}
.ss-etapa {{ display:flex; align-items:center; gap:7px; padding:6px 11px 5px; border-radius:4px; font-size:12.5px;
  background:var(--painel); border:1px solid var(--borda); color:var(--mudo);
  box-shadow:inset 0 1px 0 var(--tecla-luz); font-family:'Archivo X'; font-stretch:112%; font-weight:560; }}
.ss-etapa b {{ color:var(--texto); font-weight:620; }}
.ss-horizonte {{ height:30px; margin:14px 0 18px; border-radius:3px; background-image:{_url(_HORIZONTE)};
  background-size:240px 30px; box-shadow:0 1px 0 var(--tecla-luz), 0 2px 5px rgba(0,0,0,.25); }}

/* ---------- LEDs ---------- */
.ss-led {{ width:8px; height:8px; border-radius:50%; display:inline-block; flex:none; background:var(--led-off);
  box-shadow:inset 0 1px 1px rgba(0,0,0,.45); }}
.ss-led.ok {{ background:var(--led-ok); box-shadow:0 0 6px var(--led-ok), inset 0 -1px 1px rgba(0,0,0,.3); }}
.ss-led.alerta {{ background:var(--led-alerta); box-shadow:0 0 6px var(--led-alerta), inset 0 -1px 1px rgba(0,0,0,.3); }}

/* ---------- etiquetas de rotulador (barra lateral) ---------- */
.ss-dymo {{ display:inline-block; margin:18px 0 6px -2px; padding:4px 11px 3px; border-radius:2px;
  background:var(--carvao); color:#F3E6C8; font-family:'Archivo X'; font-stretch:122%; font-weight:700; font-size:11.5px;
  letter-spacing:.16em; text-transform:uppercase; transform:rotate(-.7deg);
  text-shadow:0 -1px 0 rgba(0,0,0,.8), 0 1px 0 rgba(255,255,255,.18);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.10), inset 0 -2px 3px rgba(0,0,0,.5), 0 1px 2px rgba(0,0,0,.35); }}
.ss-dymo.laranja {{ background:#B8461A; }}
section[data-testid="stSidebar"] .ss-logo {{ display:block; width:168px; margin:2px auto 4px; }}
section[data-testid="stSidebar"] label p {{ font-size:13.5px; font-weight:520; }}

/* ---------- títulos de seção ---------- */
.ss-secao {{ display:flex; align-items:center; gap:10px; margin:18px 0 8px; font-family:'Archivo X'; font-stretch:115%;
  font-weight:640; font-size:17px; color:var(--texto); }}
.ss-secao i {{ width:16px; height:13px; flex:none; border-radius:2px;
  background:linear-gradient(var(--carvao) 0 34%, var(--laranja) 34% 67%, var(--ferrugem) 67%); }}
.ss-legenda {{ font-size:13px; color:var(--mudo); margin:14px 0 6px; }}
.ss-legenda b {{ color:var(--texto); font-weight:640; }}

/* ---------- teclas (botões) ---------- */
button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-secondary"],
button[data-testid="stBaseButton-tertiary"], div[data-testid="stPopover"] > div > button {{
  font-family:'Archivo X', 'Archivo', sans-serif !important; font-stretch:112%; transition:transform .05s, box-shadow .05s; }}
button[data-testid="stBaseButton-primary"] {{ background:var(--laranja) !important; color:#1F1C19 !important;
  border:1px solid var(--primaria-borda) !important; min-height:42px;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.35), 0 3px 0 var(--primaria-borda); }}
button[data-testid="stBaseButton-primary"] p {{ font-weight:680; color:#1F1C19 !important; }}
button[data-testid="stBaseButton-primary"]:hover {{ filter:brightness(1.06); }}
button[data-testid="stBaseButton-secondary"], div[data-testid="stPopover"] > div > button {{
  background:var(--tecla) !important; color:var(--tecla-texto) !important; border:1px solid var(--tecla-borda) !important;
  box-shadow:inset 0 1px 0 var(--tecla-luz), 0 3px 0 var(--tecla-sombra); min-height:38px; }}
button[data-testid="stBaseButton-secondary"]:hover, div[data-testid="stPopover"] > div > button:hover {{
  border-color:var(--laranja) !important; }}
button[data-testid="stBaseButton-primary"]:active, button[data-testid="stBaseButton-secondary"]:active,
div[data-testid="stPopover"] > div > button:active {{ transform:translateY(2px);
  box-shadow:inset 0 1px 2px rgba(0,0,0,.3), 0 1px 0 var(--tecla-sombra) !important; }}
button:disabled {{ opacity:.45; box-shadow:none !important; }}
button p {{ white-space:normal; line-height:1.25; }}
div[data-testid="stDownloadButton"] button {{ min-width:92px; }}

/* ---------- abas como teclas de seleção com LED ---------- */
div[role="tablist"] {{ gap:7px; flex-wrap:wrap; padding-bottom:6px; }}
div[data-testid="stTab"] {{ background:var(--tecla); border:1px solid var(--tecla-borda); border-radius:4px;
  padding:7px 13px 6px !important; margin:0 0 3px 0 !important;
  box-shadow:inset 0 1px 0 var(--tecla-luz), 0 3px 0 var(--tecla-sombra); }}
div[data-testid="stTab"] p {{ font-family:'Archivo X', 'Archivo' !important; font-stretch:112%; font-weight:600;
  font-size:13.5px !important; display:flex; align-items:center; gap:8px; }}
div[data-testid="stTab"] p::before {{ content:""; width:7px; height:7px; border-radius:50%; background:var(--led-off);
  box-shadow:inset 0 1px 1px rgba(0,0,0,.45); }}
div[data-testid="stTab"][aria-selected="true"] {{ background:var(--tecla-ativa); transform:translateY(2px);
  box-shadow:inset 0 2px 4px rgba(0,0,0,.28), 0 1px 0 var(--tecla-sombra); }}
div[data-testid="stTab"][aria-selected="true"] p {{ color:var(--texto) !important; }}
div[data-testid="stTab"][aria-selected="true"] p::before {{ background:var(--laranja); box-shadow:0 0 7px var(--laranja); }}
div[data-testid="stTab"]::after, div[data-testid="stTab"]::before, .react-aria-SelectionIndicator {{ display:none !important; }}
div[data-testid="stTabs"] div[data-testid="stTabs"] div[data-testid="stTab"] {{ padding:5px 10px 4px !important; }}
div[data-testid="stTabs"] div[data-testid="stTabs"] div[data-testid="stTab"] p {{ font-size:12.5px !important; }}

/* ---------- mostradores ---------- */
.ss-mostrador {{ position:relative; background:var(--painel); border:1px solid var(--borda); border-radius:6px;
  padding:9px 12px 9px; display:flex; flex-direction:column; gap:6px; min-height:106px;
  box-shadow:inset 0 1px 0 var(--tecla-luz), 0 2px 0 var(--tecla-sombra);
  background-image:radial-gradient(circle at 7px 7px, var(--parafuso) 1.8px, transparent 2.4px),
    radial-gradient(circle at calc(100% - 7px) 7px, var(--parafuso) 1.8px, transparent 2.4px),
    radial-gradient(circle at 7px calc(100% - 7px), var(--parafuso) 1.8px, transparent 2.4px),
    radial-gradient(circle at calc(100% - 7px) calc(100% - 7px), var(--parafuso) 1.8px, transparent 2.4px); }}
.ss-rot {{ display:flex; align-items:center; gap:7px; font-size:12.5px; font-weight:600; color:var(--mudo);
  padding:0 6px; }}
.ss-lcd {{ position:relative; background:var(--lcd-fundo); border-radius:3px; padding:7px 10px 6px; text-align:right;
  font-family:'DSEG14', monospace; font-size:27px; line-height:1.05; color:var(--lcd-texto); text-shadow:var(--lcd-brilho);
  box-shadow:inset 0 2px 6px rgba(0,0,0,.45), inset 0 0 0 1px rgba(0,0,0,.25); overflow:hidden; white-space:nowrap; }}
.ss-lcd .fantasma {{ position:absolute; right:10px; top:7px; color:var(--lcd-fantasma); text-shadow:none; }}
.ss-lcd .valor {{ position:relative; }}
.ss-sub {{ font-size:12px; color:var(--mudo); padding:0 6px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}

/* ---------- figuras como cópias impressas ---------- */
div[data-testid="stImage"] img {{ background:#FFFFFF; padding:10px; border-radius:2px; box-shadow:var(--cartao-sombra); }}
.st-key-previa_fixa {{ position:sticky; top:3.6rem; }}
.st-key-barra_rapida {{ background:var(--painel); border:1px solid var(--borda); border-radius:6px; padding:8px 12px 2px;
  box-shadow:inset 0 1px 0 var(--tecla-luz); }}

/* ---------- painéis e expansores ---------- */
div[data-testid="stExpander"] details {{ border:1px solid var(--borda) !important; border-radius:6px !important;
  background:var(--painel); box-shadow:inset 0 1px 0 var(--tecla-luz); }}
div[data-testid="stExpander"] summary p {{ font-family:'Archivo X'; font-stretch:110%; font-weight:600; }}
div[data-testid="stPopoverBody"] {{ background:var(--painel-2); }}
.ss-vazio {{ display:flex; align-items:center; gap:18px; padding:22px 24px; border:1px dashed var(--borda);
  border-radius:6px; background-image:{_url(_PONTOS)}; color:var(--mudo); }}
.ss-vazio img {{ width:58px; opacity:.85; }}
.ss-vazio b {{ color:var(--texto); font-weight:640; display:block; margin-bottom:2px; }}

/* ---------- esquema da planilha ---------- */
.papel {{ display:inline-block; padding:2px 8px; margin:2px 4px 2px 0; font-size:12.5px; color:#2A2520; border-radius:2px; }}
table.esquema {{ border-collapse:collapse; font-size:13px; margin:.4rem 0 .6rem; }}
table.esquema th {{ font-weight:600; padding:4px 10px; color:#2A2520; border-top:2px solid var(--texto);
  border-bottom:1px solid var(--texto); }}
table.esquema td {{ padding:3px 10px; color:var(--texto); }}
table.esquema tr:last-child td {{ border-bottom:2px solid var(--texto); }}
[data-testid="stElementToolbar"] {{ display:none !important; }}
div[data-testid="stAlertContainer"] {{ border-radius:6px; border:1px solid var(--borda);
  box-shadow:inset 0 1px 0 var(--tecla-luz); }}
@media (prefers-reduced-motion: reduce) {{ * {{ transition:none !important; }} }}
</style>
"""

JS_TEMA = """
<script>
(function () {
  function lum(c) { const m = (c || "").match(/\\d+(\\.\\d+)?/g); if (!m) return 1;
    return (0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]) / 255; }
  function ver() { const app = document.querySelector('.stApp'); if (!app) return;
    const t = lum(getComputedStyle(app).backgroundColor) < 0.5 ? 'escuro' : 'claro';
    if (document.documentElement.dataset.tema !== t) document.documentElement.dataset.tema = t; }
  ver();
  if (!window.__ssTema) { window.__ssTema = setInterval(ver, 350); }
})();
</script>
"""


def aplicar():
    st.markdown(CSS, unsafe_allow_html=True)
    st.html(JS_TEMA, unsafe_allow_javascript=True)


# ----------------------------------------------------------------------------
# Componentes
# ----------------------------------------------------------------------------
def cabecalho(etapas: list[tuple[str, str, str]]):
    """etapas: (nome, detalhe, estado) com estado em {"ok", "alerta", ""}."""
    chips = "".join(f"<span class='ss-etapa'><span class='ss-led {e}'></span><b>{n}</b>{(' ' + d) if d else ''}</span>"
                    for n, d, e in etapas)
    st.html(f"""
<div class="ss-topo">
  <img class="ss-selo" src="{img64('logo_emblema.png')}" alt="">
  <div class="ss-marca"><img src="{img64('logo_marca.png')}" alt="Stat-Soil">
    <p>Estatística de experimentos agronômicos: da planilha à figura de publicação</p></div>
  <div class="ss-etapas">{chips}</div>
</div>
<div class="ss-horizonte" role="presentation"></div>""")


def dymo(texto: str, laranja=False):
    st.html(f"<span class='ss-dymo{' laranja' if laranja else ''}'>{texto}</span>")


def logo_lateral():
    st.html(f"<img class='ss-logo' src='{img64('logo_completo.png')}' alt='Stat-Soil'>")


def secao(texto: str):
    st.html(f"<div class='ss-secao'><i></i>{texto}</div>")


def legenda_figura(n: int, titulo: str):
    st.html(f"<div class='ss-legenda'><b>Figura {n}.</b> {titulo}</div>")


_LCD_OK = set("0123456789,.%-:/ ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz<>+")


def _lcd(valor: str) -> tuple[str, str]:
    v = str(valor).replace("−", "-").replace("–", "-").replace("—", "-").replace("±", "+")
    v = "".join(c if c in _LCD_OK else " " for c in v)
    fantasma = "".join(c if c in ",.:" else ("!" if c == " " else "~") for c in v)
    return v.replace(" ", "!"), fantasma


def mostrador(rotulo: str, valor: str, sub: str = "", led: str | None = None):
    """Mostrador numérico de cristal líquido com segmentos apagados ao fundo."""
    v, f = _lcd(valor)
    led_html = f"<span class='ss-led {led}'></span>" if led is not None else ""
    st.html(f"<div class='ss-mostrador'><div class='ss-rot'>{led_html}{rotulo}</div>"
            f"<div class='ss-lcd' aria-label='{valor}'><span class='fantasma'>{f}</span>"
            f"<span class='valor'>{v}</span></div><div class='ss-sub'>{sub}</div></div>")


def vazio(titulo: str, texto: str):
    st.html(f"<div class='ss-vazio'><img src='{img64('logo_emblema_solo.png')}' alt=''>"
            f"<div><b>{titulo}</b>{texto}</div></div>")
