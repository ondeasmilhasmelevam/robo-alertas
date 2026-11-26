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
from datetime import datetime

from channels import load_config
from seats_api import SeatsAeroClient
from telegram_bot import TelegramBot
from engine import run_cycle_for_channel, run_melhores_destinos, run_iberia_scan
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
    if not canais:
        _log("Nenhum canal ligado (ou nenhum bateu com o filtro). Nada a fazer.")
        return 1

    cliente = SeatsAeroClient(cfg["seats_api_key"])
    bot = (BotDeTeste() if args.teste
           else TelegramBot(cfg["telegram_bot_token"], ""))
    maximo = cfg.get("max_alerts_per_cycle", 10)

    inicio = time.time()
    rotulo = "COMPLETO" if args.modo == "completo" else "IBERIA/BRITISH/QATAR"
    _log("=" * 58)
    _log(f"CICLO {rotulo} {datetime.now():%d/%m/%Y %H:%M}"
         f"{'  [MODO TESTE — não envia]' if args.teste else ''}")
    _log(f"Canais: {', '.join(c['name'] for c in canais)}")
    _log("=" * 58)

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

    # Arquivo que o site le (alertas_site.json). So tem o que foi enviado
    # de verdade; em --teste o BotDeTeste nao envia, entao nao grava nada.
    try:
        publicar_site.salvar(callback=_log)
    except Exception as e:
        _log(f"[site] Nao deu pra gravar o alertas_site.json: {e}")

    _log("=" * 58)
    _log(f"Ciclo terminado em {(time.time() - inicio) / 60:.1f} min"
         f"{f' — {erros} canal(is) com erro' if erros else ''}")
    # chamadas restantes na API (útil pra saber se o plano está estourando)
    if cliente.remaining_calls is not None:
        _log(f"Chamadas seats.aero restantes hoje: {cliente.remaining_calls}")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
