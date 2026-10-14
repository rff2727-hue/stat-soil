"""
Identidade visual Stat-Soil: instrumento de laboratório analógico.

* Dois temas (painel grafite / bancada bege), alternados em ⋮ → Settings → Theme.
  As cores são aplicadas também em tempo de execução (``aplicar_tema``), de modo
  que a aparência não depende de o arquivo .streamlit/config.toml ter sido
  publicado junto com o código.
* Tipografia: uma família (Archivo), em largura normal no texto e expandida em
  títulos, abas e teclas; mostradores de cristal líquido (DSEG14) nos números de
  destaque. Cada fonte tem três origens, em ordem: pasta static/, jsDelivr/Google
  Fonts e fontes do sistema — nunca cai numa fonte serifada.
* Padronagem "horizonte do solo" tirada das logos.
"""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).resolve().parent
ASSETS = RAIZ / "assets"
REVISAO = "2.2.1"

# ----------------------------------------------------------------------------
# Paleta (uma fonte única para config em tempo de execução e CSS)
# ----------------------------------------------------------------------------
ESCURO = dict(fundo="#36322D", lateral="#2C2925", campo="#443F38", painel="#3E3A34", painel2="#47423B",
              borda="#5E574C", texto="#F3E6C8", mudo="#B9AD96", primaria="#F07A22", ferrugem="#C2501E")
CLARO = dict(fundo="#E8E0CF", lateral="#DDD4C1", campo="#F6F1E5", painel="#F1EADB", painel2="#F8F3E8",
             borda="#B9AD97", texto="#2A2520", mudo="#6B6152", primaria="#D2621A", ferrugem="#A84A14")

FONTE_TEXTO_URL = "Archivo:https://fonts.googleapis.com/css2?family=Archivo:ital,wght@0,100..900;1,100..900&display=swap"
FONTE_MONO_URL = "JetBrains Mono:https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@100..800&display=swap"
CDN = "https://cdn.jsdelivr.net/npm"


def aplicar_tema() -> bool:
    """Aplica o tema do Streamlit em tempo de execução (cores e, se os arquivos locais não estiverem sendo
    servidos, as fontes pela internet). Assim o visual fica certo mesmo sem o config.toml publicado."""
    from streamlit import config as cfg

    mudou = []

    def setar(chave, valor):
        try:
            if cfg.get_option(chave) != valor:
                cfg.set_option(chave, valor)
                mudou.append(chave)
        except Exception:
            pass

    for nome, p, extra in (("dark", ESCURO, dict(green="#9CCB7E", red="#E8694A", yellow="#E9C25A", blue="#93B8D6",
                                                  link="#F49A52", code="#F3C77E", hdr="#2C2925")),
                           ("light", CLARO, dict(green="#4E8A3A", red="#B8402A", yellow="#A9821A", blue="#3A6E96",
                                                 link="#A84A14", code="#8A3A10", hdr="#DDD3BF"))):
        base = f"theme.{nome}"
        for k, v in {"primaryColor": p["primaria"], "backgroundColor": p["fundo"],
                     "secondaryBackgroundColor": p["campo"], "textColor": p["texto"], "borderColor": p["borda"],
                     "dataframeBorderColor": p["borda"], "dataframeHeaderBackgroundColor": extra["hdr"],
                     "linkColor": extra["link"], "codeTextColor": extra["code"], "codeBackgroundColor": p["lateral"],
                     "greenColor": extra["green"], "redColor": extra["red"], "yellowColor": extra["yellow"],
                     "blueColor": extra["blue"], "orangeColor": p["primaria"]}.items():
            setar(f"{base}.{k}", v)
        setar(f"{base}.sidebar.backgroundColor", p["lateral"])
        setar(f"{base}.sidebar.secondaryBackgroundColor", p["campo"])
        setar(f"{base}.sidebar.borderColor", p["borda"])
    setar("theme.baseRadius", "4px")
    setar("theme.buttonRadius", "4px")
    setar("theme.showWidgetBorder", True)
    try:
        estaticos = bool(cfg.get_option("server.enableStaticServing")) and (RAIZ / "static" / "fonts").exists()
    except Exception:
        estaticos = False
    if not estaticos:   # sem a pasta static servida: fontes pelo Google Fonts
        setar("theme.font", FONTE_TEXTO_URL)
        setar("theme.headingFont", FONTE_TEXTO_URL)
        setar("theme.codeFont", FONTE_MONO_URL)
    return bool(mudou)


