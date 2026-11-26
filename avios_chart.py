# -*- coding: utf-8 -*-
"""
Tabela oficial de Avios por DISTÂNCIA (época baixa / off-peak) — Iberia Plus.
Por trecho. Regra do usuário: só alertar o PISO de época baixa de cada cabine
(o valor mais baixo), conforme a BANDA DE DISTÂNCIA da rota — calculada
automaticamente (Haversine) a partir das coordenadas dos aeroportos.

Colunas da tabela -> cabines internas:
  Básica            -> economy   (a econômica mais barata)
  Turista Premium   -> premium
  Business Confort  -> business
(Confort fica de fora: não é o piso da econômica.)
"""
import math

# (min_mi, max_mi, {economy, premium, business})  — valores época baixa, por trecho
OFFPEAK_BANDS = [
    (0,    650,   {"economy": 3500,  "premium": None,  "business": 9750}),
    (651,  1150,  {"economy": 6500,  "premium": None,  "business": 16500}),
    (1151, 2000,  {"economy": 9500,  "premium": None,  "business": 22000}),
    (2001, 3000,  {"economy": 10500, "premium": None,  "business": 23000}),
    (3001, 4000,  {"economy": 16000, "premium": 29500, "business": 40500}),
    (4001, 5500,  {"economy": 20000, "premium": 36750, "business": 50500}),
    (5501, 6500,  {"economy": 24000, "premium": 44000, "business": 60500}),
    (6501, 7000,  {"economy": 28250, "premium": 51000, "business": 70500}),
    (7001, 99999, {"economy": 41000, "premium": 71000, "business": 97000}),
]

# Coordenadas (lat, lon) dos aeroportos. Origens BR + destinos comuns.
# Basta adicionar aqui pra cobrir uma rota nova — a banda sai sozinha.
AIRPORT_COORDS = {
    # Brasil
    "GIG": (-22.81, -43.25), "GRU": (-23.43, -46.47), "VCP": (-23.01, -47.13),
    "SSA": (-12.91, -38.33), "REC": (-8.13, -34.92), "FOR": (-3.78, -38.53),
    "BSB": (-15.87, -47.92), "CNF": (-19.63, -43.97), "POA": (-29.99, -51.17),
    "BEL": (-1.38, -48.48), "NAT": (-5.91, -35.25), "SDU": (-22.91, -43.16),
    # Europa
    "MAD": (40.47, -3.56), "BCN": (41.30, 2.08), "LHR": (51.47, -0.45),
    "AMS": (52.31, 4.76), "LIS": (38.77, -9.13), "CDG": (49.01, 2.55),
    "FCO": (41.80, 12.25), "FRA": (50.03, 8.57), "MXP": (45.63, 8.72),
    "DUB": (53.42, -6.27), "ORY": (48.72, 2.38),
    # América do Sul (destinos/origens vizinhos)
    "EZE": (-34.82, -58.54), "AEP": (-34.56, -58.42), "SCL": (-33.39, -70.79),
    "LIM": (-12.02, -77.11), "BOG": (4.70, -74.15), "MVD": (-34.84, -56.03),
    "ASU": (-25.24, -57.52), "UIO": (-0.13, -78.36), "GYE": (-2.16, -79.88),
    "CCS": (10.60, -66.99), "VVI": (-17.64, -63.14),
    "MDE": (6.17, -75.43), "PTY": (9.07, -79.38), "PUJ": (18.57, -68.36),
    "SJO": (9.99, -84.21),
    "CBB": (-17.42, -66.18), "ROS": (-32.90, -60.79), "COR": (-31.32, -64.21),
    # América do Norte
    "MIA": (25.79, -80.29), "JFK": (40.64, -73.78), "MCO": (28.43, -81.31),
    # Oriente Médio / Ásia (p/ Avios via parceiros — futuro)
    "DXB": (25.25, 55.36), "DOH": (25.27, 51.61), "AUH": (24.43, 54.65),
}

