# Composição algorítmica com cadeias de Markov: melodias no estilo de Michael Jackson

TP1 – Composição Musical Algorítmica (IA na Música, UFMG).

O sistema aprende, com cadeias de Markov, as transições entre notas nas melodias de 34 músicas de Michael Jackson (solo, Jackson 5 e fase infantil) e gera melodias novas em MIDI.

- **Método:** cadeias de Markov de ordem configurável (0 a n), com backoff para ordens menores quando um contexto nunca foi visto.
- **Restrição estilística:** o estilo de Michael Jackson, definido pelo corpus de treino.
- **Estado do modelo:** cada estado é um par `(altura MIDI, duração em tempos)`. As melodias são transpostas para Dó maior / Lá menor antes do treino.
- **Probabilidades:** aprendidas do corpus real, por contagem de transições.

## Estrutura

```
src/preprocessar.py     # lê os MIDIs, extrai a melodia e gera o corpus (corpus_mj.json)
src/gerar.py            # treina a cadeia e gera as melodias em MIDI
musicas.csv             # lista das músicas usadas e qual trilha de cada MIDI é a melodia
corpus_mj.json          # corpus já pré-processado (entrada do gerar.py)
teste_sanidade.py       # reconstrói MIDIs a partir do corpus para conferir o pré-processamento
saida/                  # melodias geradas (.mid) e áudios sintetizados
requirements.txt
```

## Instalação

Requer Python 3.10 ou superior.

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

Todos os comandos abaixo devem ser executados **da raiz do repositório**, pois os caminhos (`musicas.csv`, `corpus_mj.json`, `saida/`) são relativos.

## Reproduzindo os resultados

### 1. Gerar melodias (não precisa dos MIDIs originais)

O `corpus_mj.json` já está no repositório, então basta:

```bash
python src/gerar.py --ordem 3
```

Argumentos de `src/gerar.py`:

| Argumento | Padrão | Descrição |
|---|---|---|
| `--ordem` | 2 | ordem da cadeia (memória, em número de estados) |
| `--quantas` | 10 | quantas melodias gerar |
| `--semente` | 0 | semente da primeira melodia (as seguintes usam semente+1, +2, ...) |
| `--tempos` | 64 | tamanho em tempos (64 = 16 compassos em 4/4) |
| `--bpm` | 100 | andamento do MIDI gerado |
| `--instrumentos` | 0 | programas General MIDI separados por vírgula (0 = piano, 11 = vibrafone, 80 = lead square, 73 = flauta) |
| `--corpus` | `corpus_mj.json` | arquivo JSON com o corpus |

Os arquivos saem em `saida/` com o nome `mj_ordem<N>_semente<S>.mid`. A mesma ordem e semente geram sempre a mesma melodia. Com vários instrumentos, todos tocam a mesma melodia (a partir do segundo, deslocada em oitavas); o timbre é só orquestração para a audição.

Exemplos:

```bash
# comparar ordens com as mesmas sementes
python src/gerar.py --ordem 1 --quantas 5
python src/gerar.py --ordem 3 --quantas 5
python src/gerar.py --ordem 5 --quantas 5

# variar andamento e timbre
python src/gerar.py --ordem 3 --semente 10 --quantas 3 --bpm 115 --instrumentos 11,80
```

### 2. Refazer o pré-processamento (opcional)

Isso exige os MIDIs originais, que **não estão no repositório** por questões de direitos autorais. Para refazer, coloque os 34 arquivos `.mid` listados na coluna `arquivo` do `musicas.csv` diretamente na pasta `data/` e rode:

```bash
python src/preprocessar.py
```

Opções: `--sem-transposicao` e `--sem-oitava` (para experimentos com e sem esses passos) e `--incluir-ouvir` (inclui músicas com status "ouvir" no CSV).

### 3. Conferir o pré-processamento

```bash
python teste_sanidade.py
```

Reconstrói MIDIs a partir do corpus na pasta `sanidade/`, para escutar se as melodias continuam reconhecíveis.

### 4. Áudio

Os MIDIs são convertidos para áudio (`.wav`) apenas para audição. Os arquivos renderizados ficam em `saida/`, com o sufixo `-mix` no nome (por exemplo, `mj_ordem2_semente6-mix.wav`).

Junto do relatório, foi submetido uma pasta com alguns arquivos .wav:

| Arquivo | Ordem | Semente | Para que serve |
|---|---|---|---|
| `mj_ordem2_semente6-mix.wav` | 2 | 6 | comparação entre ordens (mesma semente) |
| `mj_ordem5_semente6-mix.wav` | 5 | 6 | comparação entre ordens (mesma semente) |
| `mj_ordem2_semente7-mix.wav` | 2 | 7 | comparação entre ordens (mesma semente) |
| `mj_ordem5_semente7-mix.wav` | 5 | 7 | comparação entre ordens (mesma semente) |
| `mj_ordem2_semente5-mix.wav` | 2 | 5 | exemplo adicional |
| `mj_ordem4_semente8-mix.wav` | 4 | 8 | exemplo adicional, em outra ordem |

**Como ouvir a diferença entre as ordens:** as sementes 6 e 7 foram renderizadas na ordem 2 e na ordem 5, com a mesma semente nas duas. Compare `mj_ordem2_semente6` com `mj_ordem5_semente6`, e `mj_ordem2_semente7` com `mj_ordem5_semente7`. A ordem baixa tende a soar mais livre e menos reconhecível. A ordem alta tende a seguir trechos mais fiéis às músicas do corpus, com maior risco de reproduzir passagens inteiras.

Os outros arquivos (`ordem2_semente5` e `ordem4_semente8`) mostram como o resultado soa em outras ordens e sementes.

## Uso de IA

Ferramentas de IA foram usadas como apoio neste projeto, conforme permitido pelo enunciado.

**Ferramenta:** Claude (Anthropic).

**O que foi feito com IA e com qual objetivo:**

- **Geração de código auxiliar:** scripts de apoio ao experimento, como leitura da lista de músicas, extração de notas dos MIDIs, teste de sanidade, saída MIDI com vários instrumentos e argumentos de linha de comando.
- **Arquitetura do projeto:** discussão e definição da organização do código, da representação do corpus (estados `(altura, duração)`), das etapas de pré-processamento e geração, e dos arquivos do repositório.


**Links das conversas:**

- https://claude.ai/share/b1ff564e-dc1e-442b-959b-8ce2f7a5ea21

## Dados

As melodias de treino vêm de arquivos MIDI de músicas de Michael Jackson, Jackson 5 e da fase infantil dele, escolhidos em `musicas.csv`. Para cada arquivo, o CSV indica qual trilha é a melodia (coluna `trilha`). Parte das trilhas foi escolhida por heurística ou palpite, o que fica registrado nas colunas `motivo` e `alternativa`.
