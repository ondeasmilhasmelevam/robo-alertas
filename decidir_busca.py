# -*- coding: utf-8 -*-
"""decidir_busca.py — responde "esta na hora de buscar?"

Por que isso existe
-------------------
O cron do GitHub NAO e confiavel em repositorio gratuito: ele atrasa e, pior,
simplesmente engole execucoes quando a fila esta cheia. Medido em 27/11/2026:
das 4 batidas devidas na noite anterior, so 1 aconteceu — e com 6h33 de atraso.
Cada batida perdida e uma madrugada inteira sem buscar passagem.

O conserto nao e pedir ao GitHub que seja pontual. E parar de depender de uma
unica batida: o workflow passa a bater de 20 em 20 minutos e este programa diz
se ja passou da hora de algum horario do dia e se ele ainda nao foi feito.
Com 90 minutos de tolerancia, o GitHub teria de engolir CINCO batidas seguidas
pra um horario se perder.

Quem lembra o que ja foi feito e o arquivo `ultima_busca.txt`, gravado de volta
no repositorio pelo proprio workflow depois que a busca termina. Ele guarda uma
linha so, no formato `2026-11-27-21`.

Saida: escreve `rodar`, `modo` e `marca` no $GITHUB_OUTPUT.
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
    print(motivo)
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
