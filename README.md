# Stat-Soil · v2.2

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
ui_estudio.py           Estúdio de figuras (figura, painel, tema global)
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
  relatorio_docx.py     relatório completo em Word
  projeto.py            arquivo de projeto .estatexp
  tema.py               esquema de ~130 parâmetros de estilo, presets e temas .json
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

1. Crie um repositório no GitHub (ex.: `estatistica-experimental`) e envie o conteúdo desta pasta.
2. Em <https://share.streamlit.io>, **Create app** → selecione o repositório, branch `main`, arquivo `app.py`.
3. Em *Advanced settings*, escolha Python 3.11 ou 3.12. Deploy.

Identidade visual: as logos ficam em `assets/` (`logo_completo.png`, `logo_emblema.png`, `logo_marca.png`,
`icone.png`). As cores e fontes da interface estão em `.streamlit/config.toml` (o `server.enableStaticServing` precisa ficar
ativo para as fontes embutidas); a paleta dos gráficos, em `motor/graficos.py`
(`PALETA`, validada para daltonismo).

## Validação

`tests/test_motor.py` compara o motor com o statsmodels (SQ tipo I/III em DIC, DBC desbalanceado, DQL, fatorial,
parcelas subdivididas, sub-subdivididas e faixas), com `scipy.stats.dunnett`, com o Tukey do statsmodels e com as
fórmulas de Banzatto & Kronka para o erro combinado de parcelas subdivididas (QM, GL de Satterthwaite e DMS).
`tests/test_v21.py` valida Welch (statsmodels), Kruskal-Wallis e Friedman (SciPy), contrastes ortogonais (soma das
SQ = SQ de tratamentos), análise conjunta (statsmodels), MEE (solução analítica), trilha (coeficientes padronizados),
o modelo misto com parcela perdida e o arquivo de projeto (ida e volta exata).

## Limitações atuais

- Os testes de médias em desdobramentos multiestrato usam um GL único (Satterthwaite) por fatia.
- Medidas repetidas com estrutura de covariância (AR(1), não estruturada) ainda não estão implementadas; o modelo
  misto atual cobre apenas os estratos do delineamento.
- A análise conjunta cobre DIC e DBC (um fator ou fatorial); conjunta de parcelas subdivididas ainda não.
