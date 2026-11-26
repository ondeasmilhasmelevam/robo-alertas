"""
Motor Inteligente de Precificacao v1
=======================================
Substitui tetos fixos por analise historica adaptativa.
Aprende padroes de preco por rota e identifica oportunidades reais.
"""

import json
import os
import sys
import math
import logging
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger("miles_bot")

PRICING_FILE = "pricing_history.json"
MIN_OBSERVATIONS = 3  # Minimo de observacoes para usar baseline
MAX_HISTORY_PER_ROUTE = 100  # Maximo de entradas por rota


def _get_path():
    return os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), PRICING_FILE)


class SmartPricing:
    """Motor inteligente de precificacao baseado em historico."""

    def __init__(self):
        self.data = {}
        self._load()

    def _load(self):
        p = _get_path()
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                logger.info(f"SmartPricing: {len(self.data)} rotas no historico")
            except:
                self.data = {}

    def _save(self):
        try:
            with open(_get_path(), "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False)
        except IOError as e:
            logger.error(f"SmartPricing: erro ao salvar: {e}")

    def _key(self, origin, destination, source, cabin):
        return f"{origin}|{destination}|{source}|{cabin}"

    def record_price(self, origin, destination, source, cabin, cost):
        """Registra um preco observado (mesmo que nao seja enviado)."""
        key = self._key(origin, destination, source, cabin)
        now = datetime.now().isoformat()

        if key not in self.data:
            self.data[key] = {
                "origin": origin, "destination": destination,
                "source": source, "cabin": cabin,
                "prices": [], "stats": {},
            }

        entry = self.data[key]
        entry["prices"].append({"cost": cost, "date": now})

        # Limitar historico
        if len(entry["prices"]) > MAX_HISTORY_PER_ROUTE:
            entry["prices"] = entry["prices"][-MAX_HISTORY_PER_ROUTE:]

        # Recalcular stats
        self._update_stats(key)

    def _update_stats(self, key):
        """Recalcula estatisticas para uma rota."""
        entry = self.data[key]
        prices = [p["cost"] for p in entry["prices"]]

        if not prices:
            entry["stats"] = {}
            return

        prices_sorted = sorted(prices)
        n = len(prices_sorted)

        entry["stats"] = {
            "count": n,
            "min": prices_sorted[0],
            "max": prices_sorted[-1],
            "mean": round(sum(prices) / n),
            "median": prices_sorted[n // 2],
            "p25": prices_sorted[max(0, n // 4)],
            "p75": prices_sorted[min(n - 1, 3 * n // 4)],
            "p10": prices_sorted[max(0, n // 10)],
            "p90": prices_sorted[min(n - 1, 9 * n // 10)],
            "std": round(self._std(prices)),
            "last_update": datetime.now().isoformat(),
        }

    def _std(self, values):
        """Desvio padrao."""
        if len(values) < 2: return 0
        mean = sum(values) / len(values)
        return math.sqrt(sum((x - mean) ** 2 for x in values) / (len(values) - 1))

    def evaluate(self, origin, destination, source, cabin, cost):
        """
        Avalia se um preco e uma boa oportunidade.

        Retorna:
        {
            "decision": "send" | "skip" | "fallback",
            "score": float (0-100, quanto maior melhor a oportunidade),
            "reason": str,
            "stats": dict (estatisticas da rota),
            "classification": "espetacular" | "muito_bom" | "bom" | "normal" | "caro" | "outlier",
        }
        """
        key = self._key(origin, destination, source, cabin)
        entry = self.data.get(key, {})
        stats = entry.get("stats", {})
        count = stats.get("count", 0)

        # Registrar o preco observado
        self.record_price(origin, destination, source, cabin, cost)

        # Se nao tem historico suficiente, usa fallback
        if count < MIN_OBSERVATIONS:
            return {
                "decision": "fallback",
                "score": 50,
                "reason": f"Historico insuficiente ({count}/{MIN_OBSERVATIONS} obs)",
                "stats": stats,
                "classification": "desconhecido",
            }

        # Calcular score baseado na posicao no historico
        p_min = stats["min"]
        p_mean = stats["mean"]
        p_median = stats["median"]
        p25 = stats["p25"]
        p75 = stats["p75"]
        p10 = stats["p10"]
        p90 = stats["p90"]
        std = stats["std"]

        # ── Classificacao ──────────────────────────────────────
        if cost <= p10:
            classification = "espetacular"
            score = 95
        elif cost <= p25:
            classification = "muito_bom"
            score = 80
        elif cost <= p_median:
            classification = "bom"
            score = 65
        elif cost <= p75:
            classification = "normal"
            score = 40
        elif cost <= p90:
            classification = "caro"
            score = 20
        else:
            classification = "outlier"
            score = 5

        # ── Ajuste por proximidade ao minimo historico ──────────
        if p_min > 0:
            ratio = cost / p_min
            if ratio <= 1.0:
                score = min(100, score + 10)  # Novo recorde!
            elif ratio <= 1.05:
                score = min(100, score + 5)   # Muito proximo do recorde
            elif ratio >= 3.0:
                score = max(0, score - 20)    # 3x o minimo = muito inflado

        # ── Ajuste por desvio padrao ────────────────────────────
        if std > 0:
            z_score = (cost - p_mean) / std
            if z_score < -1.5:
                score = min(100, score + 10)  # Muito abaixo da media
            elif z_score > 2.0:
                score = max(0, score - 15)    # Muito acima da media

        # ── Decisao ─────────────────────────────────────────────
        if classification in ("espetacular", "muito_bom"):
            decision = "send"
            reason = f"Oportunidade! Preco no {classification} (score {score})"
        elif classification == "bom":
            decision = "send"
            reason = f"Bom preco, abaixo da mediana (score {score})"
        elif classification == "normal":
            decision = "skip"
            reason = f"Preco normal, acima da mediana (score {score})"
        elif classification == "caro":
            decision = "skip"
            reason = f"Preco caro, acima do P75 (score {score})"
        else:  # outlier
            decision = "skip"
            reason = f"Outlier! Preco muito acima do padrao (score {score})"

        return {
            "decision": decision,
            "score": score,
            "reason": reason,
            "stats": stats,
            "classification": classification,
        }

    def evaluate_ida_volta(self, origin, dest, source, cabin, cost_ida, cost_volta):
        """
        Avalia se a combinacao IDA + VOLTA faz sentido.
        Evita enviar ida boa + volta absurda.
        """
        eval_ida = self.evaluate(origin, dest, source, cabin, cost_ida)
        eval_volta = self.evaluate(dest, origin, source, cabin, cost_volta)

        ida_ok = eval_ida["decision"] in ("send", "fallback")
        volta_ok = eval_volta["decision"] in ("send", "fallback")

        # Se ida e boa mas volta e outlier/cara
        if ida_ok and not volta_ok:
            if eval_volta["classification"] in ("outlier", "caro"):
                return {
                    "send_ida": True,
                    "send_volta": False,
                    "reason": f"Ida otima ({cost_ida:,}), mas volta inflada ({cost_volta:,}). Enviando so ida.",
                    "ida_eval": eval_ida,
                    "volta_eval": eval_volta,
                }

        # Se ambas sao boas
        if ida_ok and volta_ok:
            return {
                "send_ida": True,
                "send_volta": True,
                "reason": "Ida e volta com bons precos!",
                "ida_eval": eval_ida,
                "volta_eval": eval_volta,
            }

        # Se nenhuma e boa
        return {
            "send_ida": ida_ok,
            "send_volta": volta_ok,
            "reason": f"Ida: {eval_ida['classification']}, Volta: {eval_volta['classification']}",
            "ida_eval": eval_ida,
            "volta_eval": eval_volta,
        }

    def save_periodically(self):
        """Chama ao final de cada ciclo para persistir dados."""
        self._save()

    def get_route_stats(self, origin, destination, source, cabin):
        """Retorna stats de uma rota especifica."""
        key = self._key(origin, destination, source, cabin)
        return self.data.get(key, {}).get("stats", {})

    def get_summary(self):
        """Resumo geral do historico."""
        total = len(self.data)
        with_baseline = sum(1 for v in self.data.values() if v.get("stats", {}).get("count", 0) >= MIN_OBSERVATIONS)
        total_prices = sum(len(v.get("prices", [])) for v in self.data.values())
        return {
            "total_routes": total,
            "routes_with_baseline": with_baseline,
            "total_observations": total_prices,
        }