# Distâncias OFICIAIS da Iberia (o site mostra os Avios por elas). Usamos estas
# no lugar da geodésica porque várias rotas caem em cima da fronteira de banda
# (ex.: VVI 5.538 e ASU 5.707 entram na banda 7 por pouco).
_OFICIAIS_MAD = {
    "MDE": 4988,   # Medellín
    "LIM": 5916,   # Lima
    "SCL": 6657,   # Santiago
    "EZE": 6264,   # Buenos Aires
    "MVD": 6178,   # Montevidéu
    "ROS": 6243,   # Rosário
    "COR": 6290,   # Córdoba
    "ASU": 5707,   # Assunção
    "VVI": 5538,   # Santa Cruz de la Sierra
    "CBB": 5662,   # Cochabamba
    "UIO": 5426,   # Quito
    "PTY": 5066,   # Cidade do Panamá
    "PUJ": 4080,   # Punta Cana
}

ROUTE_MILES_OVERRIDE = {}
for _o, _mi in _OFICIAIS_MAD.items():
    ROUTE_MILES_OVERRIDE[(_o, "MAD")] = _mi
    ROUTE_MILES_OVERRIDE[("MAD", _o)] = _mi


# ---------------------------------------------------------------------------
# QATAR AIRWAYS (resgate Avios pelo Iberia Club) — tabela por REGIÃO, não por
# distância. Vale para voos DIRETOS com origem/destino DOHA operados pela QR.
# Valores por trajeto, ÉPOCA BAIXA (o sistema só alerta o piso).
# ---------------------------------------------------------------------------
QATAR_OFFPEAK = {
    "africa1":   {"economy": 17500, "business": 35000, "first": 52500},
    "africa2":   {"economy": 22500, "business": 45000, "first": 67500},
    "america1":  {"economy": 35000, "business": 70000, "first": 105000},
    "america2":  {"economy": 35000, "business": 70000, "first": 105000},
    "asia1":     {"economy": 25000, "business": 50000, "first": 75000},
    "asia2":     {"economy": 30000, "business": 60000, "first": 90000},
    "asia_austral": {"economy": 35000, "business": 70000, "first": 105000},
    "europa1":   {"economy": 17500, "business": 35000, "first": 52500},
    "europa2":   {"economy": 21500, "business": 43000, "first": 64500},
    "levante":   {"economy": 13000, "business": 26000, "first": 39000},
    "medio_oriente": {"economy": 7000, "business": 14000, "first": 21000},
    "sul_asia1": {"economy": 13000, "business": 26000, "first": 39000},
    "sul_asia2": {"economy": 17500, "business": 35000, "first": 52500},
}

