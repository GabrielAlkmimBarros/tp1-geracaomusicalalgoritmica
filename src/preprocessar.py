import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import mido
import numpy as np
import pretty_midi

PASTA_DADOS = Path("data")
LISTA_MUSICAS = Path("musicas.csv")
SAIDA = Path("corpus_mj.json")

LIMITE_MAX = 4.0  # em tempos (semínimas)

# Múltiplos de 1/4 (semicolcheias) até LIMITE_MAX, mais as tercinas curtas (1/3 e 2/3).
DURACOES_PERMITIDAS = sorted({round(k / 4, 4) for k in range(1, 17)} | {round(1 / 3, 4), round(2 / 3, 4)})
LIMIAR_ORNAMENTO = min(DURACOES_PERMITIDAS) / 2  # abaixo disso a nota é um ornamento
TOLERANCIA_SIMULTANEAS = 1 / 16  # notas que começam a menos disso (em tempos) contam como simultâneas

FASES = {"solo", "solo_infancia", "grupo"}  
CENTRO_OITAVA = 67                          
CANAL_BATERIA = 9                           

# Perfis de Krumhansl-Kessler: peso típico de cada nota numa escala maior / menor
PERFIL_MAIOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
PERFIL_MENOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
NOMES_NOTAS = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


# lista de músicas
def ler_lista(aceitos):
    """leitura do arquivo musicas.csv e monta o MAPA_MELODIA: arquivo -> número da trilha."""
   
    with open(LISTA_MUSICAS, encoding="utf-8-sig") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    mapa = {}
    for linha in linhas:
        if linha["status"].strip() in aceitos and linha["fase"].strip() in FASES:
            mapa[linha["arquivo"].strip()] = (linha["musica"], int(linha["trilha"]))
    return mapa


# leitura
def extrair_notas(midi):
    """percorre as mensagens de todas as trilhas acumulando o tempo absoluto em ticks.
    retorna um dicionário (trilha, canal) -> lista de notas (inicio, fim, altura), com início e fim em TEMPOS (ticks / ticks_por_tempo)."""
    
    tpb = midi.ticks_per_beat
    vozes = {}
    for num_trilha, trilha in enumerate(midi.tracks):
        tempo_abs = 0
        abertas = {}  # (canal, altura) -> instante de início
        for msg in trilha:
            tempo_abs += msg.time
            if msg.type not in ("note_on", "note_off"):
                continue
            chave = (msg.channel, msg.note)
            ligada = msg.type == "note_on" and msg.velocity > 0
            if chave in abertas and (ligada or msg.type == "note_off" or msg.velocity == 0):
                # fecha a nota que estava soando (desligada ou religada)
                inicio = abertas.pop(chave)
                vozes.setdefault((num_trilha, msg.channel), []).append(
                    (inicio / tpb, tempo_abs / tpb, msg.note))
            if ligada:
                abertas[chave] = tempo_abs
    for notas in vozes.values():
        notas.sort()
    return vozes


def trilha_da_melodia(vozes, posicao):
    """retorna a chave (trilha, canal) da melodia, dado o número da trilha no musicas.csv."""
    return sorted(vozes)[posicao - 1]


# melodia
def resolver_simultaneas(notas):
    """Notas que começam no mesmo instante (até TOLERANCIA_SIMULTANEAS de diferença): fica só a mais aguda.
    A tolerância pega acordes "espalhados", em que as notas não começam exatamente juntas."""
    grupos = []
    for nota in sorted(notas):
        if grupos and nota[0] - grupos[-1][0][0] < TOLERANCIA_SIMULTANEAS:
            grupos[-1].append(nota)
        else:
            grupos.append([nota])
    resultado = []
    for grupo in grupos:
        mais_aguda = max(grupo, key=lambda n: n[2])
        resultado.append((grupo[0][0], mais_aguda[1], mais_aguda[2]))  # mantém o início do grupo
    return resultado


def estimar_tonalidade(vozes):
    """Algoritmo de Krumhansl-Schmuckler: soma quanto tempo cada nota soa em todos instrumentos
    compara com o perfil de cada uma das 24 tonalidades. Retorna (tônica 0-11, "maior"/"menor", correlação)."""
   
    duracao_por_nota = np.zeros(12)
    for (_, canal), notas in vozes.items():
        if canal == CANAL_BATERIA:
            continue
        for inicio, fim, altura in notas:
            duracao_por_nota[altura % 12] += fim - inicio
    candidatas = [
        (np.corrcoef(duracao_por_nota, np.roll(perfil, tonica))[0, 1], tonica, modo)
        for tonica in range(12)
        for perfil, modo in ((PERFIL_MAIOR, "maior"), (PERFIL_MENOR, "menor"))
    ]
    r, tonica, modo = max(candidatas)
    return tonica, modo, r


def transpor(notas, tonica, modo):
    """Leva a melodia para Dó maior (ou Lá menor), pelo menor deslocamento possível."""
    alvo = 0 if modo == "maior" else 9
    desloc = (alvo - tonica) % 12
    if desloc > 6:
        desloc -= 12
    return [(inicio, fim, altura + desloc) for inicio, fim, altura in notas]


def ajustar_oitava(notas):
    """Desloca a melodia inteira em oitavas para a altura média ficar perto de CENTRO_OITAVA."""
    media = np.mean([altura for _, _, altura in notas])
    oitavas = round((CENTRO_OITAVA - media) / 12)
    return [(inicio, fim, altura + 12 * oitavas) for inicio, fim, altura in notas]


