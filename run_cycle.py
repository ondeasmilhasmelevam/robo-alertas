# -*- coding: utf-8 -*-
"""
run_cycle.py — Um ciclo de busca, SEM interface gráfica.
===========================================================
É a porta de entrada pra rodar na nuvem (GitHub Actions, VPS, cron): executa
uma varredura do seats.aero em todos os canais ligados, manda os alertas e sai.
O painel continua existindo pra uso local; isto aqui é o mesmo motor sem janela.

NÃO inclui o Avios.com — aquele precisa de Chrome logado e só roda no PC.

Uso:
    python run_cycle.py                 # ciclo completo, envia de verdade
    python run_cycle.py --modo avios    # so Iberia/British/Qatar (bem mais barato)
    python run_cycle.py --teste         # roda tudo mas NÃO envia (só mostra)
    python run_cycle.py --canal Europa  # só os canais cujo nome contém "Europa"
    python run_cycle.py --sem-md        # pula a parte de Melhores Destinos

As chaves saem de variáveis de ambiente quando existirem (SEATS_API_KEY,
TELEGRAM_BOT_TOKEN, ...); senão, do channels_config.json. Ver channels.py.
"""
import argparse
import logging
import sys
import time
from datetime import datetime, timezone

from channels import load_config
from seats_api import SeatsAeroClient
from telegram_bot import TelegramBot
from engine import (run_cycle_for_channel, run_melhores_destinos, run_iberia_scan,
                    iniciar_cache_do_ciclo, encerrar_cache_do_ciclo)
import publicar_site


def _log(msg=""):
    print(f"{datetime.now():%H:%M:%S}  {msg}", flush=True)


class BotDeTeste:
    """Fica no lugar do TelegramBot em --teste: mostra em vez de enviar."""

    def __init__(self, token="", chat_id=""):
        self.token = token or "teste"
        self.chat_id = chat_id
        self.enviados = 0

    def send_message(self, text, silent=False, _mirror=True):
        self.enviados += 1
        _log(f"[NÃO ENVIADO — modo teste] chat {self.chat_id}:")
        print(text, flush=True)
        print("-" * 60, flush=True)
        return True

    def send_batch(self, messages, delay=0.0):
        for m in messages:
            self.send_message(m)
        return len(messages)

    def for_chat(self, chat_id=""):
        outro = BotDeTeste(self.token, chat_id)
        return outro

    def test_connection(self):
        return True


