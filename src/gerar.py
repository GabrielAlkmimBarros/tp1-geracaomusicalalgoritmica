

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

import pretty_midi

INICIO = ("INICIO", 0)  # estado artificial que marca o começo de cada música


# treinamento
def treinar(corpus, ordem_max):
    """
    Conta as transições para TODAS as ordens de 0 até ordem_max.
    As ordens menores são usadas no backoff (quando um contexto nunca foi visto).

    modelos[k][contexto] = Counter({proximo_estado: quantas_vezes})
    contexto é uma tupla com os k estados anteriores (k = 0 -> tupla vazia).
    """
    modelos = [defaultdict(Counter) for _ in range(ordem_max + 1)]
    for musica in corpus:
        # Coloca ordem_max estados INICIO na frente: assim o modelo também
        # aprende como as músicas costumam começar.
        seq = [INICIO] * ordem_max + [tuple(e) for e in musica]
        for i in range(ordem_max, len(seq)):
            for k in range(ordem_max + 1):
                contexto = tuple(seq[i - k:i])
                modelos[k][contexto][seq[i]] += 1
    return modelos


# geração
def sortear(contador, rng):
    estados = list(contador.keys())
    pesos = list(contador.values())
    return rng.choices(estados, weights=pesos, k=1)[0]


def gerar(modelos, ordem, total_tempos, rng):
    """
    Gera estados até a melodia somar total_tempos tempos.
    Retorna a melodia e quantas vezes foi preciso fazer backoff.
    """
    historico = [INICIO] * ordem
    melodia = []
    backoffs = 0
    tempos = 0.0
    while tempos < total_tempos:
        # Tenta o contexto de ordem n; se nunca foi visto, tenta n-1, n-2, ... 0
        for k in range(ordem, -1, -1):
            contexto = tuple(historico[len(historico) - k:]) if k > 0 else ()
            if contexto in modelos[k]:
                break
            backoffs += 1
        proximo = sortear(modelos[k][contexto], rng)
        melodia.append(proximo)
        historico.append(proximo)
        tempos += proximo[1]
    return melodia, backoffs


# saída MIDI
def salvar_midi(melodia, caminho, bpm, instrumentos=(0,)):
    """
    instrumentos: números de programa General MIDI (0 = piano, 40 = violino, 73 = flauta).
    Cada instrumento toca a mesma melodia; a partir do segundo, a linha é
    deslocada uma oitava (alternando abaixo e acima) para não soar idêntica.
    """
    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    seg_por_tempo = 60.0 / bpm
    deslocamentos = [0, -12, 12, -24]  # oitava de cada instrumento, na ordem
    for i, programa in enumerate(instrumentos):
        desloc = deslocamentos[i % len(deslocamentos)]
        inst = pretty_midi.Instrument(program=programa, name=f"MELODY_{i}")
        t = 0.0
        for altura, dur in melodia:
            # A duração do estado é o espaço até a próxima nota (inclui pausa).
            # A nota soa por no máximo 2 tempos; o resto vira silêncio.
            soando = min(dur, 2.0) * 0.9 * seg_por_tempo
            inst.notes.append(pretty_midi.Note(velocity=90, pitch=int(altura) + desloc,
                                               start=t, end=t + soando))
            t += dur * seg_por_tempo
        pm.instruments.append(inst)
    pm.write(str(caminho))


# main
def main():
    p = argparse.ArgumentParser(description="Gera melodias pop com cadeia de Markov")
    p.add_argument("--ordem", type=int, default=2, help="ordem da cadeia (memória)")
    p.add_argument("--quantas", type=int, default=10, help="quantas melodias gerar")
    p.add_argument("--semente", type=int, default=0, help="semente da primeira melodia")
    p.add_argument("--tempos", type=float, default=64, help="tamanho em tempos (64 = 16 compassos)")
    p.add_argument("--bpm", type=float, default=100, help="andamento do MIDI gerado")
    p.add_argument("--instrumentos", default="0", help="programas General MIDI separados por vírgula, ex.: 0,40,73")
    p.add_argument("--corpus", default="corpus_mj.json", help="arquivo JSON com o corpus de músicas (Michael Jackson)")
    args = p.parse_args()

    corpus = json.loads(Path(args.corpus).read_text())
    instrumentos = [int(x) for x in args.instrumentos.split(",")]
    print(f"Treinando cadeia de ordem {args.ordem} com {len(corpus)} músicas...")
    modelos = treinar(corpus, args.ordem)
    print(f"Contextos de ordem {args.ordem} aprendidos: {len(modelos[args.ordem])}\n")

    pasta = Path("saida")
    pasta.mkdir(exist_ok=True)
    for semente in range(args.semente, args.semente + args.quantas):
        rng = random.Random(semente)  # mesma semente -> mesma melodia (reprodutível)
        melodia, backoffs = gerar(modelos, args.ordem, args.tempos, rng)
        prefixo = Path(args.corpus).stem.replace("corpus", "").strip("_")
        prefixo = f"{prefixo}_" if prefixo else ""
        caminho = pasta / f"{prefixo}ordem{args.ordem}_semente{semente}.mid"
        salvar_midi(melodia, caminho, args.bpm, instrumentos)
        inicio = " ".join(pretty_midi.note_number_to_name(a) for a, _ in melodia[:10])
        print(f"{caminho}: {len(melodia)} notas, {backoffs} backoffs | {inicio} ...")


if __name__ == "__main__":
    main()