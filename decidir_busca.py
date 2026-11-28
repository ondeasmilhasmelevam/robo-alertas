# -*- coding: utf-8 -*-
"""decidir_busca.py — responde "esta na hora de buscar?"

Por que isso existe
-------------------
O cron do GitHub NAO e confiavel em repositorio gratuito. Medido em
27/11/2026: das 4 batidas devidas na noite anterior so 1 aconteceu, com 6h33
de atraso; a das 09:00 UTC saiu as 14:38; e com agendamento de 20 em 20
minutos as batidas das 15:00 e 15:20 nao vieram. Atraso em HORAS — nenhuma
tolerancia em minutos resolve isso. Cada batida perdida e uma madrugada
inteira sem buscar passagem.

Entao o relogio do GitHub nao decide mais nada. O busca.yml fica de PLANTAO
por 5h30 e chama este programa de 5 em 5 minutos; aqui e que se olha a hora de
Brasilia e se responde se algum horario do dia ja passou e ainda nao foi feito.

Quem lembra o que ja foi feito e o arquivo `ultima_busca.txt`, gravado de volta
no repositorio pelo proprio workflow depois que a busca termina. Ele guarda uma
linha so, no formato `2026-11-27-21`.

Saida: a linha `DECISAO=sim|completo|2026-11-27-21` (que o plantao le) e, se a
variavel existir, os mesmos campos no $GITHUB_OUTPUT.
"""
import datetime
import os
import sys
from zoneinfo import ZoneInfo

BRASILIA = ZoneInfo("America/Sao_Paulo")
MARCADOR = "ultima_busca.txt"
COTA = "cota_seats.txt"      # "2026-11-27 412" — gravado pelo run_cycle.py

# Horarios que CEDEM A VEZ quando a cota da seats.aero esta curta, e quanto
# precisa sobrar pra eles rodarem. As 21h e as madrugadas nao cedem: sao hora
# de abertura de assento, perder e perder passagem. As 9h e um reforco pros
# grupos sem Avios — vale a pena, mas nao a ponto de deixar a cota no osso e
# a varredura das 21h ser cortada no meio da paginacao (foi o que aconteceu
# em 27/11/2026, sem ninguem ficar sabendo).
HORARIOS_QUE_CEDEM = {9}
COTA_MINIMA = 250

# Horario de Brasilia -> (o que buscar, quem). Ver o ORCAMENTO DA API no
# busca.yml antes de acrescentar horario: a seats.aero da 1000 chamadas por dia.
#
# O "quem" vazio quer dizer todos os grupos ligados. "sem-avios" quer dizer so
# os grupos que nao tem iberia/british/qatar — hoje America do Norte e Brasil.
# Eles existem porque as quatro varreduras da madrugada sao horario de
# liberacao da familia Avios e pulam esses dois grupos; sem as 9h, eles so
# receberiam passagem uma vez por dia. Custo medido: 18 consultas (~150
# chamadas), contra 48 da varredura completa.
# As 3h sairam em 28/11/2026. Motivo: a varredura completa das 21h foi MEDIDA
# em 598 chamadas (a estimativa no comentario era 350-400, errada em 50%), e
# com ela nesse tamanho o dia nao cabia: na hora das 9h sobravam ~220, abaixo
# do COTA_MINIMA, e a rodada dos grupos sem Avios cedia a vez todo dia. As 3h
# eram o horario mais dispensavel por serem vizinhas das 2h — perde pouca
# abertura e libera ~45 chamadas, o bastante pra sobrar ~267 as 9h.
HORARIOS = [
    (21, "completo", ""),           # 21h: todo mundo
    (0,  "avios",    ""),           # madrugada: horario de liberacao da Avios
    (2,  "avios",    ""),
    (6,  "avios",    ""),
    (9,  "completo", "sem-avios"),  # 9h: a vez dos tres grupos sem Avios
]

# Quanto tempo depois da hora ainda vale correr atras do prejuizo. Passou
# disso, o horario fica pra la: buscar as 23h30 o que era pra ser as 21h ja
# atrapalha o horario seguinte e gasta chamada da API a toa.
# Em funcionamento normal isso nem entra em cena: o plantao olha de 5 em 5
# minutos. A tolerancia e pro caso de a corrente de plantoes ter quebrado e o
# agendamento de reserva ter demorado a religar.
TOLERANCIA_MIN = 90


