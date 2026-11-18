# Stat-Soil · v3.0.0

Plataforma web para análise estatística de experimentos agronômicos, no mesmo padrão da plataforma de
recomendação de solo: **Python + motor determinístico + Streamlit**, entrada e saída em **Excel**, hospedagem
gratuita no **Streamlit Community Cloud**.

## O que faz

| Etapa | Recursos |
|---|---|
| Delineamentos | DIC, DBC, DQL · um fator · fatorial (2 a 4 fatores) · fatorial + tratamento(s) adicional(is) · parcelas subdivididas (tempo/espaço, com fatorial na parcela ou subparcela) · sub-subdivididas · faixas |
| ANOVA | SQ exatas; médias ajustadas e SQ tipo III em delineamentos de um estrato (aceita parcelas perdidas); cada efeito testado contra o erro do seu estrato em parcelas subdivididas/faixas; CV por estrato |
| Pressupostos | Shapiro-Wilk, Anderson-Darling, Bartlett, Levene (Brown-Forsythe), não aditividade de Tukey, resíduos studentizados, Box-Cox com aplicação em um clique |
| Médias | Tukey (Tukey-Kramer), Scott-Knott, LSD, Duncan, SNK, Bonferroni, Dunnett; letras pelo algoritmo *insert-absorb*; desdobramento automático das interações com erro combinado e GL de Satterthwaite |
| Regressão | decomposição polinomial na ANOVA + 12 modelos (linear, quadrático, cúbico, raiz, log, Mitscherlich, linear-platô, quadrático-platô, exponencial, potência, Michaelis-Menten, logístico) ranqueados por adequação e AICc, com pontos notáveis (MET, platô, doses para 90/95%) |
| Robustas | ANOVA de Welch + Games-Howell, Kruskal-Wallis + Dunn, Friedman + Conover (p ajustados por Holm); exclusão de observações pelo número da linha com reanálise |
| Inferência | tamanhos de efeito (η²p, ω²p), IC 95% das médias e das diferenças par a par, contrastes definidos pelo usuário (com verificação de ortogonalidade), máxima eficiência econômica (MEE) |
| Modelos mistos | parcelas subdivididas/sub-subdivididas/faixas com parcelas perdidas: REML próprio, F de Wald e GL por contenção |
| Vários ambientes | análise conjunta (locais, safras): razão de Hartley, blocos dentro de ambientes, ambientes fixos ou aleatórios |
| Multivariada | correlações (Pearson/Spearman), PCA (biplot com elipses), agrupamento hierárquico (UPGMA/Ward, corte de Mojena, correlação cofenética, dendrograma), análise de trilha (efeitos diretos e indiretos, VIF, número de condição, crista) |
| Planejamento | número de repetições pelo poder do teste F (F não central) e DMS de Tukey esperada a partir do CV |
| Textos | rascunho automático de Material e Métodos e de Resultados (pt/en) |
| Saídas | Excel com tabelas em padrão de periódico; **relatório Word completo** (Métodos, resultados, tabelas 1,0/0,5 pt e figuras com legenda); gráficos em PNG/TIFF 600 dpi, SVG editável e PDF; **arquivo de projeto .estatexp** para reabrir tudo depois |

## Novidades da v3.0

- **Edição por clique**: no Estúdio, passar o mouse destaca cada elemento da figura (eixos, títulos, legenda, letras,
  equação, área do gráfico) e um clique abre só os controles dele. O modo avançado mantém todas as opções em abas.
- **Galeria de estilos** com miniaturas da própria figura; **23 paletas** em três grupos (seguras para daltônicos,
  periódicos, sequenciais) escolhidas pela faixa de cores.
- **Novos gráficos**: pirulito, ordenação pela média, linha estatística (F, p, η²p), colchetes automáticos entre
  médias, rótulos diretos no lugar da legenda e barras empilhadas de composição (valores ou 100%).
- **Quadro de resultados** por variável (efeitos com barra de η² parcial, pressupostos com luzes, leitura rápida) e
  visão geral de todas as variáveis. Novos testes: Lilliefors, D'Agostino-Pearson, Fligner-Killeen e Cochran.
- **Pasta de figuras da sessão** com download em lote; aba “Pasta e downloads”.
- **Downloads**: todo arquivo é gerado antes de o botão de baixar aparecer (fim do “Failed to generate file for
  download”); Excel, Word, HTML e pacotes usam “Preparar” e depois “Baixar”.
- **Relatórios**: Word reestruturado (capa, resumo, seções numeradas, pressupostos, paginação) e relatório em HTML
  de arquivo único, imprimível em PDF.