def main():
    ap = argparse.ArgumentParser(description="Um ciclo de busca de milhas, sem interface.")
    ap.add_argument("--teste", action="store_true", help="não envia nada, só mostra")
    ap.add_argument("--canal", default="", help="filtra canais pelo nome (texto parcial)")
    ap.add_argument("--sem-md", action="store_true", help="pula Melhores Destinos")
    ap.add_argument("--modo", choices=["completo", "avios"], default="completo",
                    help="completo = todos os programas (~350 chamadas da API); "
                         "avios = so Iberia/British/Qatar (~70). A conta da "
                         "seats.aero da 1000 chamadas por dia, por isso existem "
                         "os dois: 5 varreduras completas por dia nao cabem.")
    ap.add_argument("--grupos-sem-avios", action="store_true",
                    help="so os grupos que NAO tem iberia/british/qatar. A "
                         "varredura avios pula esses grupos (nao ha o que "
                         "buscar neles), entao sem isso eles so seriam "
                         "atendidos uma vez por dia, na varredura completa.")
    args = ap.parse_args()

    # O console do Windows nasce em cp1252 e engasga nos emoji do alerta
    # ("charmap codec can't encode"), o que derrubava o ciclo inteiro no meio.
    # No Linux do GitHub Actions isso nao acontece, mas aqui sim.
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    logging.basicConfig(level=logging.WARNING,
                        format="%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%H:%M:%S")

    cfg = load_config()
    if not cfg.get("seats_api_key"):
        _log("ERRO: falta a chave do seats.aero (SEATS_API_KEY ou channels_config.json).")
        return 2
    if not args.teste and not cfg.get("telegram_bot_token"):
        _log("ERRO: falta o token do Telegram (TELEGRAM_BOT_TOKEN).")
        return 2

    canais = [c for c in cfg.get("channels", []) if c.get("enabled", True)]
    if args.canal:
        alvo = args.canal.lower()
        canais = [c for c in canais if alvo in c.get("name", "").lower()]
    if args.grupos_sem_avios:
        # Quais grupos sao esses sai da propria configuracao, nao de uma lista
        # escrita a mao: se um dia voce ligar iberia/british/qatar no grupo do
        # Brasil, ele sai daqui sozinho e passa a ser atendido pelas quatro
        # varreduras avios da madrugada.
        from engine import SCHEDULED_SCAN_SOURCES
        canais = [c for c in canais
                  if not any(s in (c.get("programs") or [])
                             for s in SCHEDULED_SCAN_SOURCES)]
    if not canais:
        _log("Nenhum canal ligado (ou nenhum bateu com o filtro). Nada a fazer.")
        return 1

    cliente = SeatsAeroClient(cfg["seats_api_key"])
    bot = (BotDeTeste() if args.teste
           else TelegramBot(cfg["telegram_bot_token"], ""))
    maximo = cfg.get("max_alerts_per_cycle", 10)

    inicio = time.time()
    rotulo = "COMPLETO" if args.modo == "completo" else "IBERIA/BRITISH/QATAR"
    if args.grupos_sem_avios:
        rotulo += " (so os grupos sem Avios)"
    _log("=" * 58)
    _log(f"CICLO {rotulo} {datetime.now():%d/%m/%Y %H:%M}"
         f"{'  [MODO TESTE — não envia]' if args.teste else ''}")
    _log(f"Canais: {', '.join(c['name'] for c in canais)}")
    _log("=" * 58)

    # Uma busca na API serve todos os grupos: a consulta nao muda de canal
    # pra canal, so o recorte depois. Com os 5 grupos ligados isso corta 45%
    # das chamadas (90 consultas viram 49).
    uniao = iniciar_cache_do_ciclo(canais)
    if uniao and len(canais) > 1:
        _log(f"Cache do ciclo ligado ({len(uniao)} origens no total)")

    erros = 0
    if args.modo == "avios":
        # Varredura focada: so os 3 programas da familia Avios. E a que roda nos
        # horarios de liberacao (eles abrem assento as 0h, 2h, 3h, 6h e 21h) e
        # custa um quinto das chamadas de uma varredura completa.
        origens = cfg.get("origins", ["GIG", "GRU"])
        try:
            run_iberia_scan(client=cliente, bot=bot, channels=canais,
                            origins=origens, max_alerts=maximo, callback=_log)
        except Exception as e:
            erros += 1
            _log(f"ERRO na varredura Iberia/British/Qatar: {e}")
    else:
        for canal in canais:
            origens = canal.get("origins") or cfg.get("origins", ["GIG", "GRU"])
            try:
                run_cycle_for_channel(client=cliente, bot=bot, channel=canal,
                                      origins=origens, max_alerts=maximo,
                                      callback=_log)
            except Exception as e:
                erros += 1
                _log(f"[{canal['name']}] ERRO: {e}")

    if args.modo == "completo" and not args.sem_md and cfg.get("melhores_destinos_enabled"):
        try:
            run_melhores_destinos(bot, canais, callback=_log)
        except Exception as e:
            _log(f"[Melhores Destinos] ERRO: {e}")

    encerrar_cache_do_ciclo()

    # Arquivo que o site le (alertas_site.json). So tem o que foi enviado
    # de verdade; em --teste o BotDeTeste nao envia, entao nao grava nada.
    try:
        publicar_site.salvar(callback=_log)
    except Exception as e:
        _log(f"[site] Nao deu pra gravar o alertas_site.json: {e}")

    _log("=" * 58)
    _log(f"Ciclo terminado em {(time.time() - inicio) / 60:.1f} min"
         f"{f' — {erros} canal(is) com erro' if erros else ''}")
    # Quanto sobrou da cota do dia. Fica gravado em cota_seats.txt porque cada
    # busca é um processo novo: sem o arquivo, a busca seguinte não teria como
    # saber que a cota está no fim. É isso que o decidir_busca.py lê pra deixar
    # o horário das 9h (o único que não é abertura de assento) ceder a vez
    # quando a cota está curta. Em 27/11/2026 a cota zerou no meio do dia e a
    # busca foi cortada na metade da paginação, sem ninguém ficar sabendo.
    if cliente.remaining_calls is not None:
        _log(f"Chamadas seats.aero restantes hoje: {cliente.remaining_calls}")
        try:
            with open("cota_seats.txt", "w", encoding="utf-8") as f:
                f.write(f"{datetime.now(timezone.utc):%Y-%m-%d} "
                        f"{cliente.remaining_calls}\n")
        except OSError:
            pass
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
