"""
Servico de Distancia entre Aeroportos
=======================================
Calcula distancia usando Haversine e classifica na faixa correta.
"""

import json
import math
import os
import sys
import logging

logger = logging.getLogger("miles_bot")

# ── Faixas de distancia (em milhas nauticas) ──────────────────
DISTANCE_BANDS = [
    (1, 0, 650),
    (2, 651, 1150),
    (3, 1151, 2000),
    (4, 2001, 3000),
    (5, 3001, 4000),
    (6, 4001, 5500),
    (7, 5501, 6500),
    (8, 6501, 7000),
    (9, 7001, 999999),
]

# ── Tabela de precos por faixa (por trecho) ───────────────────
# Chave: faixa -> cabine -> (baixa_temporada, alta_temporada)
FARE_TABLE = {
    1: {
        "economy":  (3500, 4750),
        "comfort":  (7000, 8750),
        "premium":  (None, None),
        "business": (9750, 11500),
    },
    2: {
        "economy":  (6500, 8000),
        "comfort":  (12500, 14000),
        "premium":  (None, None),
        "business": (16500, 18250),
    },
    3: {
        "economy":  (9500, 10750),
        "comfort":  (16000, 18750),
        "premium":  (None, None),
        "business": (22000, 24000),
    },
    4: {
        "economy":  (10500, 12000),
        "comfort":  (17000, 20750),
        "premium":  (None, None),
        "business": (23000, 31000),
    },
    5: {
        "economy":  (16000, 19500),
        "comfort":  (25000, 31500),
        "premium":  (29500, 40250),
        "business": (40500, 59000),
    },
    6: {
        "economy":  (20000, 24250),
        "comfort":  (31250, 39000),
        "premium":  (36750, 50500),
        "business": (50500, 74000),
    },
    7: {
        "economy":  (24000, 29250),
        "comfort":  (37250, 46500),
        "premium":  (44000, 60500),
        "business": (60500, 88500),
    },
    8: {
        "economy":  (28250, 34250),
        "comfort":  (42750, 54000),
        "premium":  (51000, 70500),
        "business": (70500, 103500),
    },
    9: {
        "economy":  (41000, 49250),
        "comfort":  (60000, 75000),
        "premium":  (71000, 97000),
        "business": (97000, 140000),
    },
}

# ── Cache de aeroportos ───────────────────────────────────────
_airports_cache = None


def _resource_path(filename):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


def _load_airports() -> dict:
    global _airports_cache
    if _airports_cache is not None:
        return _airports_cache

    path = _resource_path("airports.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            _airports_cache = json.load(f)
    except FileNotFoundError:
        logger.error(f"airports.json nao encontrado em {path}")
        _airports_cache = {}

    return _airports_cache


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Distancia em MILHAS TERRESTRES (statute miles) entre dois pontos.

    CORRIGIDO 25/11/2026: usava 3440.065 (raio em milhas NAUTICAS), mas a tabela
    de faixas da Iberia/British/Qatar (FARE_TABLE) e em milhas TERRESTRES. Como
    nautica e ~13% menor, varias rotas caiam numa faixa abaixo da real e o limite
    ficava apertado demais, cortando alerta bom: GRU-LHR e LIM-MAD iam pra faixa
    6 em vez da 7, SCL-MAD pra 7 em vez da 8, GIG-EZE pra 2 em vez da 3.
    """
    R = 3958.7613  # Raio da Terra em milhas terrestres

    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    return R * c


def get_distance(origin: str, destination: str) -> float:
    """
    Retorna distancia em milhas entre dois aeroportos (codigos IATA).
    Retorna -1 se algum aeroporto nao for encontrado.
    """
    airports = _load_airports()
    orig = airports.get(origin.upper())
    dest = airports.get(destination.upper())

    if not orig or not dest:
        return -1

    # Distancia OFICIAL da Iberia quando conhecida (avios_chart) — rotas em cima
    # da fronteira de faixa nao podem depender do calculo geodesico.
    try:
        import avios_chart
        oficial = avios_chart.ROUTE_MILES_OVERRIDE.get((origin.upper(), destination.upper()))
        if oficial:
            return float(oficial)
    except Exception:
        pass

    return haversine_miles(orig["lat"], orig["lon"], dest["lat"], dest["lon"])


def get_band(distance: float) -> int:
    """Retorna a faixa (1-9) para uma distancia em milhas."""
    for band, min_d, max_d in DISTANCE_BANDS:
        if min_d <= distance <= max_d:
            return band
    return 9  # fallback para distancias muito grandes


def get_fare_limits(band: int, cabin: str) -> tuple:
    """
    Retorna (baixa_temporada, alta_temporada) para uma faixa e cabine.
    cabin: economy, comfort, premium, business
    """
    band_data = FARE_TABLE.get(band, {})

    # Mapear cabines da API para nossas cabines
    cabin_map = {
        "economy": "economy",
        "comfort": "comfort",
        "premium": "premium",
        "business": "business",
        "first": "business",  # primeira classe usa tabela de business
    }

    mapped = cabin_map.get(cabin, "economy")
    limits = band_data.get(mapped, (None, None))

    return limits


def is_distance_award(
    cost: int,
    origin: str,
    destination: str,
    cabin: str = "business",
) -> tuple:
    """
    Verifica se um preco e award usando o sistema de faixas por distancia.

    Retorna: (is_award: bool, band: int, distance: float, low_fare: int, high_fare: int)

    Logica:
    - Se custo <= preco baixa temporada -> award (otimo preco!)
    - Se custo <= preco alta temporada -> award (bom preco)
    - Se custo > preco alta temporada -> rejeitar
    """
    distance = get_distance(origin, destination)
    if distance < 0:
        return (False, 0, 0, 0, 0)

    band = get_band(distance)
    low_fare, high_fare = get_fare_limits(band, cabin)

    if low_fare is None or high_fare is None:
        return (False, band, distance, 0, 0)

    is_good = cost <= high_fare

    return (is_good, band, distance, low_fare, high_fare)


def classify_price(cost: int, low_fare: int, high_fare: int) -> str:
    """Classifica o preco encontrado."""
    if low_fare <= 0:
        return "desconhecido"
    if cost <= low_fare * 0.7:
        return "espetacular"
    if cost <= low_fare:
        return "muito_bom"
    if cost <= high_fare:
        return "bom"
    if cost <= high_fare * 1.2:
        return "normal"
    return "caro"