- **Explorador interativo** dos dados (Plotly) e tabela de dados fixa, com rolagem própria.

## Novidades da v2.2.1

- Correção do erro `AttributeError` em `ajuste_rapido` no Streamlit Cloud (módulo antigo mantido em memória após a
  atualização): a revisão de cada módulo é conferida e, se preciso, eles são recarregados.
- Fontes e cores não dependem mais do `.streamlit/config.toml` nem da pasta `static/` estarem publicadas: o tema é
  aplicado em tempo de execução e as fontes têm origem alternativa na internet e fontes de sistema sem serifa.

## Novidades da v2.2

- **Nome e identidade Stat-Soil**: logos novas no cabeçalho e na barra lateral, padronagem "horizonte do solo",
  ícone do navegador.
- **Temas claro e escuro de verdade** (bancada bege e painel grafite, este um pouco mais claro), alternados no menu
  ⋮ → Settings → Theme; mostradores de cristal líquido, teclas com LED, etiquetas de rotulador e grão de papel.
- **Uma família tipográfica** em toda a plataforma (Archivo, larguras normal e expandida), inclusive na barra lateral;
  DSEG14 apenas nos mostradores numéricos.
- **Correções relatadas**: o modelo de regressão agora pode ser trocado ao lado do gráfico (Ajuste rápido), na aba
  Regressão e no Estúdio, e as escolhas ficam sincronizadas; os valores individuais podem ser ligados/desligados em
  todos os tipos de gráfico, inclusive barras, direto no Ajuste rápido.
- **Estúdio inspirado no OriginPro**: barra rápida, busca de opções, desfazer, copiar/colar formato por partes,
  novos tipos (meia-caixa, meio-violino, linhas de interação), rótulos de valor, contorno automático, escalas
  log10/log2/ln/raiz, fator 10ⁿ, separador de milhar, texto formatado (sobrescrito, subscrito, itálico, grego),
  faixas sombreadas, setas e formas, faixa de predição, mesma escala Y em painéis, EPS e TIFF CMYK.
- **Layout**: gráficos em grade de cartões com ações logo abaixo, cabeçalho com o estado de cada etapa.

## Novidades da v2.1

- Visual "instrumento anos 80": grafite quente, âmbar, JetBrains Mono + Archivo (fontes embutidas em `static/fonts`),
  mostradores numéricos no lugar de medidores; figuras sempre em cartão branco.
- Alternativas robustas e não paramétricas, exclusão de discrepantes com reanálise, tamanhos de efeito e IC.
- Contrastes, MEE, análise conjunta, modelo misto (REML) para parcelas perdidas em parcelas subdivididas.
- Agrupamento (dendrograma no Estúdio), análise de trilha e aba Planejamento.
- Relatório Word completo e arquivo de projeto (.estatexp).
- Correção: downloads gerados sob demanda não acessam mais o estado da sessão (o Excel de resultados falhava na v2.0
  em alguns servidores).

## Novidades da v2.0

- **Estúdio de figuras** (nova aba): edição detalhada de cada figura com prévia ao vivo — tamanho exato em mm e dpi,
  8 famílias de fonte com tamanho por elemento, eixos (limites, intervalos, marcas secundárias, eixo quebrado, eixos
  destacados, escala log, separador decimal), cor/marcador/linha por grupo, renomear/reordenar/ocultar níveis,
  6 tipos de gráfico de médias (pontos, barras, box, violino, raincloud, beeswarm), barras de erro (EP, DP, IC95,
  só superior, traço terminal), letras, colchetes de significância, linhas de referência, textos livres, legenda e
  equações com faixa de confiança da curva. Modo **Painel** (grade de até 4 × 4 com rótulos a/b/c) e modo
  **Tema global** com presets e temas salvos/carregados em .json.
- **Tabelas** com botões Excel e Word no padrão de periódico (1,0 pt / 0,5 pt; cabeçalho em negrito).
- **Regressão**: coluna "Falta de ajuste" com veredito legível; famílias de crescimento (Gompertz, Weibull),
  isotermas (Langmuir, Freundlich, Temkin, Sips) e cinéticas (1ª ordem/Stanford & Smith, pseudo-2ª ordem, Elovich,
  difusão parabólica, dois compartimentos).

## Estrutura

