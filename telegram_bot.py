"""
Bot Telegram — v2
==================
Envia alertas formatados para grupo privado.
"""

import requests
import logging
import time

try:
    import discord_bot  # espelho opcional para o Discord
except Exception:
    discord_bot = None

logger = logging.getLogger("miles_bot")

TELEGRAM_API = "https://api.telegram.org/bot{token}"


class TelegramBot:

    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = TELEGRAM_API.format(token=token)

    def send_message(self, text: str, silent: bool = False, _mirror: bool = True) -> bool:
        """Envia mensagem de texto. Tenta com parse_mode e sem se falhar."""
        # Espelha pro Discord (uma vez; o Discord faz o proprio split).
        if _mirror and discord_bot is not None:
            discord_bot.mirror(text)

        url = f"{self.base_url}/sendMessage"

        # Telegram tem limite de 4096 caracteres por mensagem
        if len(text) > 4000:
            return self._send_long_message(text, silent)

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_notification": silent,
            "disable_web_page_preview": True,
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            data = resp.json()

            if data.get("ok"):
                return True

            error = data.get("description", "")
            logger.error(f"Erro Telegram: {error}")
            return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao enviar Telegram: {e}")
            return False

    def _send_long_message(self, text: str, silent: bool) -> bool:
        """Divide mensagens longas em partes."""
        lines = text.split("\n")
        chunks = []
        current = []
        current_len = 0

        for line in lines:
            if current_len + len(line) + 1 > 3800:
                chunks.append("\n".join(current))
                current = [line]
                current_len = len(line)
            else:
                current.append(line)
                current_len += len(line) + 1

        if current:
            chunks.append("\n".join(current))

        success = True
        for i, chunk in enumerate(chunks):
            if i > 0:
                time.sleep(1)
            # _mirror=False: o texto completo ja foi espelhado pro Discord.
            if not self.send_message(chunk, silent, _mirror=False):
                success = False

        return success

    def send_batch(self, messages: list[str], delay: float = 1.5) -> int:
        """Envia várias mensagens com delay. Retorna quantas enviou."""
        sent = 0
        for i, msg in enumerate(messages):
            if self.send_message(msg, silent=(i > 0)):
                sent += 1
            if i < len(messages) - 1:
                time.sleep(delay)
        return sent

    def test_connection(self) -> bool:
        """Testa se o bot funciona e envia mensagem de confirmação."""
        try:
            url = f"{self.base_url}/getMe"
            resp = requests.get(url, timeout=10)
            info = resp.json()
            if not info.get("ok"):
                logger.error("Token inválido!")
                return False

            bot_name = info["result"].get("username", "?")
            logger.info(f"Bot conectado: @{bot_name}")

            return self.send_message(
                "✅ Bot de Alertas de Milhas conectado!\n\n"
                "Monitoramento de executiva ativo.\n"
                "Alertas serão enviados aqui automaticamente."
            )

        except Exception as e:
            logger.error(f"Falha no teste: {e}")
            return False
