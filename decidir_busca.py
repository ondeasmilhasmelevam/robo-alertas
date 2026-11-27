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

# Horario de Brasilia -> o que buscar. Ver o ORCAMENTO DA API no busca.yml
# antes de acrescentar horario: a conta da seats.aero da 1000 chamadas por dia.
HORARIOS = [(21, "completo"), (0, "avios"), (2, "avios"), (3, "avios"), (6, "avios")]

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
        for hora, modo in HORARIOS:
            quando = datetime.datetime.combine(dia, datetime.time(hora), BRASILIA)
            if quando <= agora:
                passados.append((quando, hora, modo))
    passados.sort()
    return passados[-1] if passados else None


def ja_feito():
    try:
        with open(MARCADOR, "r", encoding="utf-8") as f:
            return f.read().strip()
    except (IOError, OSError):
        return ""


def responder(rodar, modo, marca, motivo):
    """Fala duas vezes: uma pra gente ler e uma pra maquina ler.

    O plantao do busca.yml pega a linha DECISAO= com cut; o $GITHUB_OUTPUT fica
    pra quando isso for chamado como um passo de workflow por conta propria.
    """
    print(motivo)
    print(f"DECISAO={'sim' if rodar else 'nao'}|{modo}|{marca}")
    saida = os.environ.get("GITHUB_OUTPUT")
    if saida:
        with open(saida, "a", encoding="utf-8") as f:
            f.write(f"rodar={'sim' if rodar else 'nao'}\n")
            f.write(f"modo={modo}\n")
            f.write(f"marca={marca}\n")


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

    quando, hora, modo = atual
    marca = f"{quando:%Y-%m-%d}-{hora:02d}"
    atraso = int((agora - quando).total_seconds() // 60)

    if ja_feito() == marca:
        responder(False, modo, marca, f"{relogio} — o horario das {hora}h ja foi feito.")
    elif atraso > TOLERANCIA_MIN:
        responder(False, modo, marca,
                  f"{relogio} — o horario das {hora}h passou faz {atraso} min "
                  f"(limite {TOLERANCIA_MIN}); fica pro proximo.")
    else:
        responder(True, modo, marca,
                  f"{relogio} — esta na hora: {hora}h, busca {modo} "
                  f"({atraso} min de atraso).")


if __name__ == "__main__":
    sys.exit(main())