@lru_cache(maxsize=None)
def img64(nome: str) -> str:
    p = ASSETS / nome
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


# ----------------------------------------------------------------------------
# Padronagens (SVG embutido)
# ----------------------------------------------------------------------------
_HORIZONTE = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='240' height='26' viewBox='0 0 240 26'>"
    "<rect width='240' height='26' fill='#1F1C19'/>"
    "<path d='M0 8 C40 3 80 13 120 8 S200 3 240 8 V26 H0Z' fill='#F3E6C8'/>"
    "<path d='M0 10 C40 5 80 15 120 10 S200 5 240 10 V26 H0Z' fill='#F07A22'/>"
    "<path d='M0 16.5 C40 21 80 12 120 16.5 S200 21 240 16.5 V26 H0Z' fill='#F3E6C8'/>"
    "<path d='M0 18.5 C40 23 80 14 120 18.5 S200 23 240 18.5 V26 H0Z' fill='#C2501E'/>"
    "<g fill='#F07A22'><circle cx='18' cy='4' r='1.5'/><circle cx='71' cy='5.5' r='1.1'/>"
    "<circle cx='132' cy='3.6' r='1.7'/><circle cx='190' cy='3' r='1'/></g>"
    "<g fill='#F3E6C8'><circle cx='46' cy='4.5' r='0.9'/><circle cx='162' cy='5.5' r='1.1'/></g>"
    "<g fill='#1F1C19'><circle cx='30' cy='14' r='1.2'/><circle cx='95' cy='12' r='0.9'/>"
    "<circle cx='150' cy='13.5' r='1.4'/><circle cx='214' cy='14' r='1'/>"
    "<circle cx='60' cy='23' r='1.3'/><circle cx='120' cy='24' r='0.9'/><circle cx='200' cy='23' r='1.5'/></g>"
    "</svg>")
_GRAO = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='180' height='180'>"
    "<filter id='g'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/>"
    "<feColorMatrix values='0 0 0 0 0.5  0 0 0 0 0.45  0 0 0 0 0.4  0 0 0 0.55 0'/></filter>"
    "<rect width='180' height='180' filter='url(#g)'/></svg>")
_PONTOS = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='46' height='46'>"
    "<g fill='#F07A22' fill-opacity='0.16'><circle cx='6' cy='8' r='2'/><circle cx='30' cy='20' r='1.4'/>"
    "<circle cx='17' cy='38' r='1.7'/></g><g fill='#C2501E' fill-opacity='0.14'><circle cx='40' cy='40' r='1.2'/>"
    "<circle cx='22' cy='12' r='1'/></g></svg>")


def _url(svg: str) -> str:
    return 'url("data:image/svg+xml;utf8,' + svg.replace('"', "'").replace("#", "%23") + '")'


# ----------------------------------------------------------------------------
# CSS
# ----------------------------------------------------------------------------
def _vars(p, claro):
    if claro:
        extra = """
  --carvao:#1F1C19; --tecla:#F5EFE3; --tecla-ativa:#E2D9C6; --tecla-borda:#9C907A; --tecla-sombra:#A79A82;
  --tecla-luz:rgba(255,255,255,.85); --tecla-texto:#2A2520;
  --lcd-fundo:#B9C0A1; --lcd-texto:#20241A; --lcd-brilho:none; --lcd-fantasma:rgba(35,39,28,.075); --lcd-borda:#7E8569;
  --led-ok:#3E8F2B; --led-alerta:#D2621A; --led-off:#BFB39C; --parafuso:#A99C84;
  --cartao-sombra:0 1px 0 #CFC4AE, 0 8px 18px rgba(60,45,25,.14); --grao-opacidade:.06;"""
    else:
        extra = """
  --carvao:#1F1C19; --tecla:#4A453E; --tecla-ativa:#3A3631; --tecla-borda:#211E1A; --tecla-sombra:#1C1916;
  --tecla-luz:rgba(255,236,205,.10); --tecla-texto:#F3E6C8;
  --lcd-fundo:#1C1713; --lcd-texto:#FF8B2E; --lcd-brilho:0 0 7px rgba(255,139,46,.45); --lcd-fantasma:rgba(255,139,46,.075); --lcd-borda:#14110E;
  --led-ok:#8EDB6A; --led-alerta:#FF8B2E; --led-off:#2A2622; --parafuso:#2A2622;
  --cartao-sombra:0 1px 0 #24211D, 0 8px 18px rgba(0,0,0,.28); --grao-opacidade:.10;"""
    return (f"--fundo:{p['fundo']}; --lateral:{p['lateral']}; --campo:{p['campo']}; --painel:{p['painel']}; "
            f"--painel-2:{p['painel2']}; --borda:{p['borda']}; --texto:{p['texto']}; --mudo:{p['mudo']}; "
            f"--laranja:{p['primaria']}; --ferrugem:{p['ferrugem']}; --primaria-borda:#8C3A10;" + extra)


