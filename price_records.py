"""
Sistema de Preco Recorde
=========================
Salva o menor preco ja visto por rota+programa+cabine.
Quando aparece preco igual ou menor, marca como RECORDE.
"""

import json
import os
import sys
import logging
from datetime import datetime

logger = logging.getLogger("miles_bot")

RECORDS_FILE = "price_records.json"


def _resource_path(f):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, f)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), f)


def _get_records_path():
    # Always save in the working directory, not in _MEIPASS
    return os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), RECORDS_FILE)


class PriceRecords:
    """Gerencia historico de menores precos por rota."""

    def __init__(self):
        self.records = {}
        self._load()

    def _load(self):
        path = _get_records_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.records = json.load(f)
                logger.info(f"Historico de precos: {len(self.records)} rotas registradas")
            except (json.JSONDecodeError, IOError):
                self.records = {}

    def _save(self):
        path = _get_records_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.records, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Erro ao salvar historico de precos: {e}")

    def make_key(self, origin: str, destination: str, source: str, cabin: str) -> str:
        """Chave unica: rota + programa + cabine."""
        return f"{origin}-{destination}|{source}|{cabin}"

    def check_and_update(self, origin: str, destination: str, source: str, cabin: str, cost: int) -> dict:
        """
        Verifica se o preco atual e recorde.

        Retorna:
        {
            "is_record": True/False,
            "is_near_record": True/False,
            "current_price": int,
            "previous_record": int or None,
            "first_seen": bool,
            "record_date": str or None,
        }
        """
        key = self.make_key(origin, destination, source, cabin)
        now = datetime.now().isoformat()

        existing = self.records.get(key)

        if not existing:
            # Primeira vez vendo esta rota
            self.records[key] = {
                "lowest_price": cost,
                "first_seen": now,
                "last_record_date": now,
                "origin": origin,
                "destination": destination,
                "source": source,
                "cabin": cabin,
                "history": [{"price": cost, "date": now}],
            }
            self._save()
            return {
                "is_record": False,  # Primeira vez nao marca como recorde
                "is_near_record": False,
                "current_price": cost,
                "previous_record": None,
                "first_seen": True,
                "record_date": None,
            }

        prev_lowest = existing["lowest_price"]

        # Recorde: preco igual ou menor que o menor ja visto
        if cost <= prev_lowest:
            is_record = cost < prev_lowest
            is_near = False

            existing["lowest_price"] = cost
            existing["last_record_date"] = now

            # Manter historico (max 20 entradas)
            history = existing.get("history", [])
            history.append({"price": cost, "date": now})
            if len(history) > 20:
                history = history[-20:]
            existing["history"] = history

            self.records[key] = existing
            self._save()

            return {
                "is_record": is_record,
                "is_near_record": False,
                "current_price": cost,
                "previous_record": prev_lowest,
                "first_seen": False,
                "record_date": existing.get("last_record_date"),
            }

        # Proximo do recorde: ate 10% acima
        near_threshold = prev_lowest * 1.10
        is_near = cost <= near_threshold

        return {
            "is_record": False,
            "is_near_record": is_near,
            "current_price": cost,
            "previous_record": prev_lowest,
            "first_seen": False,
            "record_date": existing.get("last_record_date"),
        }

    def get_record(self, origin: str, destination: str, source: str, cabin: str) -> dict:
        """Retorna info do recorde para uma rota."""
        key = self.make_key(origin, destination, source, cabin)
        return self.records.get(key, {})

    def get_stats(self) -> dict:
        """Estatisticas do historico."""
        total = len(self.records)
        if total == 0:
            return {"total_routes": 0}

        records_with_history = sum(1 for r in self.records.values() if len(r.get("history", [])) > 1)
        return {
            "total_routes": total,
            "routes_with_updates": records_with_history,
        }