```
app.py                  interface Streamlit
ui_comum.py             estado, catálogo de figuras, cache e tabelas na interface
ui_estudio.py           Estúdio de figuras (edição por clique, galeria, painel, tema global)
ui_comp.py              componentes próprios: figura clicável e seletor de paletas (st.components.v2)
ui_analises.py          seções das análises complementares (robustas, contrastes, MEE, conjunta, trilha…)
motor/
  modelo.py             especificação do delineamento, validação e preparo dos dados
  anova.py              motor de ANOVA (um estrato e multiestrato), fatias e desdobramentos
  comparacoes.py        testes de médias e letras
  regressao.py          catálogo de modelos, ajuste, ranqueamento e equações
  pressupostos.py       testes de pressupostos e Box-Cox
  multivariada.py       correlações, PCA, agrupamento e análise de trilha
  robusto.py            Welch/Games-Howell, Kruskal-Wallis/Dunn, Friedman/Conover
  misto.py              REML para dados multiestrato incompletos
  conjunta.py           análise conjunta de experimentos
  planejamento.py       poder e número de repetições
  relatorio_blocos.py   estrutura do relatório (compartilhada por Word e HTML)
  relatorio_docx.py     relatório completo em Word
  relatorio_html.py     relatório em HTML de arquivo único
  projeto.py            arquivo de projeto .estatexp
  tema.py               esquema de ~160 parâmetros de estilo, presets e temas .json
  figuras.py            motor gráfico v2 (especificações de dados + tema; painéis; exportação exata)
  tabelas.py            tabelas avulsas em Excel e Word no padrão de periódico
  graficos.py           registro de fontes (e funções da v1, mantidas por compatibilidade)
  relatorio.py          escolha automática dos gráficos e pacote .zip
  exportar.py           Excel de resultados
  templates.py          modelos de planilha por delineamento
  textos.py             Material e Métodos e interpretação automáticos
  exemplos.py           dados simulados de cada delineamento
assets/fonts/           Roboto, Inter, Source Sans 3, IBM Plex, Lato, Open Sans, Liberation (OFL) — figuras
static/fonts/           Archivo (variável), DSEG14 e JetBrains Mono (OFL) — interface
estilo.py               identidade visual (CSS dos dois temas, cabeçalho, mostradores, etiquetas)
tests/                  validação contra statsmodels/SciPy e fórmulas de livro
exemplos/dados_ref.xlsx experimento real usado como referência
```

## Rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
python -m pytest -q        # testes de validação
```

## Publicar no Streamlit Community Cloud

1. Envie **todo** o conteúdo desta pasta ao repositório do GitHub, inclusive a pasta oculta `.streamlit/`
   (no macOS ela não aparece no Finder: use ⌘ ⇧ . para mostrá-la, ou envie pelo GitHub Desktop / `git push`).
   Ela liga o servidor de arquivos da pasta `static/`, de onde vêm as fontes.
2. Em <https://share.streamlit.io>, **Create app** → repositório, branch `main`, arquivo `app.py`; Python 3.11 ou 3.12.
3. Depois de cada atualização, use **Manage app → Reboot app**. A própria plataforma também confere a revisão dos
   módulos e descarta versões antigas que o servidor tenha mantido em memória.

Se a pasta `.streamlit/` ficar de fora, a plataforma continua com as cores certas (o tema é aplicado também em
tempo de execução) e busca as fontes na internet (Google Fonts e jsDelivr); nunca cai numa fonte serifada.

## Validação

`tests/test_motor.py` compara o motor com o statsmodels (SQ tipo I/III em DIC, DBC desbalanceado, DQL, fatorial,
parcelas subdivididas, sub-subdivididas e faixas), com `scipy.stats.dunnett`, com o Tukey do statsmodels e com as
fórmulas de Banzatto & Kronka para o erro combinado de parcelas subdivididas (QM, GL de Satterthwaite e DMS).
`tests/test_v21.py` valida Welch (statsmodels), Kruskal-Wallis e Friedman (SciPy), contrastes ortogonais (soma das
SQ = SQ de tratamentos), análise conjunta (statsmodels), MEE (solução analítica), trilha (coeficientes padronizados),
o modelo misto com parcela perdida e o arquivo de projeto (ida e volta exata).
`tests/test_v30.py` cobre os novos gráficos, o mapa de regiões clicáveis, os novos testes de pressupostos e os
relatórios em Word e HTML.

## Limitações atuais

- Os testes de médias em desdobramentos multiestrato usam um GL único (Satterthwaite) por fatia.
- Medidas repetidas com estrutura de covariância (AR(1), não estruturada) ainda não estão implementadas; o modelo
  misto atual cobre apenas os estratos do delineamento.
- A análise conjunta cobre DIC e DBC (um fator ou fatorial); conjunta de parcelas subdivididas ainda não.