_VE, _VC = _vars(ESCURO, False), _vars(CLARO, True)
_TEXTO = "'Archivo', 'SS Archivo', 'Helvetica Neue', Arial, sans-serif"
_LARGO = "'SS Archivo', 'Archivo', 'Helvetica Neue', Arial, sans-serif"
_LCD = "'SS LCD', 'JetBrains Mono', ui-monospace, Menlo, Consolas, monospace"

CSS = f"""
<style>
@font-face {{ font-family:'SS Archivo'; font-weight:100 900; font-stretch:62% 125%; font-display:swap;
  src:url('app/static/fonts/archivo-var-latin.woff2') format('woff2'),
      url('{CDN}/@fontsource-variable/archivo@5.3.0/files/archivo-latin-wdth-normal.woff2') format('woff2'); }}
@font-face {{ font-family:'SS LCD'; font-display:block;
  src:url('app/static/fonts/DSEG14Classic-Regular.woff2') format('woff2'),
      url('{CDN}/dseg@0.46.0/fonts/DSEG14-Classic/DSEG14Classic-Regular.woff2') format('woff2'); }}
:root {{ --f-texto:{_TEXTO}; --f-largo:{_LARGO}; --f-lcd:{_LCD}; {_VE} }}
@media (prefers-color-scheme: light) {{ :root:not([data-tema]) {{ {_VC} }} }}
html[data-tema="escuro"] {{ {_VE} }}
html[data-tema="claro"] {{ {_VC} }}

/* ---------- base: cores e fontes independem do config.toml ---------- */
body, .stApp {{ background-color:var(--fundo) !important; color:var(--texto); }}
section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div {{ background-color:var(--lateral) !important; }}
.stApp :is(p, li, label, input, textarea, [data-baseweb="select"] div, [data-baseweb="tag"] span,
  [data-testid="stCaptionContainer"]):not([data-testid="stIconMaterial"]) {{ font-family:var(--f-texto); }}
.stApp::before {{ content:""; position:fixed; inset:0; pointer-events:none; z-index:0; opacity:var(--grao-opacidade);
  background-image:{_url(_GRAO)}; }}
.stMainBlockContainer {{ max-width:1480px; padding-top:1.4rem; padding-bottom:4rem; }}
header[data-testid="stHeader"] {{ background:transparent; }}
div[data-testid="stDecoration"] {{ display:none; }}
.stMarkdown p, .stCaption, label, li {{ font-feature-settings:"tnum" 1; }}
.stApp :is(h1, h2, h3, h4) {{ font-family:var(--f-largo) !important; font-stretch:115%; font-weight:600 !important;
  letter-spacing:.005em; }}
.stApp h4 {{ font-size:1.08rem !important; }}
strong, b {{ font-weight:600; }}
.stApp :is(input, textarea, [data-baseweb="select"] > div, [data-baseweb="base-input"],
  [data-testid="stNumberInputContainer"]) {{ background-color:var(--campo) !important; }}
.stApp :is([data-baseweb="select"] > div, [data-baseweb="base-input"], [data-testid="stNumberInputContainer"],
  [data-baseweb="textarea"]) {{ border-color:var(--borda) !important; }}
.stApp :is(input, textarea) {{ color:var(--texto) !important; }}
span[data-baseweb="tag"] {{ background-color:var(--laranja) !important; }}
span[data-baseweb="tag"] span {{ color:#1F1C19 !important; }}

/* ---------- cabeçalho ---------- */
.ss-topo {{ display:flex; align-items:center; gap:18px; flex-wrap:wrap; }}
.ss-selo {{ width:62px; height:62px; filter:drop-shadow(0 2px 0 rgba(0,0,0,.25)); }}
.ss-marca img {{ height:40px; display:block; }}
.ss-marca p {{ margin:6px 0 0 2px; color:var(--mudo); font:400 14px/1.4 var(--f-texto); }}
.ss-etapas {{ margin-left:auto; display:flex; gap:6px; flex-wrap:wrap; }}
.ss-etapa {{ display:flex; align-items:center; gap:7px; padding:6px 11px 5px; border-radius:4px;
  font:560 12.5px/1.2 var(--f-largo); font-stretch:112%; background:var(--painel); border:1px solid var(--borda);
  color:var(--mudo); box-shadow:inset 0 1px 0 var(--tecla-luz); }}
.ss-etapa b {{ color:var(--texto); font-weight:620; }}
.ss-horizonte {{ height:30px; margin:14px 0 18px; border-radius:3px; background-image:{_url(_HORIZONTE)};
  background-size:277px 30px; box-shadow:0 1px 0 var(--tecla-luz), 0 2px 5px rgba(0,0,0,.25); }}

/* ---------- LEDs ---------- */
.ss-led {{ width:8px; height:8px; border-radius:50%; display:inline-block; flex:none; background:var(--led-off);
  box-shadow:inset 0 1px 1px rgba(0,0,0,.45); }}
.ss-led.ok {{ background:var(--led-ok); box-shadow:0 0 6px var(--led-ok), inset 0 -1px 1px rgba(0,0,0,.3); }}
.ss-led.alerta {{ background:var(--led-alerta); box-shadow:0 0 6px var(--led-alerta), inset 0 -1px 1px rgba(0,0,0,.3); }}

/* ---------- etiquetas de rotulador (barra lateral) ---------- */
.ss-dymo {{ display:inline-block; margin:18px 0 6px -2px; padding:4px 11px 3px; border-radius:2px;
  background:var(--carvao); color:#F3E6C8; font:700 11.5px/1.3 var(--f-largo); font-stretch:122%;
  letter-spacing:.16em; text-transform:uppercase; transform:rotate(-.7deg);
  text-shadow:0 -1px 0 rgba(0,0,0,.8), 0 1px 0 rgba(255,255,255,.18);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.10), inset 0 -2px 3px rgba(0,0,0,.5), 0 1px 2px rgba(0,0,0,.35); }}
.ss-dymo.laranja {{ background:#B8461A; }}
section[data-testid="stSidebar"] .ss-logo {{ display:block; width:168px; margin:2px auto 4px; }}
section[data-testid="stSidebar"] label p {{ font-size:13.5px; font-weight:520; }}

/* ---------- títulos de seção e legendas ---------- */
.ss-secao {{ display:flex; align-items:center; gap:10px; margin:18px 0 8px; font:640 17px/1.3 var(--f-largo);
  font-stretch:115%; color:var(--texto); }}
.ss-secao i {{ width:16px; height:13px; flex:none; border-radius:2px;
  background:linear-gradient(var(--carvao) 0 34%, var(--laranja) 34% 67%, var(--ferrugem) 67%); }}
.ss-legenda {{ font:400 13px/1.4 var(--f-texto); color:var(--mudo); margin:14px 0 6px; }}
.ss-legenda b {{ color:var(--texto); font-weight:640; }}

/* ---------- teclas (botões) ---------- */
.stApp :is(button[data-testid^="stBaseButton"], div[data-testid="stPopover"] button) p {{
  font-family:var(--f-largo) !important; font-stretch:112%; white-space:normal; line-height:1.25; }}
button[data-testid^="stBaseButton"], div[data-testid="stPopover"] button {{ transition:transform .05s, box-shadow .05s; }}
button[data-testid="stBaseButton-primary"] {{ background:var(--laranja) !important; color:#1F1C19 !important;
  border:1px solid var(--primaria-borda) !important; min-height:42px;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.35), 0 3px 0 var(--primaria-borda); }}
button[data-testid="stBaseButton-primary"] p {{ font-weight:680 !important; color:#1F1C19 !important; }}
button[data-testid="stBaseButton-primary"]:hover {{ filter:brightness(1.06); }}
button[data-testid="stBaseButton-secondary"], div[data-testid="stPopover"] > div > button {{
  background:var(--tecla) !important; color:var(--tecla-texto) !important; border:1px solid var(--tecla-borda) !important;
  box-shadow:inset 0 1px 0 var(--tecla-luz), 0 3px 0 var(--tecla-sombra); min-height:38px; }}
button[data-testid="stBaseButton-secondary"] p, div[data-testid="stPopover"] > div > button p {{
  color:var(--tecla-texto) !important; font-weight:560; }}
button[data-testid="stBaseButton-secondary"]:hover, div[data-testid="stPopover"] > div > button:hover {{
  border-color:var(--laranja) !important; }}
button[data-testid^="stBaseButton"]:active, div[data-testid="stPopover"] > div > button:active {{ transform:translateY(2px);
  box-shadow:inset 0 1px 2px rgba(0,0,0,.3), 0 1px 0 var(--tecla-sombra) !important; }}
button:disabled {{ opacity:.45; box-shadow:none !important; }}
div[data-testid="stDownloadButton"] button {{ min-width:92px; }}

/* ---------- abas como teclas de seleção com LED ---------- */
div[role="tablist"] {{ gap:7px; flex-wrap:wrap; padding-bottom:6px; }}
div[data-testid="stTab"] {{ background:var(--tecla); border:1px solid var(--tecla-borda); border-radius:4px;
  padding:7px 13px 6px !important; margin:0 0 3px 0 !important;
  box-shadow:inset 0 1px 0 var(--tecla-luz), 0 3px 0 var(--tecla-sombra); }}
div[data-testid="stTab"] p {{ font-family:var(--f-largo) !important; font-stretch:112%; font-weight:600 !important;
  font-size:13.5px !important; display:flex; align-items:center; gap:8px; color:var(--tecla-texto) !important; }}
div[data-testid="stTab"] p::before {{ content:""; width:7px; height:7px; border-radius:50%; background:var(--led-off);
  box-shadow:inset 0 1px 1px rgba(0,0,0,.45); flex:none; }}
div[data-testid="stTab"][aria-selected="true"] {{ background:var(--tecla-ativa); transform:translateY(2px);
  box-shadow:inset 0 2px 4px rgba(0,0,0,.28), 0 1px 0 var(--tecla-sombra); }}
div[data-testid="stTab"][aria-selected="true"] p::before {{ background:var(--laranja); box-shadow:0 0 7px var(--laranja); }}
div[data-testid="stTab"]::after, div[data-testid="stTab"]::before, .react-aria-SelectionIndicator {{ display:none !important; }}
div[data-testid="stTabs"] div[data-testid="stTabs"] div[data-testid="stTab"] {{ padding:5px 10px 4px !important; }}
div[data-testid="stTabs"] div[data-testid="stTabs"] div[data-testid="stTab"] p {{ font-size:12.5px !important; }}

/* ---------- mostradores de cristal líquido ---------- */
.ss-mostrador {{ position:relative; background:var(--painel); border:1px solid var(--borda); border-radius:6px;
  padding:9px 12px 9px; display:flex; flex-direction:column; gap:6px; min-height:106px;
  box-shadow:inset 0 1px 0 var(--tecla-luz), 0 2px 0 var(--tecla-sombra);
  background-image:radial-gradient(circle at 7px 7px, var(--parafuso) 1.8px, transparent 2.4px),
    radial-gradient(circle at calc(100% - 7px) 7px, var(--parafuso) 1.8px, transparent 2.4px),
    radial-gradient(circle at 7px calc(100% - 7px), var(--parafuso) 1.8px, transparent 2.4px),
    radial-gradient(circle at calc(100% - 7px) calc(100% - 7px), var(--parafuso) 1.8px, transparent 2.4px); }}
.ss-rot {{ display:flex; align-items:center; gap:7px; font:600 12.5px/1.3 var(--f-texto); color:var(--mudo); padding:0 6px; }}
.ss-lcd {{ position:relative; background:var(--lcd-fundo); border-radius:3px; padding:7px 10px 6px; text-align:right;
  font:400 27px/1.05 var(--f-lcd); color:var(--lcd-texto); text-shadow:var(--lcd-brilho);
  box-shadow:inset 0 2px 6px rgba(0,0,0,.45), inset 0 0 0 1px var(--lcd-borda); overflow:hidden; white-space:nowrap; }}
.ss-lcd .fantasma {{ position:absolute; right:10px; top:7px; color:var(--lcd-fantasma); text-shadow:none; display:none; }}
html.ss-lcd-ok .ss-lcd .fantasma {{ display:inline; }}
.ss-lcd .valor {{ position:relative; }}
html:not(.ss-lcd-ok) .ss-lcd {{ font-size:28px; font-family:'JetBrains Mono', ui-monospace, Menlo, Consolas, monospace; }}
.ss-sub {{ font-size:12px; color:var(--mudo); padding:0 6px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}

/* ---------- figuras como cópias impressas ---------- */
div[data-testid="stImage"] img {{ background:#FFFFFF; padding:10px; border-radius:2px; box-shadow:var(--cartao-sombra); }}
.st-key-previa_fixa {{ position:sticky; top:3.6rem; }}
.st-key-barra_rapida {{ background:var(--painel); border:1px solid var(--borda); border-radius:6px; padding:8px 12px 2px;
  box-shadow:inset 0 1px 0 var(--tecla-luz); }}

/* ---------- painéis, expansores, avisos ---------- */
div[data-testid="stExpander"] details {{ border:1px solid var(--borda) !important; border-radius:6px !important;
  background:var(--painel); box-shadow:inset 0 1px 0 var(--tecla-luz); }}
div[data-testid="stExpander"] summary p {{ font-family:var(--f-largo) !important; font-stretch:110%; font-weight:600; }}
div[data-testid="stPopoverBody"] {{ background:var(--painel-2); }}
div[data-testid="stAlertContainer"] {{ border-radius:6px; border:1px solid var(--borda); box-shadow:inset 0 1px 0 var(--tecla-luz); }}
.ss-vazio {{ display:flex; align-items:center; gap:18px; padding:22px 24px; border:1px dashed var(--borda);
  border-radius:6px; background-image:{_url(_PONTOS)}; color:var(--mudo); font-family:var(--f-texto); }}
.ss-vazio img {{ width:58px; opacity:.9; }}
.ss-vazio b {{ color:var(--texto); font-weight:640; display:block; margin-bottom:2px; }}

/* ---------- esquema da planilha ---------- */
.papel {{ display:inline-block; padding:2px 8px; margin:2px 4px 2px 0; font-size:12.5px; color:#2A2520; border-radius:2px; }}
table.esquema {{ border-collapse:collapse; font:400 13px/1.4 var(--f-texto); margin:.4rem 0 .6rem; }}
table.esquema th {{ font-weight:600; padding:4px 10px; color:#2A2520; border-top:2px solid var(--texto);
  border-bottom:1px solid var(--texto); }}
table.esquema td {{ padding:3px 10px; color:var(--texto); }}
table.esquema tr:last-child td {{ border-bottom:2px solid var(--texto); }}
[data-testid="stElementToolbar"] {{ display:none !important; }}
@media (prefers-reduced-motion: reduce) {{ * {{ transition:none !important; }} }}
</style>
"""

