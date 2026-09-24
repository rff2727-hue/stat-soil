# Estatística Experimental

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
| Extras | correlações (Pearson/Spearman), PCA (biplot com elipses), rascunho automático de Material e Métodos e de Resultados (pt/en) |
| Saídas | Excel com tabelas em padrão de periódico (resumo de QM com asteriscos, médias ± EP com letras, desdobramentos, regressões, pressupostos, descritiva, textos, dados); gráficos em PNG/TIFF 600 dpi, SVG editável e PDF |

## Estrutura

```
app.py                  interface Streamlit
motor/
  modelo.py             especificação do delineamento, validação e preparo dos dados
  anova.py              motor de ANOVA (um estrato e multiestrato), fatias e desdobramentos
  comparacoes.py        testes de médias e letras
  regressao.py          catálogo de modelos, ajuste, ranqueamento e equações
  pressupostos.py       testes de pressupostos e Box-Cox
  multivariada.py       correlações e PCA
  graficos.py           gráficos de publicação (Roboto, sem grade, EP)
  relatorio.py          escolha automática dos gráficos e pacote .zip
  exportar.py           Excel de resultados
  templates.py          modelos de planilha por delineamento
  textos.py             Material e Métodos e interpretação automáticos
  exemplos.py           dados simulados de cada delineamento
assets/fonts/           Roboto (OFL)
tests/                  validação contra statsmodels/SciPy e fórmulas de livro
exemplos/dados_ref.xlsx experimento real usado como referência
```

## Rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
python -m pytest -q        # 12 testes de validação
```

## Publicar no Streamlit Community Cloud

1. Crie um repositório no GitHub (ex.: `estatistica-experimental`) e envie o conteúdo desta pasta.
2. Em <https://share.streamlit.io>, **Create app** → selecione o repositório, branch `main`, arquivo `app.py`.
3. Em *Advanced settings*, escolha Python 3.11 ou 3.12. Deploy.

Identidade visual: coloque o logotipo em `assets/logo.png` (e, se quiser, `assets/icone.png` para a aba do
navegador). As cores do tema estão em `.streamlit/config.toml`; a paleta dos gráficos, em `motor/graficos.py`
(`PALETA`, validada para daltonismo).

## Validação

`tests/test_motor.py` compara o motor com o statsmodels (SQ tipo I/III em DIC, DBC desbalanceado, DQL, fatorial,
parcelas subdivididas, sub-subdivididas e faixas), com `scipy.stats.dunnett`, com o Tukey do statsmodels e com as
fórmulas de Banzatto & Kronka para o erro combinado de parcelas subdivididas (QM, GL de Satterthwaite e DMS).

## Limitações atuais

- Parcelas subdivididas, sub-subdivididas e faixas exigem dados completos (sem parcelas perdidas).
- Os testes de médias em desdobramentos multiestrato usam um GL único (Satterthwaite) por fatia.
- Medidas repetidas com estrutura de covariância (modelos mistos) ainda não estão implementadas.
