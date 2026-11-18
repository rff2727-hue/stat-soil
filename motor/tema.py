"""
Sistema de temas das figuras.

Um tema é um dicionário plano de parâmetros ("grupo.parametro" → valor).
A figura final usa a sobreposição:

    PADRÃO  ←  preset  ←  tema global do usuário  ←  ajustes da figura

O esquema PARAMS descreve cada parâmetro (tipo, faixa, rótulo, aba) e é
usado tanto para validar temas carregados de JSON quanto para gerar os
controles do editor automaticamente.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field

# ----------------------------------------------------------------------------
# Fontes e paletas
# ----------------------------------------------------------------------------
FONTES = {
    "Roboto": "Roboto",
    "Arial (Liberation Sans)": "Liberation Sans",
    "Inter": "Inter",
    "Source Sans 3": "Source Sans 3",
    "IBM Plex Sans": "IBM Plex Sans",
    "Lato": "Lato",
    "Open Sans": "Open Sans",
    "Times (Liberation Serif)": "Liberation Serif",
}

PALETAS = {
    # --- seguras para daltônicos
    "Solos do Cerrado": ["#A6461E", "#2878A8", "#D29A1C", "#3E8A45", "#8A4E9E", "#E0785A", "#1F9A9A", "#9A5A14"],
    "Okabe-Ito": ["#E69F00", "#56B4E9", "#009E73", "#0072B2", "#D55E00", "#CC79A7", "#F0E442", "#000000"],
    "Tol brilhante": ["#4477AA", "#EE6677", "#228833", "#CCBB44", "#66CCEE", "#AA3377", "#BBBBBB"],
    "Tol vibrante": ["#0077BB", "#EE7733", "#009988", "#CC3311", "#33BBEE", "#EE3377", "#BBBBBB"],
    "Tol suave": ["#332288", "#88CCEE", "#44AA99", "#117733", "#999933", "#DDCC77", "#CC6677", "#882255", "#AA4499"],
    "IBM": ["#648FFF", "#785EF0", "#DC267F", "#FE6100", "#FFB000", "#000000"],
    "Viridis": ["#440154", "#46327E", "#365C8D", "#277F8E", "#1FA187", "#4AC16D", "#9FDA3A", "#FDE725"],
    "Cividis": ["#00224E", "#213D6C", "#4D556C", "#6C6E72", "#8D8878", "#B1A570", "#D8C55C", "#FEE838"],
    "Batlow": ["#001959", "#113F5F", "#22605F", "#4D734D", "#807E35", "#C0903F", "#F0A27B", "#FDB6BC"],
    "Dark2 (ColorBrewer)": ["#1B9E77", "#D95F02", "#7570B3", "#E7298A", "#66A61E", "#E6AB02", "#A6761D", "#666666"],
    "Tons de cinza": ["#1A1A1A", "#7A7A7A", "#B5B5B5", "#4A4A4A", "#9A9A9A", "#D0D0D0", "#2E2E2E", "#636363"],
    # --- de periódicos e clássicas
    "Terra suave": ["#8C3B1E", "#2E6E8E", "#C8912E", "#4F7942", "#7A5C8C", "#D46A43", "#1F3B4D", "#8A8A8A"],
    "Azul–terracota": ["#1D4E89", "#B5542C", "#5B8DB8", "#D9946C", "#0B2B4C", "#7A2E14", "#A9C4E0", "#F0C7A8"],
    "Nature (NPG)": ["#E64B35", "#4DBBD5", "#00A087", "#3C5488", "#F39B7F", "#8491B4", "#91D1C2", "#DC0000"],
    "Science (AAAS)": ["#3B4992", "#EE0000", "#008B45", "#631879", "#008280", "#BB0021", "#5F559B", "#A20056"],
    "The Lancet": ["#00468B", "#ED0000", "#42B540", "#0099B4", "#925E9F", "#FDAF91", "#AD002A", "#ADB6B6"],
    "JAMA": ["#374E55", "#DF8F44", "#00A1D5", "#B24745", "#79AF97", "#6A6599", "#80796B"],
    "Set2 (ColorBrewer)": ["#66C2A5", "#FC8D62", "#8DA0CB", "#E78AC3", "#A6D854", "#FFD92F", "#E5C494", "#B3B3B3"],
    "Clássica (tab10)": ["#1F77B4", "#FF7F0E", "#2CA02C", "#D62728", "#9467BD", "#8C564B", "#E377C2", "#7F7F7F"],
    # --- sequenciais (doses, camadas, tempo)
    "Laranjas (sequencial)": ["#FDD0A2", "#FDAE6B", "#FD8D3C", "#F16913", "#D94801", "#A63603", "#7F2704"],
    "Azuis (sequencial)": ["#C6DBEF", "#9ECAE1", "#6BAED6", "#4292C6", "#2171B5", "#08519C", "#08306B"],
    "Verdes (sequencial)": ["#C7E9C0", "#A1D99B", "#74C476", "#41AB5D", "#238B45", "#006D2C", "#00441B"],
    "Terra (sequencial)": ["#F1DDC5", "#E3BE93", "#CF9A62", "#B5763D", "#8F5527", "#693A18", "#45240D"],
}
# paletas distinguíveis nas formas mais comuns de daltonismo
DALTONICOS = {"Solos do Cerrado", "Okabe-Ito", "Tol brilhante", "Tol vibrante", "Tol suave", "IBM", "Viridis", "Cividis",
              "Batlow", "Dark2 (ColorBrewer)", "Tons de cinza", "Laranjas (sequencial)", "Azuis (sequencial)",
              "Verdes (sequencial)", "Terra (sequencial)"}
GRUPOS_PALETAS = {"Seguras para daltônicos": ["Solos do Cerrado", "Okabe-Ito", "Tol brilhante", "Tol vibrante", "Tol suave",
                                              "IBM", "Viridis", "Cividis", "Batlow", "Dark2 (ColorBrewer)", "Tons de cinza"],
                  "Periódicos e clássicas": ["Terra suave", "Azul–terracota", "Nature (NPG)", "Science (AAAS)", "The Lancet",
                                             "JAMA", "Set2 (ColorBrewer)", "Clássica (tab10)"],
                  "Sequenciais (doses, camadas)": ["Laranjas (sequencial)", "Azuis (sequencial)", "Verdes (sequencial)",
                                                   "Terra (sequencial)"]}

MARCADORES = {"círculo": "o", "quadrado": "s", "triângulo": "^", "losango": "D", "triângulo invertido": "v",
              "pentágono": "p", "hexágono": "h", "estrela": "*", "cruz (+)": "P", "xis": "X"}
ORDEM_MARCADORES = ["o", "s", "^", "D", "v", "P", "X", "h"]
ESTILOS_LINHA = {"contínua": "-", "tracejada": "--", "traço-ponto": "-.", "pontilhada": ":"}
HACHURAS = ["", "///", "\\\\\\", "xxx", "...", "---", "|||", "+++"]

POSICOES_LEGENDA = ["automática", "dentro — sup. esquerda", "dentro — sup. direita", "dentro — inf. esquerda",
                    "dentro — inf. direita", "fora — acima", "fora — direita", "fora — abaixo"]
POSICOES_EQ = ["automática", "sup. esquerda", "sup. direita", "inf. esquerda", "inf. direita", "abaixo do gráfico"]


@dataclass
class P:
    chave: str
    padrao: object
    tipo: str                 # num | int | bool | cor | escolha | texto | lista | dict
    rotulo: str
    aba: str
    opcoes: list | None = None
    minimo: float | None = None
    maximo: float | None = None
    passo: float | None = None
    ajuda: str = ""
    figuras: tuple = ()       # tipos de figura a que se aplica (vazio = todos)


ABAS = ["Tela", "Fontes", "Eixos", "Séries", "Médias", "Erros e letras", "Legenda", "Regressão", "Multivariada", "Painel"]

PARAMS = [
    # ------------------------------------------------------------------ Tela
    P("tela.largura_mm", 89.0, "num", "Largura (mm)", "Tela", minimo=30, maximo=260, passo=1,
      ajuda="89 = 1 coluna · 120 = 1,5 coluna · 183 = 2 colunas"),
    P("tela.altura_mm", 0.0, "num", "Altura (mm; 0 = automática)", "Tela", minimo=0, maximo=260, passo=1),
    P("tela.proporcao", 0.72, "num", "Proporção altura/largura (se automática)", "Tela", minimo=0.3, maximo=1.6, passo=0.02),
    P("tela.dpi", 600, "int", "Resolução PNG/TIFF (dpi)", "Tela", minimo=150, maximo=1200, passo=50),
    P("tela.fundo", "#FFFFFF", "cor", "Cor de fundo", "Tela"),
    P("tela.transparente", False, "bool", "Fundo transparente na exportação", "Tela"),
    P("tela.margem", 0.3, "num", "Margem ao redor da figura", "Tela", minimo=0, maximo=3, passo=0.1),
    P("tela.titulo", "", "texto", "Título da figura (opcional)", "Tela",
      ajuda="Aceita códigos: ^{-1} sobrescrito, _{2} subscrito, *texto* itálico, \\alpha letras gregas"),
    P("tela.svg_texto", "editável", "escolha", "Texto no SVG/EPS", "Tela", opcoes=["editável", "contornos"],
      ajuda="Editável: o texto continua texto (Illustrator/Inkscape). Contornos: vira desenho (sem depender de fontes)."),
    P("tela.tiff_cor", "RGB", "escolha", "Cores do TIFF", "Tela", opcoes=["RGB", "CMYK"],
      ajuda="Algumas gráficas e editoras pedem TIFF em CMYK (sempre com compressão LZW)."),
    # ------------------------------------------------------------------ Fontes
    P("fonte.familia", "Roboto", "escolha", "Família", "Fontes", opcoes=list(FONTES)),
    P("fonte.tamanho", 7.0, "num", "Tamanho base (pt)", "Fontes", minimo=4, maximo=24, passo=0.5),
    P("fonte.titulo_eixo", 7.0, "num", "Títulos dos eixos (pt)", "Fontes", minimo=4, maximo=28, passo=0.5),
    P("fonte.numeros", 7.0, "num", "Números dos eixos (pt)", "Fontes", minimo=4, maximo=24, passo=0.5),
    P("fonte.legenda", 6.5, "num", "Legenda (pt)", "Fontes", minimo=4, maximo=24, passo=0.5),
    P("fonte.letras", 7.0, "num", "Letras de médias (pt)", "Fontes", minimo=4, maximo=24, passo=0.5),
    P("fonte.equacao", 6.5, "num", "Equações (pt)", "Fontes", minimo=4, maximo=24, passo=0.5),
    P("fonte.peso_titulos", "normal", "escolha", "Peso dos títulos", "Fontes", opcoes=["light", "normal", "bold"]),
    P("fonte.peso_numeros", "normal", "escolha", "Peso dos números", "Fontes", opcoes=["light", "normal", "bold"]),
    P("fonte.italico_titulos", False, "bool", "Títulos dos eixos em itálico", "Fontes"),
    P("fonte.cor", "#1A1A1A", "cor", "Cor do texto", "Fontes"),
    # ------------------------------------------------------------------ Eixos
    P("eixos.espessura", 0.6, "num", "Espessura das linhas dos eixos (pt)", "Eixos", minimo=0.1, maximo=3, passo=0.05),
    P("eixos.cor", "#1A1A1A", "cor", "Cor dos eixos", "Eixos"),
    P("eixos.esquerda", True, "bool", "Eixo esquerdo", "Eixos"),
    P("eixos.inferior", True, "bool", "Eixo inferior", "Eixos"),
    P("eixos.superior", False, "bool", "Eixo superior", "Eixos"),
    P("eixos.direita", False, "bool", "Eixo direito", "Eixos"),
    P("eixos.destacar", 0.0, "num", "Afastar eixos do gráfico (pt)", "Eixos", minimo=0, maximo=12, passo=0.5,
      ajuda="Eixos destacados, estilo Nature"),
    P("eixos.marcas_direcao", "out", "escolha", "Direção das marcas", "Eixos", opcoes=["out", "in", "inout"]),
    P("eixos.marcas_comp", 2.8, "num", "Comprimento das marcas (pt)", "Eixos", minimo=0, maximo=10, passo=0.2),
    P("eixos.marcas_esp", 0.6, "num", "Espessura das marcas (pt)", "Eixos", minimo=0.1, maximo=3, passo=0.05),
    P("eixos.marcas_menores", 0, "int", "Marcas secundárias entre principais (0 = nenhuma)", "Eixos", minimo=0, maximo=9, passo=1),
    P("eixos.y_min", None, "num", "Y mínimo (vazio = automático)", "Eixos"),
    P("eixos.y_max", None, "num", "Y máximo (vazio = automático)", "Eixos"),
    P("eixos.y_passo", None, "num", "Intervalo das marcas de Y", "Eixos"),
    P("eixos.y_log", False, "bool", "Escala logarítmica em Y (log10)", "Eixos"),
    P("eixos.y_escala", "linear", "escolha", "Escala de Y", "Eixos", opcoes=["linear", "log10", "log2", "ln", "raiz quadrada"]),
    P("eixos.y_fator", 0, "int", "Dividir números de Y por 10ⁿ (n)", "Eixos", minimo=0, maximo=9, passo=1,
      ajuda="Ex.: n = 3 mostra 2,5 no lugar de 2500 e acrescenta (×10³) ao título do eixo"),
    P("eixos.y_decimais", -1, "int", "Casas decimais em Y (−1 = auto)", "Eixos", minimo=-1, maximo=6, passo=1),
    P("eixos.x_min", None, "num", "X mínimo (eixos numéricos)", "Eixos"),
    P("eixos.x_max", None, "num", "X máximo (eixos numéricos)", "Eixos"),
    P("eixos.x_passo", None, "num", "Intervalo das marcas de X (numérico)", "Eixos"),
    P("eixos.x_decimais", -1, "int", "Casas decimais em X (−1 = auto)", "Eixos", minimo=-1, maximo=6, passo=1),
    P("eixos.x_escala", "linear", "escolha", "Escala de X (eixos numéricos)", "Eixos",
      opcoes=["linear", "log10", "log2", "ln", "raiz quadrada"]),
    P("eixos.x_rotacao", 0, "int", "Rotação dos rótulos de X (graus)", "Eixos", minimo=0, maximo=90, passo=5),
    P("eixos.quebra_de", None, "num", "Quebrar eixo Y de…", "Eixos", ajuda="Eixo quebrado: valor inferior do intervalo omitido"),
    P("eixos.quebra_ate", None, "num", "…até", "Eixos", ajuda="Eixo quebrado: valor superior do intervalo omitido"),
    P("eixos.decimal", "auto", "escolha", "Separador decimal", "Eixos", opcoes=["auto", "vírgula", "ponto"]),
    P("eixos.milhar", False, "bool", "Separador de milhar nos números (2.500)", "Eixos"),
    P("eixos.linha_media", False, "bool", "Linha da média geral", "Eixos"),
    P("eixos.linha_zero", False, "bool", "Linha de referência em y = 0", "Eixos"),
    P("eixos.grade", False, "bool", "Linhas de grade (Y)", "Eixos"),
    P("eixos.grade_cor", "#E6E6E6", "cor", "Cor da grade", "Eixos"),
    P("eixos.rotulo_x", "", "texto", "Título do eixo X (vazio = automático)", "Eixos"),
    P("eixos.rotulo_y", "", "texto", "Título do eixo Y (vazio = automático)", "Eixos"),
    P("eixos.pad_titulo", 3.0, "num", "Distância título–eixo (pt)", "Eixos", minimo=0, maximo=20, passo=0.5),
    # ------------------------------------------------------------------ Séries
    P("series.paleta", "Solos do Cerrado", "escolha", "Paleta", "Séries", opcoes=list(PALETAS)),
    P("series.cor_unica", "#5B3A29", "cor", "Cor (série única)", "Séries"),
    P("series.colorir_niveis", False, "bool", "Colorir cada nível com uma cor (gráfico de um fator)", "Séries"),
    P("series.marcador_tam", 4.0, "num", "Tamanho dos marcadores das médias (pt)", "Séries", minimo=1, maximo=14, passo=0.25),
    P("series.marcador_borda", 0.5, "num", "Contorno dos marcadores (pt)", "Séries", minimo=0, maximo=3, passo=0.1),
    P("series.marcador_borda_cor", "#FFFFFF", "cor", "Cor do contorno", "Séries"),
    P("series.vazados", False, "bool", "Marcadores vazados", "Séries"),
    P("series.variar_marcador", True, "bool", "Variar o marcador entre grupos", "Séries"),
    P("series.linha_esp", 1.0, "num", "Espessura das linhas (pt)", "Séries", minimo=0.2, maximo=4, passo=0.1),
    P("series.variar_linha", True, "bool", "Variar o estilo de linha entre grupos", "Séries"),
    P("grupos.cores", {}, "dict", "Cores por grupo", "Séries"),
    P("grupos.marcadores", {}, "dict", "Marcadores por grupo", "Séries"),
    P("grupos.linhas", {}, "dict", "Estilos de linha por grupo", "Séries"),
    P("niveis.renomear", {}, "dict", "Renomear níveis", "Séries"),
    P("niveis.ordem", [], "lista", "Ordem dos níveis", "Séries"),
    P("niveis.ocultar", [], "lista", "Ocultar níveis", "Séries"),
    # ------------------------------------------------------------------ Médias
    P("medias.tipo", "pontos", "escolha", "Tipo de gráfico", "Médias",
      opcoes=["pontos", "barras", "pirulito", "box", "meia-caixa", "violino", "meio-violino", "raincloud", "beeswarm",
              "linhas"],
      ajuda="Pirulito: haste fina com ponto na média (bom para muitos tratamentos, ordenados). Meia-caixa/meio-violino: "
            "distribuição de um lado e dados do outro. Linhas: médias ligadas (gráfico de interação)."),
    P("medias.ordenar", "original", "escolha", "Ordenar tratamentos pela média", "Médias",
      opcoes=["original", "crescente", "decrescente"]),
    P("medias.horizontal", False, "bool", "Orientação horizontal", "Médias"),
    P("emp.modo", "valores", "escolha", "Barras empilhadas: escala", "Médias", opcoes=["valores", "percentual (100%)"]),
    P("emp.rotulos", True, "bool", "Barras empilhadas: valor dentro de cada segmento", "Médias"),
    P("emp.total", False, "bool", "Barras empilhadas: total acima da barra", "Médias"),
    P("medias.largura", 0.62, "num", "Largura das barras/caixas", "Médias", minimo=0.1, maximo=1, passo=0.02),
    P("medias.barra_alfa", 1.0, "num", "Opacidade do preenchimento", "Médias", minimo=0, maximo=1, passo=0.05),
    P("medias.barra_cor", "#E4D5C7", "cor", "Preenchimento das barras (série única)", "Médias"),
    P("medias.contorno_esp", 0.0, "num", "Contorno das barras/caixas (pt)", "Médias", minimo=0, maximo=3, passo=0.1),
    P("medias.contorno_cor", "#1A1A1A", "cor", "Cor do contorno", "Médias"),
    P("medias.contorno_auto", False, "bool", "Contorno automático (tom mais escuro do preenchimento)", "Médias"),
    P("medias.hachuras", False, "bool", "Hachuras por grupo (impressão P&B)", "Médias"),
    P("medias.hachura_esp", 0.6, "num", "Espessura das hachuras (pt)", "Médias", minimo=0.1, maximo=2, passo=0.05),
    P("medias.rotulo_valor", False, "bool", "Mostrar o valor de cada média (rótulo de dados)", "Médias"),
    P("medias.rotulo_decimais", -1, "int", "Casas decimais do rótulo (−1 = auto)", "Médias", minimo=-1, maximo=4, passo=1),
    P("medias.obs", True, "bool", "Mostrar observações individuais", "Médias"),
    P("medias.obs_tam", 7.0, "num", "Tamanho das observações (pt²)", "Médias", minimo=1, maximo=60, passo=1),
    P("medias.obs_alfa", 0.45, "num", "Transparência das observações", "Médias", minimo=0.05, maximo=1, passo=0.05),
    P("medias.obs_disp", 0.14, "num", "Dispersão horizontal das observações", "Médias", minimo=0, maximo=0.45, passo=0.01),
    P("medias.obs_lado", True, "bool", "Observações ao lado da média (gráfico de pontos)", "Médias"),
    P("medias.obs_cor", "série", "escolha", "Cor das observações", "Médias", opcoes=["série", "cinza", "preto"]),
    P("medias.espaco_grupos", 0.8, "num", "Largura ocupada por grupo (interações)", "Médias", minimo=0.3, maximo=1, passo=0.05),
    P("medias.conectar", False, "bool", "Ligar médias com linha (interação/perfil)", "Médias"),
    # ------------------------------------------------------------------ Erros e letras
    P("erro.tipo", "ep", "escolha", "Barra de erro", "Erros e letras", opcoes=["ep", "dp", "ic95", "nenhuma"]),
    P("erro.esp", 0.8, "num", "Espessura da barra de erro (pt)", "Erros e letras", minimo=0.1, maximo=3, passo=0.05),
    P("erro.chapeu", 0.0, "num", "Largura do traço terminal (pt)", "Erros e letras", minimo=0, maximo=8, passo=0.25),
    P("erro.so_superior", False, "bool", "Somente a metade superior", "Erros e letras"),
    P("erro.cor", "série", "escolha", "Cor da barra de erro", "Erros e letras", opcoes=["série", "preto", "cinza"]),
    P("letras.mostrar", True, "bool", "Mostrar letras", "Erros e letras"),
    P("letras.se_ns", False, "bool", "Mostrar letras mesmo sem efeito significativo (F)", "Erros e letras"),
    P("letras.posicao", "acima dos dados", "escolha", "Posição das letras", "Erros e letras",
      opcoes=["acima dos dados", "acima do erro", "topo alinhado"]),
    P("letras.distancia", 0.035, "num", "Distância das letras (fração do eixo)", "Erros e letras", minimo=0, maximo=0.2, passo=0.005),
    P("letras.italico", False, "bool", "Letras em itálico", "Erros e letras"),
    P("letras.separar", False, "bool", "Separar minúscula e maiúscula com espaço (interações)", "Erros e letras"),
    P("stats.subtitulo", False, "bool", "Resumo estatístico no topo (F, p, η²p, n)", "Erros e letras",
      ajuda="Como no ggbetweenstats: o teste que sustenta a figura aparece escrito nela"),
    P("stats.colchetes", "nenhum", "escolha", "Colchetes automáticos entre pares", "Erros e letras",
      opcoes=["nenhum", "significativos", "todos"],
      ajuda="Desenha colchetes com o valor de p de cada comparação do teste de médias (até 10 pares)"),
    P("stats.colchete_texto", "estrelas", "escolha", "Texto dos colchetes automáticos", "Erros e letras",
      opcoes=["estrelas", "valor de p"]),
    P("anot.colchetes", [], "lista", "Colchetes de significância", "Erros e letras"),
    P("anot.linhas", [], "lista", "Linhas de referência", "Erros e letras"),
    P("anot.textos", [], "lista", "Textos livres", "Erros e letras"),
    P("anot.faixas", [], "lista", "Faixas sombreadas", "Erros e letras"),
    P("anot.formas", [], "lista", "Setas e formas", "Erros e letras"),
    # ------------------------------------------------------------------ Legenda
    P("legenda.mostrar", True, "bool", "Mostrar legenda", "Legenda"),
    P("legenda.posicao", "automática", "escolha", "Posição", "Legenda", opcoes=POSICOES_LEGENDA),
    P("legenda.direta", False, "bool", "Rótulos diretos na ponta das linhas (sem caixa de legenda)", "Legenda",
      ajuda="Cada linha recebe o nome ao lado do último ponto, na cor da série"),
    P("legenda.colunas", 0, "int", "Colunas (0 = automático)", "Legenda", minimo=0, maximo=8, passo=1),
    P("legenda.titulo", True, "bool", "Mostrar título da legenda", "Legenda"),
    P("legenda.moldura", False, "bool", "Moldura", "Legenda"),
    P("legenda.comp_simbolo", 1.6, "num", "Comprimento do símbolo", "Legenda", minimo=0.5, maximo=5, passo=0.1),
    P("legenda.espaco", 0.5, "num", "Espaço entre itens", "Legenda", minimo=0, maximo=2, passo=0.05),
    P("legenda.dx", 0.0, "num", "Deslocamento horizontal (fração)", "Legenda", minimo=-0.5, maximo=0.5, passo=0.01),
    P("legenda.dy", 0.0, "num", "Deslocamento vertical (fração)", "Legenda", minimo=-0.5, maximo=0.5, passo=0.01),
    # ------------------------------------------------------------------ Regressão
    P("reg.equacao", True, "bool", "Mostrar equação", "Regressão"),
    P("reg.r2", True, "bool", "Mostrar R²", "Regressão"),
    P("reg.r2_aj", False, "bool", "Usar R² ajustado", "Regressão"),
    P("reg.posicao", "automática", "escolha", "Posição das equações", "Regressão", opcoes=POSICOES_EQ),
    P("reg.digitos", 4, "int", "Algarismos significativos na equação", "Regressão", minimo=2, maximo=6, passo=1),
    P("reg.banda", False, "bool", "Faixa ao redor da curva", "Regressão"),
    P("reg.banda_tipo", "confiança", "escolha", "Tipo de faixa", "Regressão", opcoes=["confiança", "predição", "ambas"],
      ajuda="Confiança: incerteza da curva média. Predição: onde se espera uma nova observação (mais larga)."),
    P("reg.banda_nivel", "95%", "escolha", "Nível da faixa", "Regressão", opcoes=["90%", "95%", "99%"]),
    P("reg.banda_alfa", 0.15, "num", "Opacidade da faixa", "Regressão", minimo=0.02, maximo=0.6, passo=0.01),
    P("reg.esp", 1.0, "num", "Espessura da curva (pt)", "Regressão", minimo=0.2, maximo=4, passo=0.1),
    P("reg.estender", 0.0, "num", "Estender a curva além dos dados (fração)", "Regressão", minimo=0, maximo=0.5, passo=0.05),
    P("reg.media_ns", True, "bool", "Linha da média quando não significativo", "Regressão"),
    P("reg.marcar_ponto", False, "bool", "Marcar ponto de máximo/platô", "Regressão"),
    # ------------------------------------------------------------------ Multivariada
    P("pca.elipses", "automático", "escolha", "Elipses de confiança (95%) no biplot", "Multivariada",
      opcoes=["automático", "sim", "não"]),
    P("pca.setas", True, "bool", "Mostrar vetores das variáveis", "Multivariada"),
    P("pca.setas_cor", "#4A4A4A", "cor", "Cor dos vetores", "Multivariada"),
    P("pca.eixo_x", 1, "int", "Componente no eixo X", "Multivariada", minimo=1, maximo=6, passo=1),
    P("pca.eixo_y", 2, "int", "Componente no eixo Y", "Multivariada", minimo=1, maximo=6, passo=1),
    P("pca.tam_pontos", 14.0, "num", "Tamanho dos pontos (pt²)", "Multivariada", minimo=2, maximo=80, passo=1),
    P("cor.triangulo", "inferior", "escolha", "Matriz de correlação", "Multivariada", opcoes=["inferior", "completa"]),
    P("cor.valores", True, "bool", "Mostrar coeficientes nas células", "Multivariada"),
    P("cor.estrelas", True, "bool", "Mostrar asteriscos de significância", "Multivariada"),
    P("cor.decimais", 2, "int", "Casas decimais dos coeficientes", "Multivariada", minimo=1, maximo=3, passo=1),
    P("cor.paleta", "Azul–branco–terracota", "escolha", "Escala de cores", "Multivariada",
      opcoes=["Azul–branco–terracota", "Azul–branco–vermelho", "Verde–branco–roxo", "Cinzas"]),
    # ------------------------------------------------------------------ Painel
    P("painel.estilo", "a", "escolha", "Rótulo dos painéis", "Painel", opcoes=["a", "A", "(a)", "(A)", "a)", "A.", "nenhum"]),
    P("painel.tamanho", 8.0, "num", "Tamanho do rótulo (pt)", "Painel", minimo=4, maximo=24, passo=0.5),
    P("painel.peso", "normal", "escolha", "Peso do rótulo", "Painel", opcoes=["light", "normal", "bold"]),
    P("painel.dx", -0.02, "num", "Posição horizontal do rótulo", "Painel", minimo=-0.4, maximo=0.2, passo=0.01),
    P("painel.dy", 1.02, "num", "Posição vertical do rótulo", "Painel", minimo=0.8, maximo=1.3, passo=0.01),
    P("painel.wspace", 0.35, "num", "Espaço horizontal entre painéis", "Painel", minimo=0, maximo=1.5, passo=0.05),
    P("painel.hspace", 0.45, "num", "Espaço vertical entre painéis", "Painel", minimo=0, maximo=1.5, passo=0.05),
    P("painel.mesma_escala_y", False, "bool", "Mesma escala de Y em todos os painéis", "Painel",
      ajuda="Como o 'Merge Graphs' do OriginPro: facilita comparar painéis lado a lado"),
    P("painel.ocultar_internos", False, "bool", "Ocultar números e título de Y nos painéis internos", "Painel",
      ajuda="Só vale com a mesma escala de Y"),
]

POR_CHAVE = {p.chave: p for p in PARAMS}
PADRAO = {p.chave: copy.deepcopy(p.padrao) for p in PARAMS}

PRESETS = {
    "Solos (padrão da plataforma)": {},
    "Inspirado em Nature": {
        "fonte.familia": "Arial (Liberation Sans)", "fonte.tamanho": 7, "fonte.titulo_eixo": 7, "fonte.numeros": 6.5,
        "fonte.legenda": 6.5, "painel.estilo": "a", "painel.peso": "bold", "painel.tamanho": 8,
        "eixos.espessura": 0.5, "eixos.marcas_esp": 0.5, "series.paleta": "Okabe-Ito",
    },
    "Inspirado em Science": {
        "fonte.familia": "Arial (Liberation Sans)", "fonte.tamanho": 7, "painel.estilo": "A", "painel.peso": "bold",
        "painel.tamanho": 9, "eixos.espessura": 0.75, "eixos.marcas_esp": 0.75, "series.paleta": "Clássica (tab10)",
    },
    "Inspirado em The Lancet": {
        "fonte.familia": "Arial (Liberation Sans)", "fonte.tamanho": 7.5, "painel.estilo": "A", "painel.peso": "bold",
        "series.paleta": "Azul–terracota", "medias.tipo": "barras", "eixos.espessura": 0.6,
    },
    "Inspirado em Elsevier": {
        "fonte.familia": "Arial (Liberation Sans)", "fonte.tamanho": 8, "fonte.titulo_eixo": 8, "fonte.numeros": 8,
        "fonte.legenda": 7.5, "fonte.letras": 8, "tela.largura_mm": 90.0, "painel.estilo": "(a)",
    },
    "Tons de cinza (impressão)": {
        "series.paleta": "Tons de cinza", "series.cor_unica": "#1A1A1A", "medias.barra_cor": "#D9D9D9",
        "medias.hachuras": True, "medias.contorno_esp": 0.5,
    },
    "Apresentação (slides)": {
        "tela.largura_mm": 160.0, "fonte.tamanho": 14, "fonte.titulo_eixo": 14, "fonte.numeros": 13,
        "fonte.legenda": 12, "fonte.letras": 13, "fonte.equacao": 12, "series.marcador_tam": 7, "medias.obs_tam": 22,
        "eixos.espessura": 1.2, "eixos.marcas_esp": 1.2, "eixos.marcas_comp": 5, "erro.esp": 1.5, "reg.esp": 2.0,
        "series.linha_esp": 2.0,
    },
}


DIVERGENTES = {
    "Azul–branco–terracota": ("#2878A8", "#F4F1EC", "#A6461E"),
    "Azul–branco–vermelho": ("#2166AC", "#F7F7F7", "#B2182B"),
    "Verde–branco–roxo": ("#1B7837", "#F7F7F7", "#762A83"),
    "Cinzas": ("#4D4D4D", "#FFFFFF", "#4D4D4D"),
}


def resolver(*camadas) -> dict:
    """Sobrepõe camadas de ajustes ao padrão. Valores None/'' em camadas superiores
    só sobrescrevem quando o parâmetro admite vazio (limites de eixo, rótulos)."""
    t = copy.deepcopy(PADRAO)
    for c in camadas:
        if not c:
            continue
        for k, v in c.items():
            if k in POR_CHAVE:
                t[k] = copy.deepcopy(v)
    return t


def diferencas(t: dict, base: dict | None = None) -> dict:
    """Somente o que difere de `base` (por padrão, do PADRÃO) — é o que vai para o JSON."""
    base = base or PADRAO
    return {k: v for k, v in t.items() if k in POR_CHAVE and v != base.get(k)}


def para_json(ajustes: dict, nome="Meu tema") -> str:
    return json.dumps({"plataforma": "Stat-Soil", "versao_tema": 1, "nome": nome,
                       "parametros": ajustes}, ensure_ascii=False, indent=2)


def de_json(texto: str) -> tuple[str, dict, list]:
    d = json.loads(texto)
    params = d.get("parametros", d)
    validos, ignorados = {}, []
    for k, v in params.items():
        if k not in POR_CHAVE:
            ignorados.append(k)
            continue
        p = POR_CHAVE[k]
        if p.tipo == "escolha" and p.opcoes and v not in p.opcoes:
            ignorados.append(k)
            continue
        validos[k] = v
    return d.get("nome", "Tema importado"), validos, ignorados


def paleta(t: dict) -> list:
    return PALETAS.get(t["series.paleta"], PALETAS["Solos do Cerrado"])


def cor_grupo(t: dict, rotulo, i: int) -> str:
    return t["grupos.cores"].get(str(rotulo)) or paleta(t)[i % len(paleta(t))]


def marcador_grupo(t: dict, rotulo, i: int) -> str:
    m = t["grupos.marcadores"].get(str(rotulo))
    if m:
        return MARCADORES.get(m, m)
    return ORDEM_MARCADORES[i % len(ORDEM_MARCADORES)] if t["series.variar_marcador"] else "o"


def linha_grupo(t: dict, rotulo, i: int) -> str:
    m = t["grupos.linhas"].get(str(rotulo))
    if m:
        return ESTILOS_LINHA.get(m, m)
    return ["-", "--", "-.", ":"][i % 4] if t["series.variar_linha"] else "-"


def nome_nivel(t: dict, nivel) -> str:
    return t["niveis.renomear"].get(str(nivel), str(nivel))


def rotulo_painel(estilo: str, i: int) -> str:
    if estilo == "nenhum":
        return ""
    a, A = "abcdefghijklmnopqrstuvwxyz"[i % 26], "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[i % 26]
    return {"a": a, "A": A, "(a)": f"({a})", "(A)": f"({A})", "a)": f"{a})", "A.": f"{A}."}[estilo]


# ----------------------------------------------------------------------------
# Texto rico (códigos inspirados nos "escape codes" do OriginPro)
# ----------------------------------------------------------------------------
import re as _re

_SUP = str.maketrans("0123456789+-−=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁼⁽⁾ⁿ")
_SUB = str.maketrans("0123456789+-−=()", "₀₁₂₃₄₅₆₇₈₉₊₋₋₌₍₎")
_SUP_OK = set("0123456789+-−=()n")
_SUB_OK = set("0123456789+-−=()")
GREGO = {"alpha": "α", "beta": "β", "gamma": "γ", "Gamma": "Γ", "delta": "δ", "Delta": "Δ", "epsilon": "ε",
         "zeta": "ζ", "eta": "η", "theta": "θ", "Theta": "Θ", "kappa": "κ", "lambda": "λ", "Lambda": "Λ",
         "mu": "µ", "nu": "ν", "xi": "ξ", "pi": "π", "Pi": "Π", "rho": "ρ", "sigma": "σ", "Sigma": "Σ",
         "tau": "τ", "phi": "φ", "Phi": "Φ", "chi": "χ", "psi": "ψ", "Psi": "Ψ", "omega": "ω", "Omega": "Ω",
         "deg": "°", "pm": "±", "times": "×", "cdot": "·", "le": "≤", "ge": "≥", "permil": "‰"}


def _mt(txt):
    """Escapa texto para dentro de um bloco mathtext."""
    return "".join("\\ " if c == " " else ("\\" + c if c in "{}%#&_^$" else c) for c in txt)


def rico(s):
    """Converte códigos simples em texto formatado:
    ^{-1} ou ^-1 → sobrescrito · _{2} → subscrito · *Crotalaria* → itálico · \\alpha → α."""
    if not isinstance(s, str) or not any(c in s for c in "^_\\*$"):
        return s
    s = s.replace("$", "\\$")
    s = _re.sub(r"\\([A-Za-z]+)", lambda m: GREGO.get(m.group(1), m.group(0)), s)

    def sup(m):
        txt = m.group(1) if m.group(1) is not None else m.group(2)
        if txt and set(txt) <= _SUP_OK:
            return txt.translate(_SUP)
        return "$^{\\mathregular{" + _mt(txt) + "}}$"

    def sub(m):
        txt = m.group(1)
        if txt and set(txt) <= _SUB_OK:
            return txt.translate(_SUB)
        return "$_{\\mathregular{" + _mt(txt) + "}}$"

    s = _re.sub(r"\^\{([^}]*)\}|\^([-−+]?[0-9]+)", sup, s)
    s = _re.sub(r"_\{([^}]*)\}", sub, s)
    s = _re.sub(r"\*([^*\s][^*]*?)\*", lambda m: "$\\mathit{" + _mt(m.group(1)) + "}$", s)
    return s


def nome_rico(t: dict, nivel) -> str:
    """Nome exibido do nível; códigos de formatação valem apenas para nomes digitados pelo usuário."""
    novo = t["niveis.renomear"].get(str(nivel))
    return rico(novo) if novo else str(nivel)