JS_TEMA = """
<script>
(function () {
  function tema() {
    const app = document.querySelector('.stApp'); if (!app) return;
    const cs = getComputedStyle(app).colorScheme;
    let t = cs === 'dark' ? 'escuro' : (cs === 'light' ? 'claro' : null);
    if (!t) { const m = (getComputedStyle(app).color || '').match(/\\d+/g) || [0, 0, 0];
              t = (0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]) / 255 > 0.5 ? 'escuro' : 'claro'; }
    if (document.documentElement.dataset.tema !== t) document.documentElement.dataset.tema = t;
  }
  tema();
  if (!window.__ssTema) { window.__ssTema = setInterval(tema, 300); }
  // segmentos apagados do visor só aparecem se a fonte de cristal líquido carregou
  if (!window.__ssLcd && document.fonts) {
    window.__ssLcd = true;
    document.fonts.load("27px 'SS LCD'", "0123").then(function () {
      if (document.fonts.check("27px 'SS LCD'", "0123")) document.documentElement.classList.add('ss-lcd-ok');
    }).catch(function () {});
  }
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


def _versao():
    try:
        from motor import __version__
        return __version__
    except Exception:
        return ""


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
    return v, fantasma


def mostrador(rotulo: str, valor: str, sub: str = "", led: str | None = None):
    """Mostrador de cristal líquido com segmentos apagados ao fundo (quando a fonte DSEG14 carrega;
    sem ela, os dígitos aparecem numa fonte monoespaçada, sem os segmentos)."""
    v, f = _lcd(valor)
    led_html = f"<span class='ss-led {led}'></span>" if led is not None else ""
    st.html(f"<div class='ss-mostrador'><div class='ss-rot'>{led_html}{rotulo}</div>"
            f"<div class='ss-lcd' aria-label='{valor}'><span class='fantasma'>{f}</span>"
            f"<span class='valor'>{v}</span></div><div class='ss-sub'>{sub}</div></div>")


def vazio(titulo: str, texto: str):
    st.html(f"<div class='ss-vazio'><img src='{img64('logo_emblema_solo.png')}' alt=''>"
            f"<div><b>{titulo}</b>{texto}</div></div>")
