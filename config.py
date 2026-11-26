"""
⚙️ Configurações do Bot de Alertas de Milhas — v3
===================================================
Tetos baseados no Termômetro de Preços (nível BOM ou melhor).
"""

# ─── SEATS.AERO ─────────────────────────────────────────────
SEATS_API_KEY = "SUA_API_KEY_AQUI"

# ─── TELEGRAM ────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = "SEU_TOKEN_AQUI"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID_AQUI"

# ─── FILTROS ─────────────────────────────────────────────────

ORIGINS = ["GIG", "GRU"]
DESTINATIONS = []
CABIN = "business"

SOURCES = [
    "azul", "smiles", "aeroplan", "american", "delta", "united",
    "emirates", "turkish", "qatar", "singapore", "flyingblue",
    "lufthansa", "virginatlantic", "copa", "jetblue", "alaska",
    "qantas", "etihad", "finnair", "iberia", "latam", "tap",
]

# Regiões alvo
TARGET_REGIONS = ["europa", "eua", "asia", "america_sul"]

# Máximo de alertas por ciclo POR CABINE
MAX_ALERTS_PER_CYCLE = 10

# ─── REGRAS DE AWARD — TERMÔMETRO DE PREÇOS ──────────────────
# Tetos = nível "BOM" do termômetro (por trecho).
# Só envia alerta se o preço for MENOR OU IGUAL ao teto.
# Ofertas "Espetacular" e "Muito Bom" passam automaticamente.