def ultimo_horario(agora):
    """O horario mais recente que ja passou, com o modo dele."""
    passados = []
    for dias_atras in (1, 0):
        dia = (agora - datetime.timedelta(days=dias_atras)).date()
        for hora, modo, quem in HORARIOS:
            quando = datetime.datetime.combine(dia, datetime.time(hora), BRASILIA)
            if quando <= agora:
                passados.append((quando, hora, modo, quem))
    passados.sort()
    return passados[-1] if passados else None


def ja_feito():
    try:
        with open(MARCADOR, "r", encoding="utf-8") as f:
            return f.read().strip()
    except (IOError, OSError):
        return ""


def cota_de_hoje():
    """Quantas chamadas sobraram, se a anotacao for do dia de hoje.

    A cota da seats.aero vira a meia-noite UTC (21h de Brasilia), por isso a
    comparacao e com o dia UTC. Anotacao de ontem nao vale: devolve None e
    quem chamou segue em frente como se nao soubesse.
    """
    try:
        with open(COTA, "r", encoding="utf-8") as f:
            dia, sobrou = f.read().split()
        if dia == datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"):
            return int(sobrou)
    except (IOError, OSError, ValueError):
        pass
    return None


def responder(rodar, modo, marca, motivo, quem=""):
    """Fala duas vezes: uma pra gente ler e uma pra maquina ler.

    O plantao do busca.yml pega a linha DECISAO= com cut; o $GITHUB_OUTPUT fica
    pra quando isso for chamado como um passo de workflow por conta propria.
    Os campos da linha sao: rodar|modo|marca|quem.
    """
    print(motivo)
    print(f"DECISAO={'sim' if rodar else 'nao'}|{modo}|{marca}|{quem}")
    saida = os.environ.get("GITHUB_OUTPUT")
    if saida:
        with open(saida, "a", encoding="utf-8") as f:
            f.write(f"rodar={'sim' if rodar else 'nao'}\n")
            f.write(f"modo={modo}\n")
            f.write(f"marca={marca}\n")
            f.write(f"quem={quem}\n")


def main():
    agora = datetime.datetime.now(BRASILIA)
    relogio = agora.strftime("%d/%m/%Y %H:%M")

    # Botao "Run workflow": roda na hora, sem consumir horario do dia.
    manual = os.environ.get("MODO_BOTAO", "").strip()
    if manual:
        responder(True, manual, "", f"{relogio} — busca a mao ({manual}).")
        return

    atual = ultimo_horario(agora)
    if not atual:
        responder(False, "", "", f"{relogio} — nenhum horario passou ainda.")
        return

    quando, hora, modo, quem = atual
    marca = f"{quando:%Y-%m-%d}-{hora:02d}"
    atraso = int((agora - quando).total_seconds() // 60)
    de_quem = " (so os grupos sem Avios)" if quem == "sem-avios" else ""

    sobrou = cota_de_hoje()
    cota_curta = (hora in HORARIOS_QUE_CEDEM
                  and sobrou is not None and sobrou < COTA_MINIMA)

    if ja_feito() == marca:
        responder(False, modo, marca,
                  f"{relogio} — o horario das {hora}h ja foi feito.", quem)
    elif cota_curta:
        responder(False, modo, marca,
                  f"{relogio} — o horario das {hora}h cede a vez: so sobraram "
                  f"{sobrou} chamadas da API hoje (minimo {COTA_MINIMA}). "
                  f"A varredura das 21h tem prioridade.", quem)
    elif atraso > TOLERANCIA_MIN:
        responder(False, modo, marca,
                  f"{relogio} — o horario das {hora}h passou faz {atraso} min "
                  f"(limite {TOLERANCIA_MIN}); fica pro proximo.", quem)
    else:
        responder(True, modo, marca,
                  f"{relogio} — esta na hora: {hora}h, busca {modo}{de_quem} "
                  f"({atraso} min de atraso).", quem)


if __name__ == "__main__":
    sys.exit(main())
