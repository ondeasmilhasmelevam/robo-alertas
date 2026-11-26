"""
Espelho para Discord (Webhook)
==============================
Reenvia para um canal do Discord tudo que o bot manda pro Telegram.
Nao depende de nenhum outro modulo do bot (evita import circular).

Uso: o TelegramBot chama discord_bot.mirror(texto) apos enviar. O webhook
e lido UMA vez de channels_config.json ("discord_webhook"). Se estiver
vazio, tudo vira no-op (nada quebra).
"""

import os
import sys
import json
import time
import logging

import requests

logger = logging.getLogger("miles_bot")

DISCORD_MAX = 1900        # limite real e 2000; folga p/ seguranca
_USERNAME = "Onde As Milhas Me Levam"

_webhook_url = None       # cache
_loaded = False


def _config_dir():
    """Pasta onde fica o channels_config.json (ao lado do .exe, ou do script)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _load_webhook():
    global _webhook_url, _loaded
    if _loaded:
        return _webhook_url
    _loaded = True
    for base in (_config_dir(), os.getcwd()):
        path = os.path.join(base, "channels_config.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            url = (cfg.get("discord_webhook") or "").strip()
            if url:
                _webhook_url = url
                logger.info("Discord: espelho de alertas ATIVO.")
                return _webhook_url
        except (OSError, json.JSONDecodeError):
            continue
    logger.info("Discord: sem webhook configurado (espelho desligado).")
    return None


def set_webhook(url):
    """Permite definir/trocar o webhook em runtime (opcional)."""
    global _webhook_url, _loaded
    _webhook_url = (url or "").strip() or None
    _loaded = True


def _chunks(text):
    """Quebra respeitando quebras de linha e o limite do Discord."""
    if len(text) <= DISCORD_MAX:
        return [text]
    parts, cur = [], []
    ln = 0
    for line in text.split("\n"):
        if ln + len(line) + 1 > DISCORD_MAX and cur:
            parts.append("\n".join(cur))
            cur, ln = [line], len(line)
        else:
            cur.append(line)
            ln += len(line) + 1
    if cur:
        parts.append("\n".join(cur))
    return parts


def send(text, webhook_url=None):
    """Envia texto pro Discord. Retorna True/False. Nunca levanta excecao."""
    url = webhook_url or _load_webhook()
    if not url or not text:
        return False
    ok = True
    for chunk in _chunks(text):
        payload = {"content": chunk, "username": _USERNAME}
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 429:  # rate limited
                try:
                    retry = float(r.json().get("retry_after", 1))
                except Exception:
                    retry = 1.0
                time.sleep(min(retry, 5))
                r = requests.post(url, json=payload, timeout=10)
            if r.status_code >= 400:
                logger.error(f"Discord {r.status_code}: {r.text[:200]}")
                ok = False
        except requests.exceptions.RequestException as e:
            logger.error(f"Discord erro de envio: {e}")
            ok = False
        time.sleep(0.4)  # respiro entre chunks
    return ok


def mirror(text):
    """Atalho seguro chamado pelo TelegramBot. No-op se nao houver webhook."""
    try:
        if _load_webhook():
            send(text)
    except Exception as e:  # espelho jamais pode derrubar o envio principal
        logger.error(f"Discord mirror falhou: {e}")