# Aeroporto -> região da tabela Qatar (o outro ponto do trecho; Doha é o hub).
QATAR_REGIONS = {
    # América 2 (inclui o BRASIL — GRU é o ponto da Qatar no país)
    "GRU": "america2", "EZE": "america2", "MIA": "america2", "ATL": "america2",
    "LAX": "america2", "DFW": "america2", "ORD": "america2", "SEA": "america2",
    "IAH": "america2", "SFO": "america2",
    # América 1
    "JFK": "america1", "BOS": "america1", "IAD": "america1", "PHL": "america1",
    "YUL": "america1", "YYZ": "america1",
    # Europa 2
    "MAD": "europa2", "BCN": "europa2", "LHR": "europa2", "LGW": "europa2",
    "LIS": "europa2", "CDG": "europa2", "FCO": "europa2", "AMS": "europa2",
    "FRA": "europa2", "MUC": "europa2", "MXP": "europa2", "DUB": "europa2",
    "ZRH": "europa2", "VIE": "europa2", "CPH": "europa2", "ARN": "europa2",
    "OSL": "europa2", "PRG": "europa2", "WAW": "europa2", "MAN": "europa2",
    "EDI": "europa2", "BRU": "europa2", "GVA": "europa2", "AGP": "europa2",
    # Europa 1
    "IST": "europa1", "SAW": "europa1", "ATH": "europa1", "AYT": "europa1",
    "ESB": "europa1", "OTP": "europa1", "SOF": "europa1", "TBS": "europa1",
    "LCA": "europa1", "ALA": "europa1",
    # Médio Oriente
    "DXB": "medio_oriente", "AUH": "medio_oriente", "BAH": "medio_oriente",
    "RUH": "medio_oriente", "JED": "medio_oriente", "MCT": "medio_oriente",
    "KWI": "medio_oriente", "SHJ": "medio_oriente",
    # Ásia
    "BKK": "asia1", "SIN": "asia1", "KUL": "asia1", "HKG": "asia1",
    "SGN": "asia1", "HAN": "asia1", "HKT": "asia1", "PEK": "asia1",
    "NRT": "asia2", "HND": "asia2", "ICN": "asia2", "CGK": "asia2",
    "MNL": "asia2", "DPS": "asia2", "PVG": "asia2",
    "SYD": "asia_austral", "MEL": "asia_austral", "BNE": "asia_austral",
    "PER": "asia_austral", "AKL": "asia_austral", "ADL": "asia_austral",
    # Subcontinente / Levante / África
    "BOM": "sul_asia1", "DEL": "sul_asia1", "AMD": "sul_asia1", "GOI": "sul_asia1",
    "KHI": "sul_asia1", "LHE": "sul_asia1", "ISB": "sul_asia1",
    "BLR": "sul_asia2", "MAA": "sul_asia2", "CCU": "sul_asia2", "HYD": "sul_asia2",
    "CMB": "sul_asia2", "DAC": "sul_asia2", "MLE": "sul_asia2", "KTM": "sul_asia2",
    "CAI": "levante", "AMM": "levante", "BEY": "levante", "ADD": "levante",
    "SSH": "levante", "KRT": "levante",
    "NBO": "africa1", "DAR": "africa1", "EBB": "africa1", "KGL": "africa1",
    "ZNZ": "africa1", "JRO": "africa1", "TUN": "africa1", "SEZ": "africa1",
    "JNB": "africa2", "CPT": "africa2", "DUR": "africa2", "LOS": "africa2",
    "ABV": "africa2", "ACC": "africa2", "LAD": "africa2", "CMN": "africa2",
    "MPM": "africa2", "HRE": "africa2", "LUN": "africa2", "WDH": "africa2",
}

QATAR_HUB = "DOH"


def qatar_floor(origin, dest, cabin):
    """
    Piso Qatar (época baixa) quando o trecho toca Doha. Sem premium economy
    nessa tabela. Devolve None se a rota não for Qatar/região desconhecida.
    """
    if QATAR_HUB not in (origin, dest):
        return None
    outro = dest if origin == QATAR_HUB else origin
    reg = QATAR_REGIONS.get(outro)
    if not reg:
        return None
    return QATAR_OFFPEAK.get(reg, {}).get(cabin)


def _haversine_mi(a, b):
    R = 3958.7613  # raio da Terra em milhas terrestres
    lat1, lon1 = a
    lat2, lon2 = b
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def route_miles(origin, dest):
    """Distância da rota em milhas (override -> geodésica -> None)."""
    if (origin, dest) in ROUTE_MILES_OVERRIDE:
        return ROUTE_MILES_OVERRIDE[(origin, dest)]
    a, b = AIRPORT_COORDS.get(origin), AIRPORT_COORDS.get(dest)
    if a and b:
        return _haversine_mi(a, b)
    return None


def band_for_miles(mi):
    for lo, hi, vals in OFFPEAK_BANDS:
        if lo <= mi <= hi:
            return vals
    return OFFPEAK_BANDS[-1][2]


def offpeak_floor(origin, dest, cabin):
    """
    Piso de época baixa (Avios/trecho) da cabine.
    - Trecho tocando Doha  -> tabela QATAR (por região).
    - Demais (Iberia)      -> tabela por banda de distância.
    """
    q = qatar_floor(origin, dest, cabin)
    if q is not None:
        return q
    mi = route_miles(origin, dest)
    if mi is None:
        return None
    return band_for_miles(mi).get(cabin)


def rate_avios(origin, dest, cabin, miles):
    """
    Classifica o preço contra o PISO de época baixa da rota:
      <= 90% do piso  -> 'espetacular' (promo abaixo do off-peak!)
      <= piso         -> 'muito_bom'   (época baixa: o melhor esperado)
      acima do piso   -> None          (época alta / tarifa mais cara -> NÃO alerta)
    """
    floor = offpeak_floor(origin, dest, cabin)
    if floor is None:
        return None
    if miles <= floor * 0.9:
        return "espetacular"
    if miles <= floor:
        return "muito_bom"
    return None
