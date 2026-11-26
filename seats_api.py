"""
Cliente da API seats.aero — v2
===============================
Busca disponibilidade e detalhes de voos (trips).
"""

import requests
import logging
import time
from typing import Optional

logger = logging.getLogger("miles_bot")

BASE_URL = "https://seats.aero/partnerapi"


class SeatsAeroClient:

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Partner-Authorization": api_key,
            "Accept": "application/json",
        })
        self.remaining_calls = None

    def cached_search(
        self,
        origin: str,
        destination: str = "",
        cabin: str = "",
        sources: str = "",
        start_date: str = "",
        end_date: str = "",
        take: int = 500,
    ) -> list[dict]:
        """Busca por rota específica."""
        params = {"origin_airport": origin, "take": take}
        if destination:
            params["destination_airport"] = destination
        if cabin:
            params["cabin"] = cabin
        if sources:
            params["sources"] = sources
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return self._get("/search", params)

    def bulk_availability(
        self,
        source: str,
        cabin: str = "",
        start_date: str = "",
        end_date: str = "",
        origin_region: str = "",
        destination_region: str = "",
        take: int = 500,
    ) -> list[dict]:
        """Busca em massa por programa de milhas."""
        params = {"source": source, "take": take}
        if cabin:
            params["cabin"] = cabin
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if origin_region:
            params["origin_region"] = origin_region
        if destination_region:
            params["destination_region"] = destination_region
        return self._get("/availability", params)

    def get_trips(self, availability_id: str) -> list[dict]:
        """
        Busca detalhes dos voos (trips) para validar datas.
        Retorna lista de segmentos com datas, companhias, etc.
        """
        url = f"{BASE_URL}/trips/{availability_id}"
        logger.debug(f"GET {url}")
        try:
            resp = self.session.get(url, timeout=30)
            self._update_remaining(resp)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            if isinstance(data, list):
                return data
            return [data] if isinstance(data, dict) else []
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao buscar trips/{availability_id}: {e}")
            return []

    # Máximo de páginas por consulta. take=1000 * 15 = ate 15 mil registros —
    # suficiente para cobrir o ANO INTEIRO de um programa (ex: Iberia despeja
    # award de varias cidades para o ano todo e passa fácil de 1000 registros).
    MAX_PAGES = 15

    def _get(self, endpoint: str, params: dict) -> list[dict]:
        """
        Faz GET paginando via cursor até esgotar os resultados.
        A API seats.aero devolve no máximo 1000 registros por página e um
        cursor/hasMore para continuar. Sem isso, so víamos a 1a pagina e
        cortávamos datas (problema típico da Iberia, cheia de disponibilidade).
        """
        url = f"{BASE_URL}{endpoint}"
        params = dict(params)  # copia — nao mexe no dict do chamador
        all_data: list[dict] = []

        for page in range(self.MAX_PAGES):
            logger.debug(f"GET {url} | params={params}")
            try:
                resp = self.session.get(url, params=params, timeout=30)
                self._update_remaining(resp)
                resp.raise_for_status()
                payload = resp.json()
            except requests.exceptions.HTTPError as e:
                if resp.status_code == 429:
                    logger.warning("⚠️ Rate limit! Aguarde reset à meia-noite UTC.")
                else:
                    logger.error(f"Erro HTTP {resp.status_code}: {e}")
                break
            except requests.exceptions.RequestException as e:
                logger.error(f"Erro de conexão: {e}")
                break

            if isinstance(payload, dict):
                data = payload.get("data", [])
                if isinstance(data, list):
                    all_data.extend(data)
                cursor = payload.get("cursor")
                has_more = payload.get("hasMore", False)
            elif isinstance(payload, list):
                all_data.extend(payload)
                cursor = None
                has_more = False
            else:
                break

            # Sem mais paginas, ou API nao mandou cursor -> encerra.
            if not has_more or not cursor:
                break
            # Protege o orcamento diario de chamadas: nao pagina se estiver no fim.
            if self.remaining_calls is not None and self.remaining_calls < 5:
                logger.warning("⚠️ Rate limit baixo — parando paginação.")
                break

            params["cursor"] = cursor
            time.sleep(0.3)  # respiro entre paginas

        return all_data

    def _update_remaining(self, resp):
        val = resp.headers.get("X-Ratelimit-Remaining")
        if val:
            self.remaining_calls = int(val)
            if self.remaining_calls < 20:
                logger.warning(f"⚠️ Apenas {self.remaining_calls} chamadas API restantes hoje!")
