"""
Histórico de Alertas — v3
===========================
Evita enviar o mesmo alerta duas vezes.
Novo: rastreia o menor preço enviado por rota+programa nos últimos dias.
Só envia preço novo se for IGUAL OU MENOR que o melhor já enviado recentemente.
"""

import json
import os
import hashlib
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("miles_bot")

# Dias para considerar o menor preco enviado como referencia.
# Apos esse periodo, reseta e aceita qualquer preco bom de novo.
BEST_PRICE_MEMORY_DAYS = 7


class AlertHistory:

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.history: dict[str, dict] = {}
        self.best_prices: dict[str, dict] = {}  # menor preco enviado por rota+programa
        self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Compatibilidade: se o arquivo antigo nao tem best_prices
                if isinstance(data, dict) and "best_prices" in data:
                    self.history = data.get("alerts", {})
                    self.best_prices = data.get("best_prices", {})
                else:
                    # Formato antigo: tudo era history
                    self.history = data
                    self.best_prices = {}
                logger.debug(f"Histórico: {len(self.history)} alertas | {len(self.best_prices)} rotas rastreadas")
            except (json.JSONDecodeError, IOError):
                self.history = {}
                self.best_prices = {}

    def _save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump({
                    "alerts": self.history,
                    "best_prices": self.best_prices,
                }, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Erro ao salvar histórico: {e}")

    def _route_key(self, alert: dict) -> str:
        """Chave da ROTA+PROGRAMA+CABINE (sem preço/datas). Identifica a combinação."""
        return f"{alert['origin']}-{alert['destination']}|{alert['source']}|{alert.get('cabin','business')}"

    def make_key(self, alert: dict) -> str:
        """
        Chave baseada em rota + programa + custo.
        Quando o custo muda, gera um novo alerta (pode ser promoção!).
        As datas são um hash — se novas datas aparecem, alerta de novo.
        """
        dates_str = "|".join(
            d["date"] for d in sorted(alert.get("dates", []), key=lambda x: x["date"])
        )
        dates_hash = hashlib.md5(dates_str.encode()).hexdigest()[:8]

        return (
            f"{alert['origin']}-{alert['destination']}-"
            f"{alert['source']}-{alert['miles']}-{dates_hash}"
        )

    def is_new(self, alert: dict) -> bool:
        """Retorna True se este alerta ainda não foi enviado."""
        key = self.make_key(alert)
        return key not in self.history

    def is_price_worth_sending(self, alert: dict) -> bool:
        """
        Verifica se o preço vale a pena enviar comparado com o melhor
        que já enviamos recentemente para esta rota+programa.

        Regras:
        - Se nunca enviamos pra essa rota: ENVIA (primeira vez)
        - Se o último envio foi há mais de BEST_PRICE_MEMORY_DAYS dias: ENVIA (resetou)
        - Se o preço atual é MENOR OU IGUAL ao melhor enviado: ENVIA (preço melhorou)
        - Se o preço atual é MAIOR que o melhor enviado: BLOQUEIA (regressão)
        """
        rk = self._route_key(alert)
        best = self.best_prices.get(rk)

        if not best:
            return True  # Primeira vez, envia

        # Verificar se expirou
        last_sent = best.get("sent_at", "2000-01-01")
        try:
            last_dt = datetime.fromisoformat(last_sent)
            if datetime.now() - last_dt > timedelta(days=BEST_PRICE_MEMORY_DAYS):
                return True  # Expirou, reseta
        except:
            return True

        # Comparar preço
        best_miles = best.get("miles", 0)
        current_miles = alert.get("miles", 0)

        if current_miles <= best_miles:
            return True  # Preço igual ou melhor, envia

        # Preço pior que o melhor recente — bloqueia
        return False

    def mark_sent(self, alert: dict):
        """Marca como enviado e atualiza o melhor preço da rota."""
        key = self.make_key(alert)
        now = datetime.now().isoformat()
        self.history[key] = {
            "sent_at": now,
            "route": f"{alert['origin']}->{alert['destination']}",
            "source": alert["source"],
            "miles": alert["miles"],
        }
        self._update_best_price(alert, now)
        self._save()

    def mark_batch(self, alerts: list[dict]):
        """Marca vários como enviados e atualiza melhores preços."""
        now = datetime.now().isoformat()
        for a in alerts:
            key = self.make_key(a)
            self.history[key] = {
                "sent_at": now,
                "route": f"{a['origin']}->{a['destination']}",
                "source": a["source"],
                "miles": a["miles"],
            }
            self._update_best_price(a, now)
        self._save()

    def _update_best_price(self, alert: dict, now: str):
        """Atualiza o registro do melhor preço enviado para esta rota+programa."""
        rk = self._route_key(alert)
        current_miles = alert.get("miles", 0)
        existing = self.best_prices.get(rk)

        if not existing or current_miles <= existing.get("miles", 999999999):
            self.best_prices[rk] = {
                "miles": current_miles,
                "sent_at": now,
                "route": f"{alert['origin']}->{alert['destination']}",
                "source": alert["source"],
                "cabin": alert.get("cabin", "business"),
            }

    def get_best_price(self, origin, destination, source, cabin="business"):
        """Retorna o melhor preço enviado recentemente para uma rota."""
        rk = f"{origin}-{destination}|{source}|{cabin}"
        return self.best_prices.get(rk)

    def cleanup(self, days: int = 14):
        """Remove registros antigos de alertas e best_prices expirados."""
        cutoff = datetime.now() - timedelta(days=days)
        before = len(self.history)

        self.history = {
            k: v for k, v in self.history.items()
            if datetime.fromisoformat(v.get("sent_at", "2000-01-01")) > cutoff
        }

        # Limpar best_prices expirados (usa BEST_PRICE_MEMORY_DAYS)
        bp_cutoff = datetime.now() - timedelta(days=BEST_PRICE_MEMORY_DAYS)
        before_bp = len(self.best_prices)
        self.best_prices = {
            k: v for k, v in self.best_prices.items()
            if datetime.fromisoformat(v.get("sent_at", "2000-01-01")) > bp_cutoff
        }

        removed = before - len(self.history)
        removed_bp = before_bp - len(self.best_prices)
        if removed > 0 or removed_bp > 0:
            logger.info(f"Limpeza: {removed} alertas antigos | {removed_bp} best_prices expirados")
            self._save()
