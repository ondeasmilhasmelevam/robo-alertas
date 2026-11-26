"""
Repost VMM -> Onde As Milhas Me Levam  (userbot Telethon)
=========================================================
Lê as mensagens do grupo "VMM - Passagens Nacionais" (que você participa),
traduz pro nosso formato (vmm_parser) e reposta no NOSSO canal do Telegram
— que por sua vez espelha no Discord automaticamente.

IMPORTANTE — roda com a SUA conta pessoal do Telegram:
  1) pip install telethon
  2) Pegue api_id e api_hash em  https://my.telegram.org  (grátis, 2 min).
  3) Entre no grupo do VMM pela sua conta (pelo link de convite).
  4) Preencha em channels_config.json:
        "telegram_api_id":   123456,
        "telegram_api_hash": "abcdef...",
        "vmm_title_match":   "VMM",                (parte do nome do grupo)
        "repost_target_chat":"-100XXXXXXXXXX"      (canal nosso p/ postar)
  5) 1ª execução:  python repost_vmm.py
        -> vai pedir seu telefone + código do SMS (login único).
        -> cria um arquivo de sessão .session e fica escutando.

Depois é só deixar rodando junto com o bot.
"""

import os
import sys
import json
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("repost_vmm")

from vmm_parser import parse_vmm, format_repost, dedup_key

try:
    from telethon import TelegramClient, events
    TELETHON_OK = True
except ImportError:
    TelegramClient = events = None
    TELETHON_OK = False

# TelegramBot (bot oficial) posta no nosso canal e o discord_bot espelha.
from telegram_bot import TelegramBot

# Para rotear cada alerta pro canal certo (por região de destino).
try:
    from processor import get_destination_region
except Exception:
    def get_destination_region(_):
        return ""


def _region_chat_map(cfg):
    """Monta {regiao -> chat_id} a partir dos SEUS canais habilitados.
    Ex.: europa -> canal Europa, eua -> canal EUA, brasil -> canal Brasil."""
    m = {}
    for ch in cfg.get("channels", []):
        if not ch.get("enabled", True):
            continue
        cid = str(ch.get("chat_id") or "")
        if not cid:
            continue
        for r in ch.get("regions", []):
            m.setdefault(r, cid)
    return m


