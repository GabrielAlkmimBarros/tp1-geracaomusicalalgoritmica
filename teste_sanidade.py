"""Teste de sanidade do pré-processamento.

Para cada música escolhida do corpus (corpus_mj.json):
  1. confere se os eventos são válidos (altura 0-127, duração entre 0 e LIMITE_MAX);
  2. reconstrói um arquivo MIDI a partir da sequência (nota, duração);
  3. relê o MIDI escrito e confere se altura e duração batem com a sequência.

Depois é só ouvir os arquivos da pasta de saída: a melodia deve ser reconhecível
(em outra tonalidade, por causa da transposição, e sem pausas, por causa do legato).

A função sequencia_para_midi pode ser reaproveitada para salvar as músicas geradas.
"""
import argparse
import json
import sys
from pathlib import Path

import pretty_midi

CORPUS = Path("corpus_mj.json")
PASTA_SAIDA = Path("sanidade")

LIMITE_MAX = 4.0   # o mesmo valor usado no pré-processamento
RESOLUCAO = 480    # ticks por tempo; divisível por 3 e por 4, então semicolcheias e tercinas ficam exatas
TOLERANCIA = 0.01  # em tempos, ao comparar durações na releitura


def sequencia_para_midi(eventos, caminho, andamento=100, programa=0):
    """Grava um MIDI com uma única voz. eventos: lista de [altura, duracao em tempos].
    Cada nota soa até a próxima começar (legato), como a duração foi definida no pré-processamento.
    Retorna a duração total em tempos."""
    segundos_por_tempo = 60.0 / andamento
    pm = pretty_midi.PrettyMIDI(initial_tempo=andamento, resolution=RESOLUCAO)
    voz = pretty_midi.Instrument(program=programa)
    inicio = 0.0
    for altura, duracao in eventos:
        fim = inicio + duracao
        voz.notes.append(pretty_midi.Note(velocity=90, pitch=int(altura),
                                          start=inicio * segundos_por_tempo,
                                          end=fim * segundos_por_tempo))
        inicio = fim
    pm.instruments.append(voz)
    pm.write(str(caminho))
    return inicio


def verificar_eventos(eventos):
    """Problemas encontrados na sequência (lista vazia = tudo certo)."""
    problemas = []
    if not eventos:
        return ["sequência vazia"]
    for i, (altura, duracao) in enumerate(eventos):
        if not (isinstance(altura, int) and 0 <= altura <= 127):
            problemas.append(f"evento {i}: altura inválida ({altura})")
        if not (0 < duracao <= LIMITE_MAX):
            problemas.append(f"evento {i}: duração fora de (0, {LIMITE_MAX:g}] ({duracao})")
    return problemas


def comparar_releitura(eventos, caminho, andamento):
    """Lê o MIDI gravado e compara alturas e durações com a sequência original."""
    pm = pretty_midi.PrettyMIDI(str(caminho))
    notas = sorted(pm.instruments[0].notes, key=lambda n: n.start) if pm.instruments else []
    if len(notas) != len(eventos):
        return [f"número de notas diferente: gravei {len(eventos)}, li {len(notas)}"]

    tempos_por_segundo = andamento / 60.0
    inicios = [n.start * tempos_por_segundo for n in notas]
    # duração = distância até o início da próxima nota (a última usa o próprio fim)
    duracoes = [inicios[i + 1] - inicios[i] for i in range(len(notas) - 1)]
    duracoes.append((notas[-1].end - notas[-1].start) * tempos_por_segundo)

    problemas = []
    for i, ((altura, duracao), nota, dur_lida) in enumerate(zip(eventos, notas, duracoes)):
        if nota.pitch != altura:
            problemas.append(f"evento {i}: altura {altura} virou {nota.pitch}")
        if abs(dur_lida - duracao) > TOLERANCIA:
            problemas.append(f"evento {i}: duração {duracao} virou {dur_lida:.3f}")
    return problemas


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--corpus", type=Path, default=CORPUS)
    p.add_argument("--saida", type=Path, default=PASTA_SAIDA)
    p.add_argument("--indices", type=int, nargs="*",
                   help="posições das músicas no corpus (0 = primeira do musicas.csv); padrão: todas")
    p.add_argument("--andamento", type=float, default=100, help="batidas por minuto")
    p.add_argument("--programa", type=int, default=0, help="instrumento MIDI (0 = piano)")
    args = p.parse_args()

    corpus = json.loads(args.corpus.read_text())
    indices = args.indices if args.indices else range(len(corpus))
    args.saida.mkdir(exist_ok=True)

    print(f"{'índice':>6} {'notas':>6} {'tempos':>8} {'compassos':>9}  {'extensão':13} resultado")
    falhas = 0
    for i in indices:
        eventos = corpus[i]
        problemas = verificar_eventos(eventos)
        if not problemas:
            caminho = args.saida / f"musica_{i:02d}.mid"
            total = sequencia_para_midi(eventos, caminho, args.andamento, args.programa)
            problemas = comparar_releitura(eventos, caminho, args.andamento)
            alturas = [a for a, _ in eventos]
            extensao = (f"{pretty_midi.note_number_to_name(min(alturas))}-"
                        f"{pretty_midi.note_number_to_name(max(alturas))}")
            print(f"{i:>6} {len(eventos):>6} {total:>8.1f} {total / 4:>9.1f}  {extensao:13} "
                  f"{'OK' if not problemas else 'ERRO'}")
        else:
            print(f"{i:>6} {len(eventos):>6} {'-':>8} {'-':>9}  {'-':13} ERRO")
        for pb in problemas[:5]:
            print(f"         {pb}")
        if len(problemas) > 5:
            print(f"         ... e mais {len(problemas) - 5} problema(s)")
        falhas += bool(problemas)

    print(f"\nMIDIs gravados em {args.saida}/  ->  ouça e confira se as melodias são reconhecíveis.")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
