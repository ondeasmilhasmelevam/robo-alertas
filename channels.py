"""
Gerenciador de Canais — Salva/carrega configuração de grupos Telegram.
"""

import json
import os

CONFIG_FILE = "channels_config.json"

# Chaves que NUNCA devem ficar em texto puro num repositório. Se a variável de
# ambiente existir, ela vence o que está no arquivo. É assim que o robô roda na
# nuvem (GitHub Actions) sem as chaves estarem no código.
SEGREDOS_ENV = {
    "seats_api_key": "SEATS_API_KEY",
    "telegram_bot_token": "TELEGRAM_BOT_TOKEN",
    "telegram_api_id": "TELEGRAM_API_ID",
    "telegram_api_hash": "TELEGRAM_API_HASH",
    "discord_webhook": "DISCORD_WEBHOOK",
    "rove_session_cookie": "ROVE_SESSION_COOKIE",
    "rove_cookie_header": "ROVE_COOKIE_HEADER",
    "rove_anon_key": "ROVE_ANON_KEY",
    "rove_refresh_token": "ROVE_REFRESH_TOKEN",
    "avios_admin_chat": "AVIOS_ADMIN_CHAT",
}


def aplicar_segredos_do_ambiente(cfg: dict) -> dict:
    """Variável de ambiente sobrepõe o arquivo (nuvem). Sem variável, nada muda."""
    for chave, env in SEGREDOS_ENV.items():
        valor = os.environ.get(env)
        if valor:
            cfg[chave] = valor
    # chat_id de cada canal: CHAT_ID_<NOME_DO_CANAL_EM_MAIUSCULO>
    for ch in cfg.get("channels", []):
        slug = "".join(c if c.isalnum() else "_" for c in ch.get("name", "")).upper()
        valor = os.environ.get(f"CHAT_ID_{slug}")
        if valor:
            ch["chat_id"] = valor
    return cfg

DEFAULT_CHANNEL = {
    "name": "",
    "chat_id": "",
    "regions": [],
    "cabins": ["business"],
    "enabled": True,
}

AVAILABLE_REGIONS = [
    ("brasil", "Brasil (Nacional)"),
    ("europa", "Europa"),
    ("eua", "EUA / Canadá"),
    ("asia", "Ásia / Oriente Médio"),
    ("america_sul", "América do Sul"),
    ("america_central", "América Central / Caribe"),
    ("africa", "África"),
    ("oceania", "Oceania"),
]

AVAILABLE_CABINS = [
    ("economy", "Econômica"),
    ("premium", "Premium Economy"),
    ("business", "Executiva"),
    ("first", "Primeira Classe"),
]


def load_config() -> dict:
    """Carrega configuração do disco."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return aplicar_segredos_do_ambiente(json.load(f))
        except (json.JSONDecodeError, IOError):
            pass

    return aplicar_segredos_do_ambiente({
        "seats_api_key": "",
        "telegram_bot_token": "",
        "origins": ["GIG", "GRU"],
        "check_interval_minutes": 60,
        "max_alerts_per_cycle": 10,
        "channels": [],
    })


def save_config(config: dict):
    """Salva configuração no disco."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