def _base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _load_cfg():
    path = os.path.join(_base_dir(), "channels_config.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


SEEN_FILE = os.path.join(_base_dir(), "vmm_reposted.json")


def _load_seen():
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def _save_seen(seen):
    try:
        # mantém no máx. 2000 chaves recentes
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(list(seen)[-2000:], f)
    except Exception as e:
        logger.error(f"Erro salvando seen: {e}")


OBS_FILE = os.path.join(_base_dir(), "vmm_observados.jsonl")


def _log_observado(d):
    """Modo observar: grava o valor visto pra você comparar depois."""
    import datetime
    reg = {
        "quando": datetime.datetime.now().isoformat(timespec="seconds"),
        "rota": f"{d['origem']}->{d['destino']}",
        "programa": d.get("programa", ""),
        "milhas_iv": d.get("milhas_total"),
        "custo": d.get("custo"),
    }
    try:
        with open(OBS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(reg, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"Erro salvando observado: {e}")


def _mklog(log_callback):
    def log(msg):
        logger.info(msg)
        if log_callback:
            try:
                log_callback(f"[VMM] {msg}")
            except Exception:
                pass
    return log


async def main(log_callback=None, allow_login=False):
    log = _mklog(log_callback)
    cfg = _load_cfg()
    api_id = cfg.get("telegram_api_id")
    api_hash = cfg.get("telegram_api_hash")
    bot_token = cfg.get("telegram_bot_token", "")
    title_match = (cfg.get("vmm_title_match") or "Passagens").lower()
    target = str(cfg.get("repost_target_chat") or "")
    mode = (cfg.get("repost_mode") or "observe").lower()  # "observe" | "post"
    backfill_n = int(cfg.get("vmm_backfill", 0) or 0)
    region_chat = _region_chat_map(cfg)

    if not api_id or not api_hash:
        log("Userbot desligado: preencha telegram_api_id/hash em channels_config.json.")
        return

    def _post_alert(d):
        """Reposta no canal certo pela REGIÃO do destino (fallback: canal padrão)."""
        chat = region_chat.get(get_destination_region(d["destino"])) or target
        if not chat:
            return False
        return TelegramBot(bot_token, chat).send_message(format_repost(d))

    seen = _load_seen()

    client = TelegramClient(os.path.join(_base_dir(), "repost_vmm.session"), int(api_id), api_hash)
    if allow_login:
        # Rodando NO TERMINAL: permite login interativo (pede telefone + código).
        await client.start()
    else:
        # Rodando dentro do .exe (sem console): usa a sessão salva. Se ela estiver
        # válida, conecta calado. Se precisar logar, falha LIMPO (sem tocar no
        # stdin, que não existe no exe -> evita o crash "lost sys.stdin").
        def _precisa_login(*_a):
            raise RuntimeError("sessão expirada — rode 'python repost_vmm.py' no terminal p/ relogar")
        try:
            await client.start(phone=_precisa_login, code_callback=_precisa_login)
        except Exception as e:
            log(f"Userbot desligado: {e}")
            return
    log("Conectado. Procurando os grupos do VMM...")

    # Descobre o(s) chat(s) cujo título casa com 'title_match'
    alvo_ids = []
    async for dialog in client.iter_dialogs():
        nome = (dialog.name or "").lower()
        if title_match in nome:
            alvo_ids.append(dialog.id)
            log(f"Monitorando: {dialog.name}")
    if not alvo_ids:
        log(f"Nenhum grupo com '{title_match}' no nome. Entre no grupo pela sua conta.")

    # ── BACKFILL: lê o histórico recente pra registrar o padrão de valores ──
    # (histórico é SEMPRE só observado — nunca reposta alertas antigos no canal)
    if backfill_n > 0 and alvo_ids:
        log(f"Lendo histórico (até {backfill_n} msgs/grupo)...")
        novos = 0
        for cid in alvo_ids:
            try:
                async for msg in client.iter_messages(cid, limit=backfill_n):
                    d = parse_vmm(msg.message or "")
                    if not d:
                        continue
                    k = dedup_key(d)
                    if k in seen:
                        continue
                    seen.add(k)
                    _log_observado(d)
                    novos += 1
            except Exception as e:
                logger.error(f"Backfill erro no grupo {cid}: {e}")
        _save_seen(seen)
        log(f"Histórico lido: {novos} alertas registrados em vmm_observados.jsonl")

    @client.on(events.NewMessage(chats=alvo_ids or None))
    async def handler(event):
        try:
            d = parse_vmm(event.message.message or "")
            if not d:
                return
            k = dedup_key(d)
            if k in seen:
                return
            seen.add(k)
            _save_seen(seen)
            linha = f"{d['origem']}->{d['destino']} | {d['milhas_total']} milhas i/v | {d.get('programa','')}"
            if mode == "post":
                if _post_alert(d):
                    log(f"✅ Repostado ({get_destination_region(d['destino']) or 'padrão'}): {linha}")
            else:  # observe
                log(f"👀 OBSERVANDO: {linha}")
                _log_observado(d)
        except Exception as e:
            logger.error(f"Erro no handler: {e}")

    log(f"Modo: {mode.upper()} — escutando VMM ao vivo.")
    await client.run_until_disconnected()


def start_background(log_callback=None):
    """Roda o userbot em um event loop próprio (chamar numa thread daemon).
    Só inicia se telethon existir E já houver sessão salva (login feito).
    Se faltar algo, apenas avisa e sai — nunca trava o app principal."""
    log = _mklog(log_callback)
    if not TELETHON_OK:
        log("Userbot desligado: biblioteca 'telethon' não instalada.")
        return
    if not os.path.exists(os.path.join(_base_dir(), "repost_vmm.session")):
        log("Userbot: sem sessão salva. Rode 'python repost_vmm.py' uma vez para logar.")
        return
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main(log_callback))
    except Exception as e:
        log(f"Userbot parou: {e}")


if __name__ == "__main__":
    try:
        # rodando no terminal -> permite o login interativo (telefone + código)
        asyncio.run(main(allow_login=True))
    except KeyboardInterrupt:
        pass