AWARD_RULES = {

    # ═══════════════════════════════════════════════════════════
    # EUROPA
    # ═══════════════════════════════════════════════════════════

    # Europa — Executiva (Bom ou melhor)
    # Espetacular: 32,35k Avios
    # Muito bom: 84k Flying Club | 82,5k Avios | 240k Latam | 100k SUMA
    # Bom: 260k Latam | 420k Smiles
    # [GUIA] Avios GRU->Europa ~77-90k (zona OW 6 / LATAM 90k). ConnectMiles
    #        AmSul->Europa = 35k (chart). Aeroplan SA->Atlantico 55-75k.
    "europa_business": {
        "iberia":          40_000,   # Avios — espetacular/muito bom
        "american":        90_000,   # [GUIA] Avios GRU->Europa (era 100k)
        "finnair":         90_000,   # [GUIA] Avios GRU->Europa (era 100k)
        "flyingblue":     100_000,   # SUMA
        "virginatlantic":  84_000,   # Flying Club
        "tap":            120_000,
        "aeroplan":        75_000,   # [GUIA] SA->Atlantico chart (era 100k)
        "alaska":         110_000,
        "lufthansa":      100_000,
        "united":          90_000,   # apertado (Star Alliance/Aegean): saver ~88k
        "qatar":          180_000,
        "turkish":        145_000,
        "emirates":       153_000,
        "delta":          150_000,
        "etihad":         120_000,
        "copa":            90_000,   # [MAPA] Connectmiles real ex-BR 87,5k (guia dizia 35k)
        "latam":          210_000,   # [MAPA] 200k fixa / 150-170k dinamica (era 260k)
        "smiles":         290_000,   # [MAPA] 270k/trecho, 220k de Fortaleza (era 420k)
        "azul":           290_000,   # [MAPA] 260-290k/trecho saindo de SP (era 280k)
    },

    # Europa — Econômica (Bom ou melhor)
    # Espetacular: 32,35k Avios
    # Muito Bom: 100k Smiles | 60k Latam
    # Bom: 100k Latam | 184k Smiles | 42,5k Avios | 175k Azul
    "europa_economy": {
        "iberia":          42_500,   # Avios
        "american":        42_500,   # Avios via AA
        "finnair":         42_500,
        "latam":          100_000,
        "smiles":         184_000,
        "azul":           175_000,
        "flyingblue":      50_000,   # SUMA
        "tap":            108_000,
        "virginatlantic":  54_000,
        "aeroplan":        30_000,   # [GUIA] sweet GRU->Europa eco 30k (era 60k)
        "united":          60_000,
        "delta":           60_000,
        "qatar":           80_000,
        "turkish":         80_000,
        "emirates":        80_000,
        "lufthansa":       60_000,
        "alaska":          60_000,
        "copa":            25_000,   # [GUIA] ConnectMiles chart eco 17,5k (era 50k)
        "etihad":          80_000,
    },

    # Europa — Premium Economy (Bom ou melhor)
    "europa_premium": {
        "iberia":          42_500,
        "american":        60_000,
        "finnair":         60_000,
        "latam":          150_000,
        "smiles":         250_000,
        "azul":           220_000,
        "flyingblue":      70_000,
        "tap":            110_000,
        "virginatlantic":  70_000,
        "aeroplan":        45_000,   # [GUIA] SA->Atlantico prem chart (era 75k)
        "united":          80_000,
        "delta":           80_000,
        "qatar":          100_000,
        "turkish":        100_000,
        "emirates":       100_000,
        "lufthansa":       75_000,
        "alaska":          75_000,
        "copa":            40_000,   # [GUIA] ConnectMiles (era 65k)
        "etihad":         100_000,
    },

    # ═══════════════════════════════════════════════════════════
    # AMÉRICA DO NORTE (EUA / Canadá)
    # ═══════════════════════════════════════════════════════════

    # EUA — Executiva (Bom ou melhor)
    # Espetacular: 250k Smiles
    # Muito bom: 285k Smiles
    # Bom: 320k Smiles | 340k Azul | 110k ConnectMiles
    "eua_business": {
        "smiles":         320_000,
        "azul":           340_000,
        "copa":            45_000,   # [GUIA] ConnectMiles AmSul->AmNorte 35k (era 110k!)
        "latam":          240_000,   # Normal
        "tap":            190_000,
        "american":       115_000,
        "united":         169_000,
        "delta":          135_000,
        "aeroplan":        60_000,
        "alaska":          60_000,
        "qatar":           78_000,
        "flyingblue":     150_000,
        "virginatlantic":  95_000,
        "lufthansa":       65_000,
        "etihad":         120_000,
        "emirates":       153_000,
        "turkish":        145_000,
    },

    # EUA — Econômica (Bom ou melhor)
    # Bom: 75k Latam | 120k Smiles | 70k Azul
    "eua_economy": {
        "latam":           75_000,
        "smiles":         120_000,
        "azul":            70_000,
        "copa":            25_000,   # [GUIA] ConnectMiles AmSul->AmNorte eco 17,5k (era 50k)
        "american":        32_000,
        "united":          40_000,
        "delta":           40_000,
        "aeroplan":        25_000,   # [GUIA] SA->NA eco chart (era 40k)
        "alaska":          40_000,
        "flyingblue":      50_000,
        "virginatlantic":  40_000,
        "lufthansa":       40_000,
        "qatar":           50_000,
        "turkish":         50_000,
        "emirates":        50_000,
        "etihad":          50_000,
        "tap":             60_000,
    },

    # EUA — Premium Economy (Bom ou melhor)
    "eua_premium": {
        "latam":          100_000,
        "smiles":         180_000,
        "azul":           120_000,
        "copa":            40_000,   # [GUIA] ConnectMiles (era 70k)
        "american":        55_000,
        "united":          70_000,
        "delta":           70_000,
        "aeroplan":        40_000,   # [GUIA] SA->NA prem chart (era 60k)
        "alaska":          60_000,
        "flyingblue":      70_000,
        "virginatlantic":  60_000,
        "lufthansa":       55_000,
        "qatar":           65_000,
        "turkish":         65_000,
        "emirates":        65_000,
        "etihad":          65_000,
        "tap":             80_000,
    },

    # ═══════════════════════════════════════════════════════════
    # ÁSIA / ORIENTE MÉDIO
    # ═══════════════════════════════════════════════════════════

    "asia_business": {
        "american":       100_000,   # Avios
        "iberia":         100_000,
        "finnair":        100_000,
        "tap":            140_000,
        "flyingblue":      95_000,
        "qatar":          140_000,
        "emirates":       153_000,
        "turkish":        145_000,
        "singapore":      120_000,
        "etihad":         120_000,
        "alaska":         110_000,
        "united":         110_000,
        "aeroplan":        90_000,   # [GUIA] NA->Pacifico chart (era 100k)
        "copa":            60_000,   # [GUIA] ConnectMiles AmSul->Asia 50k (novo teto)
        "latam":          200_000,
        "azul":           280_000,
        "smiles":         350_000,
    },

    "asia_economy": {
        "qatar":           60_000,
        "emirates":        60_000,
        "turkish":         60_000,
        "singapore":       50_000,
        "etihad":          60_000,
        "flyingblue":      50_000,
        "american":        50_000,
        "united":          50_000,
        "aeroplan":        50_000,
        "alaska":          50_000,
        "latam":          100_000,
        "azul":           150_000,
        "smiles":         150_000,
        "tap":             80_000,
    },

    # Ásia — Premium Economy (Bom ou melhor)
    "asia_premium": {
        "qatar":           80_000,
        "emirates":        80_000,
        "turkish":         80_000,
        "singapore":       70_000,
        "etihad":          80_000,
        "flyingblue":      70_000,
        "american":        70_000,
        "united":          70_000,
        "aeroplan":        70_000,
        "alaska":          70_000,
        "latam":          150_000,
        "azul":           200_000,
        "smiles":         200_000,
        "tap":            100_000,
    },

    # ═══════════════════════════════════════════════════════════
    # AMÉRICA DO SUL (Chile, Bolívia, Uruguai, Argentina, Paraguai)
    # ═══════════════════════════════════════════════════════════

    # América do Sul — Executiva
    # Usando valores razoáveis baseados nos dados do seats.aero
    "america_sul_business": {
        "qatar":           22_000,   # Award incrível (como na imagem!)
        "delta":           31_000,
        "latam":           80_000,
        "azul":            80_000,
        "aeroplan":        40_000,   # [GUIA] Aeroplan dentro da SA 35k (era 55k)
        "smiles":         100_000,
        "copa":            35_000,   # [GUIA] ConnectMiles AmSul->AmSul/Central (era 80k)
        "united":          90_000,
        "american":       100_000,
        "turkish":        116_000,
        "virginatlantic":  50_000,
        "flyingblue":      85_000,
        "alaska":          55_000,
        "lufthansa":       30_000,
        "emirates":       100_000,
    },

    # América do Sul — Econômica (Bom ou melhor)
    # Chile/Bolívia/Uruguai/Argentina/Paraguai
    # Bom: 25k Latam | 32k Azul | 45k Smiles
    "america_sul_economy": {
        "latam":           25_000,
        "azul":            32_000,
        "smiles":          45_000,
        "aeroplan":        25_000,
        "copa":            30_000,
        "united":          22_500,
        "american":        18_000,
        "delta":           16_000,
        "qatar":           11_000,
        "turkish":         40_000,
        "virginatlantic":  25_000,
        "flyingblue":      21_000,
        "alaska":          25_000,
        "lufthansa":       20_000,
    },

    # América do Sul — Premium Economy
    "america_sul_premium": {
        "latam":           40_000,
        "azul":            50_000,
        "smiles":          65_000,
        "aeroplan":        35_000,   # [GUIA] Aeroplan dentro da SA (era 40k)
        "copa":            30_000,   # [GUIA] ConnectMiles (era 50k)
        "united":          40_000,
        "american":        35_000,
        "delta":           30_000,
        "qatar":           18_000,
        "turkish":         60_000,
        "virginatlantic":  35_000,
        "flyingblue":      35_000,
        "alaska":          40_000,
        "lufthansa":       30_000,
    },

    # ═══════════════════════════════════════════════════════════
    # AMÉRICA CENTRAL / CARIBE / MÉXICO
    # ═══════════════════════════════════════════════════════════

    # Am Central — Econômica (Bom ou melhor)
    # Bom: 120k Azul | 120k Smiles | 70k Latam
    "america_central_economy": {
        "smiles":         120_000,
        "azul":           120_000,
        "latam":           70_000,
        "copa":            25_000,   # [GUIA] ConnectMiles Caribe/Central eco (era 40k)
        "aeroplan":        25_000,   # [GUIA] SA->Central eco chart (era 50k)
        "united":          50_000,
        "american":        50_000,
        "delta":           50_000,
        "flyingblue":      50_000,
        "alaska":          40_000,
    },

    # América Central — Premium Economy
    "america_central_premium": {
        "smiles":         120_000,
        "azul":           130_000,
        "latam":           90_000,
        "copa":            40_000,   # [GUIA] ConnectMiles (era 60k)
        "aeroplan":        45_000,   # [GUIA] SA->Central prem chart (era 65k)
        "united":          65_000,
        "american":        65_000,
        "delta":           65_000,
        "flyingblue":      65_000,
        "alaska":          55_000,
    },

    "america_central_business": {
        "smiles":         120_000,
        "copa":            45_000,   # [GUIA] sweet Caribe 40k (era 80k)
        "aeroplan":        45_000,   # [GUIA] SA->Central chart (era 50k)
        "united":          90_000,
        "american":       100_000,
        "delta":          100_000,
        "latam":          100_000,
        "azul":           150_000,
        "flyingblue":      85_000,
        "alaska":          60_000,
    },

    # ═══════════════════════════════════════════════════════════
    # ÁFRICA
    # ═══════════════════════════════════════════════════════════

    "africa_business": {
        "qatar":          190_000,
        "emirates":       153_000,
        "turkish":        145_000,
        "american":        90_000,
        "alaska":         110_000,
        "copa":            60_000,   # [GUIA] ConnectMiles AmSul->Africa 50k (era 100k)
        "aeroplan":        75_000,   # [GUIA] SA->Atlantico chart (novo teto)
        "united":         110_000,
        "smiles":         350_000,
        "latam":          200_000,
        "tap":            140_000,
        "flyingblue":     120_000,
        "delta":          100_000,
    },

    "africa_economy": {
        "qatar":           80_000,
        "emirates":        80_000,
        "turkish":         80_000,
        "american":        60_000,
        "tap":             80_000,
        "flyingblue":      60_000,
        "united":          60_000,
        "delta":           60_000,
    },

    # África — Premium Economy
    "africa_premium": {
        "qatar":          100_000,
        "emirates":       100_000,
        "turkish":        100_000,
        "american":        75_000,
        "tap":            100_000,
        "flyingblue":      80_000,
        "united":          80_000,
        "delta":           80_000,
    },

    # ═══════════════════════════════════════════════════════════
    # OCEANIA
    # ═══════════════════════════════════════════════════════════

    "oceania_business": {
        "qantas":         150_000,
        "qatar":          200_000,
        "american":       120_000,
        "united":         120_000,
        "copa":            85_000,   # [GUIA] sweet Copa Brasil->Oceania Bus 82,5k (novo)
        "aeroplan":        90_000,   # [GUIA] Aeroplan Pacifico chart (novo teto)
        "latam":          200_000,
    },

    "oceania_economy": {
        "qantas":          80_000,
        "qatar":          100_000,
        "united":          80_000,
    },

    # Oceania — Premium Economy
    "oceania_premium": {
        "qantas":         110_000,
        "qatar":          130_000,
        "united":         100_000,
    },

    # ═══════════════════════════════════════════════════════════
    # BRASIL (Nacional)
    # ═══════════════════════════════════════════════════════════

    # Brasil — Economica. TETO DURO: doméstico bom raramente passa disso.
    # Corta absurdos (ex: 38k Rio-SP). Se aparecer doméstico longo (Manaus etc.)
    # acima disso, ainda assim não é "barato" — melhor não alertar.
    "brasil_economy": {
        "azul":            15_000,
        "smiles":          16_000,
        "gol":             16_000,
        "latam":           15_000,
        "copa":            15_000,
        "american":        12_000,
    },

    # Brasil — Executiva (doméstica é rara/curta).
    "brasil_business": {
        "azul":            35_000,
        "smiles":          40_000,
        "gol":             40_000,
        "latam":           35_000,
    },

    # Brasil — Premium Economy
    "brasil_premium": {
        "azul":            25_000,
        "smiles":          30_000,
        "latam":           25_000,
        "aeroplan":        20_000,
        "american":        15_000,
        "copa":            20_000,
    },
}