def calcular_duracoes(notas):
    """A duração é a distancia até o início da próxima nota: a pausa é somada à nota anterior e sobreposições se resolvem sozinhas.
    A última nota usa o próprio fim. O silêncio antes da primeira nota some, porque a sequência começa nela."""

    eventos = []
    for i, (inicio, fim, altura) in enumerate(notas):
        if i + 1 < len(notas):
            duracao = notas[i + 1][0] - inicio
        else:
            duracao = fim - inicio
        eventos.append([altura, duracao])
    return eventos


def limitar_duracao(eventos, contadores):
    """Durações acima de LIMITE_MAX viram LIMITE_MAX"""
    for evento in eventos:
        contadores["total"] += 1
        if evento[1] > LIMITE_MAX:
            evento[1] = LIMITE_MAX
            contadores["cortadas"] += 1
    return eventos


def quantizar(eventos, contadores):
    """Notas mais curtas que LIMIAR_ORNAMENTO são ornamentos: são removidas e o tempo delas é somado à nota anterior (assim a música não fica mais longa nem sai do compasso)"""
    
    fundidos = []
    for altura, duracao in eventos:
        if duracao < LIMIAR_ORNAMENTO and fundidos:
            fundidos[-1][1] += duracao
            contadores["ornamentos"] += 1
        else:
            fundidos.append([altura, duracao])
    for evento in fundidos:
        evento[1] = min(DURACOES_PERMITIDAS, key=lambda d: abs(d - evento[1]))
    return fundidos


# orquestração
def preprocessar_corpus(mapa_melodia, com_transposicao=True, com_oitava=True):
    sequencias = []
    contadores = Counter()
    print(f"{'música':34} {'tom estimado':13} notas")
    for arquivo, (nome, posicao) in mapa_melodia.items():
        try:
            midi = mido.MidiFile(PASTA_DADOS / arquivo, clip=True)
        except Exception as erro:
            print(f"!! {nome}: não abriu ({erro})")
            continue
        vozes = extrair_notas(midi)
        brutas = vozes.get(trilha_da_melodia(vozes, posicao), [])
        if not brutas:
            print(f"!! {nome}: trilha {posicao} sem notas")
            continue

        notas = resolver_simultaneas(brutas)
        tonica, modo, r = estimar_tonalidade(vozes)
        if com_transposicao:
            notas = transpor(notas, tonica, modo)
        if com_oitava:
            notas = ajustar_oitava(notas)
        eventos = calcular_duracoes(notas)
        eventos = limitar_duracao(eventos, contadores)
        eventos = quantizar(eventos, contadores)

        sequencias.append(eventos)
        aviso = "  (tonalidade incerta)" if r < 0.7 else ""
        print(f"{nome[:34]:34} {NOMES_NOTAS[tonica] + ' ' + modo:13} {len(eventos)}{aviso}")
    return sequencias, contadores


def imprimir_estatisticas(sequencias, contadores):
    todas = [tuple(e) for musica in sequencias for e in musica]
    alturas = [a for a, _ in todas]
    brancas = sum(1 for a in alturas if a % 12 in (0, 2, 4, 5, 7, 9, 11)) / len(alturas)
    print(f"\nMúsicas:            {len(sequencias)}")
    print(f"Total de notas:     {len(todas)}")
    print(f"Estados distintos:  {len(set(todas))}")
    print(f"Extensão:           {pretty_midi.note_number_to_name(min(alturas))} "
          f"a {pretty_midi.note_number_to_name(max(alturas))}")
    print(f"Notas nas 'teclas brancas' após transpor: {100 * brancas:.1f}%")
    print(f"Durações cortadas em {LIMITE_MAX:g} tempos: {contadores['cortadas']} "
          f"({100 * contadores['cortadas'] / contadores['total']:.1f}%)")
    print(f"Ornamentos fundidos à nota anterior:      {contadores['ornamentos']} "
          f"({100 * contadores['ornamentos'] / contadores['total']:.1f}%)")
    print("Durações mais comuns (tempos):")
    for d, n in Counter(d for _, d in todas).most_common(6):
        print(f"  {d:<7} {100 * n / len(todas):.1f}%")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--incluir-ouvir", action="store_true",
                   help="inclui também as músicas com status 'ouvir'")
    p.add_argument("--sem-transposicao", action="store_true",
                   help="não transpõe para Dó maior / Lá menor (para o experimento com vs. sem)")
    p.add_argument("--sem-oitava", action="store_true",
                   help="não ajusta a oitava das melodias")
    args = p.parse_args()
    aceitos = {"usar", "ouvir"} if args.incluir_ouvir else {"usar"}

    saida = SAIDA
    if args.sem_transposicao or args.sem_oitava:
        sufixo = "_sem_transposicao" * args.sem_transposicao + "_sem_oitava" * args.sem_oitava
        saida = SAIDA.with_name(SAIDA.stem + sufixo + SAIDA.suffix)

    sequencias, contadores = preprocessar_corpus(ler_lista(aceitos),
                                                 com_transposicao=not args.sem_transposicao,
                                                 com_oitava=not args.sem_oitava)
    saida.write_text(json.dumps(sequencias))
    imprimir_estatisticas(sequencias, contadores)
    print(f"\nCorpus salvo em {saida}")


if __name__ == "__main__":
    main()