# ─── YQ (TAXA DE COMBUSTÍVEL) POR PROGRAMA ───────────────────
# [GUIA] Fonte: tabela de YQ do guia. Usado só para ANOTAR no alerta
# (ex: "✅ sem YQ" / "⚠️ YQ alto"), não filtra.
# status: "nao" | "raro" | "depende" | "sim"
YQ_PROGRAMS = {
    "aeroplan":       {"status": "nao",     "obs": "Não repassa na maioria dos parceiros"},
    "united":         {"status": "nao",     "obs": "Não repassa YQ"},
    "copa":           {"status": "raro",    "obs": "Repassa principalmente Swiss e Lufthansa"},
    "alaska":         {"status": "raro",    "obs": "Alto só na British e Icelandair"},
    "turkish":        {"status": "sim",     "obs": "Alto na Lufthansa, Swiss, Thai e ANA"},
    "american":       {"status": "depende", "obs": "Alto da British; moderado Iberia/Qatar"},
    "flyingblue":     {"status": "sim",     "obs": "Alto da Air France, KLM e Virgin"},
    "iberia":         {"status": "depende", "obs": "Alto da Qatar e British; baixo Iberia/AA/LATAM"},
    "qatar":          {"status": "depende", "obs": "Alto Qatar/British/Virgin; baixo demais"},
    "emirates":       {"status": "sim",     "obs": "Alto em todas (exceto Azul, Gol e Copa)"},
    "virginatlantic": {"status": "sim",     "obs": "Alto da Virgin, Air France e KLM"},
    "singapore":      {"status": "depende", "obs": "Voo próprio sem YQ; moderado Lufthansa/Swiss"},
    "british":        {"status": "sim",     "obs": "MUITO ALTO (exceto AA, LATAM, Qantas, Alaska)"},
}

# ─── MAPEAMENTO AEROPORTO → REGIÃO ──────────────────────────
AIRPORT_REGIONS = {
    # Europa
    "LHR": "europa", "LGW": "europa", "CDG": "europa", "ORY": "europa",
    "FCO": "europa", "MXP": "europa", "MAD": "europa", "BCN": "europa",
    "LIS": "europa", "OPO": "europa", "FRA": "europa", "MUC": "europa",
    "AMS": "europa", "IST": "europa", "ZRH": "europa", "VIE": "europa",
    "BRU": "europa", "DUB": "europa", "CPH": "europa", "OSL": "europa",
    "ARN": "europa", "HEL": "europa", "WAW": "europa", "PRG": "europa",
    "BUD": "europa", "ATH": "europa", "EDI": "europa", "MAN": "europa",
    # Ásia / Oriente Médio
    "DXB": "asia", "AUH": "asia", "DOH": "asia",
    "NRT": "asia", "HND": "asia", "ICN": "asia", "HKG": "asia",
    "SIN": "asia", "BKK": "asia", "DEL": "asia", "BOM": "asia",
    "KUL": "asia", "PEK": "asia", "PVG": "asia", "TPE": "asia",
    "MNL": "asia", "SGN": "asia", "HAN": "asia", "CMB": "asia",
    "TLV": "asia", "RUH": "asia", "JED": "asia", "BAH": "asia",
    "MCT": "asia", "AMM": "asia",
    # EUA / Canadá
    "JFK": "eua", "EWR": "eua", "MIA": "eua", "LAX": "eua",
    "ORD": "eua", "SFO": "eua", "ATL": "eua", "DFW": "eua",
    "IAD": "eua", "BOS": "eua", "MCO": "eua", "FLL": "eua",
    "IAH": "eua", "DEN": "eua", "SEA": "eua", "PHX": "eua",
    "PHL": "eua", "CLT": "eua", "MSP": "eua", "DTW": "eua",
    "YYZ": "eua", "YUL": "eua", "YVR": "eua", "YOW": "eua",
    # América do Sul
    "EZE": "america_sul", "AEP": "america_sul",
    "SCL": "america_sul", "LIM": "america_sul",
    "BOG": "america_sul", "MVD": "america_sul",
    "UIO": "america_sul", "CCS": "america_sul",
    "ASU": "america_sul", "VVI": "america_sul",
    "COR": "america_sul", "MDE": "america_sul",
    "CLO": "america_sul", "CTG": "america_sul",
    "USH": "america_sul", "MDZ": "america_sul",   # Ushuaia, Mendoza
    "BRC": "america_sul", "FTE": "america_sul",   # Bariloche, El Calafate
    "IGR": "america_sul", "ROS": "america_sul",   # Puerto Iguazu, Rosario
    "GYE": "america_sul", "CUZ": "america_sul",   # Guayaquil, Cusco
    # América Central / Caribe / México
    "PTY": "america_central", "MEX": "america_central",
    "CUN": "america_central", "SJO": "america_central",
    "GUA": "america_central", "SAL": "america_central",
    "HAV": "america_central", "SJU": "america_central",
    "PUJ": "america_central", "AUA": "america_central",
    "CUR": "america_central", "MBJ": "america_central",
    "NAS": "america_central", "SDQ": "america_central",
    # África
    "JNB": "africa", "CPT": "africa", "CAI": "africa",
    "CMN": "africa", "ADD": "africa", "NBO": "africa",
    "LOS": "africa", "ACC": "africa", "DAR": "africa",
    "DSS": "africa",
    # Oceania
    "SYD": "oceania", "MEL": "oceania", "AKL": "oceania",
    "BNE": "oceania", "PER": "oceania",
    # Brasil (voos domesticos)
    "GIG": "brasil", "GRU": "brasil", "SDU": "brasil", "CGH": "brasil",
    "CNF": "brasil", "BSB": "brasil", "SSA": "brasil", "REC": "brasil",
    "FOR": "brasil", "MCZ": "brasil", "POA": "brasil", "CWB": "brasil",
    "FLN": "brasil", "NAT": "brasil", "BEL": "brasil", "MAO": "brasil",
    "VCP": "brasil", "GYN": "brasil", "CGB": "brasil", "SLZ": "brasil",
    "THE": "brasil", "AJU": "brasil", "JPA": "brasil", "NVT": "brasil",
    "IGU": "brasil", "VIX": "brasil", "PFB": "brasil", "UDI": "brasil",
    "FEN": "brasil", "MCP": "brasil", "PMW": "brasil",
}

MAX_MILES_FALLBACK = 0

# ─── OPERAÇÃO ────────────────────────────────────────────────
START_DATE = ""
END_DATE = ""
CHECK_INTERVAL_MINUTES = 60
HISTORY_FILE = "historico_alertas.json"
SHOW_FUN_FACTS = True
DEBUG = True
