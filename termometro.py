"""
Termometro de Precos — "A Verdade das Milhas" (Vitao)
=====================================================
Fonte: mapa mental do usuario (JAN/26). Faixas ABSOLUTAS por regiao/cabine/
programa, saindo do Brasil, considerando as melhores portas de entrada.

- classify(source, dest, cabin, miles) -> tier ("espetacular".."acima"/None)
- SEND_TIERS: faixas que valem alerta (bom ou melhor)
- tier_label(tier): rotulo bonito pro alerta
- emit_via(source): programas brasileiros parceiros p/ emitir aquela cia

Avios = american / finnair / iberia (todos usam Avios).
Virgin = virginatlantic | Connectmiles = copa | SUMA/LifeMiles nao mapeado.
"""

# ─── FAIXAS DO TERMOMETRO (teto de milhas por faixa) ─────────────
# tier: teto "X ou menos". Classifica-se pela 1a faixa cujo teto >= milhas.
TIERS = {
    # ═══ AMERICA DO NORTE (EUA / Canada) ═══
    "eua": {
        "economy": {
            "espetacular": {"latam": 50_000, "azul": 62_000},
            "muito_bom":   {"latam": 60_000, "azul": 80_000},
            "bom":         {"latam": 75_000, "smiles": 100_000, "azul": 100_000},
            "normal":      {"latam": 90_000, "smiles": 130_000, "azul": 125_000},
            "caro":        {"latam": 114_000, "smiles": 170_000, "azul": 160_000, "copa": 50_000, "american": 32_000},
            "pessimo":     {"latam": 140_000, "smiles": 210_000, "azul": 200_000, "american": 40_000},
        },
        "business": {
            "espetacular": {"smiles": 250_000},
            "muito_bom":   {"smiles": 285_000},
            "bom":         {"smiles": 320_000, "azul": 340_000, "copa": 110_000},
            "normal":      {"latam": 240_000, "tap": 190_000},
            "caro":        {"latam": 270_000, "american": 124_000, "finnair": 124_000, "iberia": 124_000},
        },
    },
    # ═══ EUROPA ═══
    "europa": {
        "economy": {
            # [AVIOS] valores POR TRECHO (o bot compara trecho a trecho).
            # O 21,25k/42,5k antigo era ida+volta -> deixava passar o dobro.
            # Real GIG/GRU->MAD eco: off-peak 16-20k, peak ~25,5k (SeatSpy).
            "espetacular": {"american": 16_000, "finnair": 16_000, "iberia": 16_000},
            "muito_bom":   {"latam": 75_000, "smiles": 120_000, "azul": 135_000,
                            "american": 20_000, "finnair": 20_000, "iberia": 20_000},
            "bom":         {"latam": 100_000, "smiles": 184_000, "american": 25_500, "finnair": 25_500, "iberia": 25_500, "azul": 175_000},
            "normal":      {"latam": 120_000, "smiles": 200_000, "azul": 210_000},
            "caro":        {"latam": 150_000, "smiles": 230_000, "azul": 230_000, "virginatlantic": 34_000, "tap": 108_000},
            "pessimo":     {"latam": 180_000, "copa": 95_000, "azul": 250_000, "tap": 150_000, "virginatlantic": 54_000},
        },
        "business": {
            # [AVIOS] POR TRECHO. Antes muito_bom=82,5k era ida+volta.
            # Real GIG/GRU->MAD exec: ~32-50k o trecho (aula: "40-50k executiva").
            "espetacular": {"american": 32_350, "finnair": 32_350, "iberia": 32_350},
            "muito_bom":   {"virginatlantic": 84_000, "american": 42_500, "finnair": 42_500, "iberia": 42_500, "latam": 240_000},
            "bom":         {"latam": 260_000, "smiles": 420_000,
                            "american": 50_000, "finnair": 50_000, "iberia": 50_000},
            "normal":      {"latam": 320_000, "tap": 240_000, "smiles": 500_000, "azul": 490_000, "copa": 175_000},
            "caro":        {"latam": 400_000, "smiles": 640_000, "azul": 600_000, "virginatlantic": 170_000, "tap": 362_000},
        },
    },
    # ═══ ASIA / ORIENTE MEDIO ═══
    # [DERIVADO] Ramo "Custo de oportunidade Asia" do mapa. Valores i/v foram
    # convertidos para POR-TRECHO (÷2). O mapa nao trazia faixas nomeadas, entao
    # "bom" = preco de referencia do mapa e as demais faixas foram interpoladas.
    # Avios = american/finnair/iberia. (qatar e distance-source, nao passa aqui.)
    "asia": {
        "economy": {
            "espetacular": {"american": 40_000, "finnair": 40_000, "iberia": 40_000},
            "muito_bom":   {"american": 50_000, "finnair": 50_000, "iberia": 50_000, "latam": 90_000},
            "bom":         {"american": 55_000, "finnair": 55_000, "iberia": 55_000, "latam": 100_000, "azul": 150_000, "smiles": 150_000},
            "normal":      {"latam": 130_000, "azul": 180_000, "smiles": 180_000},
            "caro":        {"latam": 160_000, "azul": 220_000, "smiles": 220_000},
        },
        "business": {
            "espetacular": {"american": 80_000, "finnair": 80_000, "iberia": 80_000},
            "muito_bom":   {"american": 95_000, "finnair": 95_000, "iberia": 95_000, "tap": 130_000},
            "bom":         {"american": 100_000, "finnair": 100_000, "iberia": 100_000, "tap": 140_000, "latam": 200_000},
            "normal":      {"latam": 240_000, "smiles": 320_000, "azul": 350_000},
            "caro":        {"latam": 300_000, "smiles": 420_000},
        },
    },
    # ═══ AMERICA CENTRAL / CARIBE ═══
    "america_central": {
        "economy": {
            "espetacular": {"smiles": 78_500, "latam": 43_000},
            "muito_bom":   {"smiles": 100_000, "latam": 60_000},
            "bom":         {"azul": 120_000, "smiles": 120_000, "latam": 70_000},
            "normal":      {"azul": 140_000, "smiles": 140_000, "latam": 80_000, "copa": 40_000},
            "caro":        {"azul": 160_000, "smiles": 160_000, "latam": 100_000},
            "pessimo":     {"azul": 180_000, "smiles": 180_000, "latam": 130_000, "copa": 80_000},
        },
        # [DERIVADO] Executiva ~2x economica (BR) + Copa/Aeroplan/AA reais do guia.
        "business": {
            "espetacular": {"copa": 35_000, "latam": 80_000},
            "muito_bom":   {"latam": 100_000, "smiles": 200_000, "aeroplan": 50_000},
            "bom":         {"latam": 130_000, "smiles": 240_000, "azul": 240_000, "copa": 60_000, "aeroplan": 60_000, "american": 100_000},
            "normal":      {"latam": 160_000, "smiles": 300_000, "azul": 300_000},
            "caro":        {"latam": 200_000, "smiles": 360_000},
        },
    },
    # ═══ AMERICA DO SUL — Cone Sul (Chile, Bolivia, Uruguai, Argentina, Paraguai) ═══
    "america_sul_sul": {
        "economy": {
            "espetacular": {"azul": 11_000},
            "muito_bom":   {"latam": 18_000, "azul": 23_000, "smiles": 30_000},
            # smiles "bom" apertado 45k->38k (pedido do usuario: cortar casos
            # caros tipo GIG-Asuncion 42k, mantendo Buenos Aires/Santiago <=38k).
            "bom":         {"latam": 25_000, "azul": 32_000, "smiles": 38_000},
            "normal":      {"latam": 40_000, "azul": 50_000, "smiles": 60_000},
            "caro":        {"latam": 50_000, "azul": 65_000, "smiles": 75_000},
            "pessimo":     {"latam": 60_000, "azul": 75_000, "smiles": 85_000},
        },
        # [DERIVADO] Executiva: Avios (GRU-EZE/SCL ~16-22k) reais do guia + BR ~2x.
        "business": {
            "espetacular": {"american": 22_000, "finnair": 22_000, "azul": 35_000},
            "muito_bom":   {"latam": 35_000, "azul": 50_000, "smiles": 70_000, "american": 30_000, "finnair": 30_000},
            "bom":         {"latam": 50_000, "azul": 70_000, "smiles": 100_000, "copa": 35_000, "aeroplan": 40_000},
            "normal":      {"latam": 80_000, "azul": 100_000, "smiles": 130_000},
            "caro":        {"latam": 100_000, "azul": 130_000, "smiles": 160_000},
        },
    },
    # ═══ AMERICA DO SUL — Andina/Norte (Colombia, Peru, Equador) ═══
    "america_sul_norte": {
        "economy": {
            "espetacular": {"latam": 24_000},
            "muito_bom":   {"latam": 30_000, "smiles": 54_000},
            "bom":         {"latam": 50_000, "smiles": 80_000, "american": 26_000, "finnair": 26_000, "iberia": 26_000, "azul": 87_200},
            "normal":      {"latam": 65_000, "smiles": 120_000, "azul": 109_000},
            "caro":        {"latam": 75_000, "smiles": 140_000, "azul": 120_000},
            "pessimo":     {"latam": 100_000},
        },
        # [DERIVADO] Executiva: BR ~2x economica + Avios/Aeroplan do guia.
        "business": {
            "espetacular": {"american": 44_000, "finnair": 44_000, "latam": 40_000},
            "muito_bom":   {"latam": 55_000, "smiles": 100_000, "american": 50_000, "finnair": 50_000},
            "bom":         {"latam": 70_000, "smiles": 140_000, "azul": 150_000, "aeroplan": 55_000},
            "normal":      {"latam": 90_000, "smiles": 180_000, "azul": 180_000},
            "caro":        {"latam": 120_000, "smiles": 220_000},
        },
    },
}

# Aeroportos da America do Sul "Andina/Norte" (Colombia, Peru, Equador, Venezuela)
AMSUL_NORTE = {"BOG", "MDE", "CLO", "CTG", "LIM", "UIO", "GYE", "CCS"}

TIER_ORDER = ["espetacular", "muito_bom", "bom", "normal", "caro", "pessimo"]
SEND_TIERS = {"espetacular", "muito_bom", "bom"}

TIER_LABELS = {
    "espetacular": "\U0001f31f ESPETACULAR",
    "muito_bom":   "\U0001f525 MUITO BOM",
    "bom":         "✅ BOM",
    "normal":      "\U0001f610 Normal",
    "caro":        "\U0001f4b8 Caro",
    "pessimo":     "⛔ Péssimo",
    "acima":       "⛔ Acima do péssimo",
}

# ─── PARCERIAS DE EMISSAO (cia/programa estrangeiro -> programa BR) ──
# "Emita via" — quando um award de programa estrangeiro aparece, indica
# quais programas brasileiros conseguem emitir aquela cia.
EMITIR_VIA = {
    "emirates":       ["azul", "smiles"],
    "tap":            ["azul", "smiles"],
    "copa":           ["azul", "smiles"],
    "united":         ["azul"],
    "turkish":        ["azul", "smiles"],
    "etihad":         ["azul"],
    "aeroplan":       ["azul", "smiles"],   # Air Canada
    "ethiopian":      ["smiles"],
    "singapore":      [],                    # sem parceria BR
    "lufthansa":      ["latam"],
    "british":        ["latam"],
    "finnair":        ["latam"],
    "qantas":         ["latam"],
    "virginatlantic": ["latam"],
    "delta":          ["latam"],
    "qatar":          ["latam"],             # so origem/destino Brasil
    "iberia":         ["latam"],
    "flyingblue":     ["smiles", "latam"],   # Air France / KLM
    "american":       ["smiles"],
    "alaska":         [],
}

_PROGRAMA_BR_NOME = {"azul": "Azul", "smiles": "Smiles", "latam": "LATAM"}
_PROGRAMAS_BR = {"azul", "smiles", "latam"}

# ─── FONTES QUE ANDAM NAO REFLETINDO AWARD (mapa "A Verdade das Milhas") ──
# Companhias/programas que historicamente param de mostrar award mas podem
# VOLTAR a qualquer momento. NAO bloqueamos o alerta — so avisamos pra pessoa
# pesquisar/confirmar antes de comemorar (o cache do seats.aero pode estar
# desatualizado justo nessas fontes instaveis).
#
# Dois niveis:
#  1) NAO_REFLETE      -> por PROGRAMA (o 'source' do seats.aero).
#  2) NAO_REFLETE_CIA  -> por CIA OPERADORA (codigo IATA lido dos campos
#     *Airlines do registro). Pega casos que aparecem via Smiles etc., onde
#     o 'source' e o programa e nao a companhia que voa.

# Por programa. Como o bot so busca saindo do Brasil, o aviso do TAP
# ("nao libera award do Brasil") vale pra todo alerta com source 'tap'.
NAO_REFLETE = {
    "tap": "TAP quase nunca libera award saindo do Brasil (~1x/ano)",
}

# Por cia operadora (codigo IATA). Detectado via *Airlines do seats.aero.
NAO_REFLETE_CIA = {
    "ET": "Ethiopian anda sem refletir award (via Smiles desde mai/24)",
    "AR": "Aerolineas anda sem refletir award (via Smiles desde mar/25)",
    "UX": "Air Europa so costuma refletir saindo de Salvador, em economica",
}

# Fallback: se o campo vier com NOME em vez de codigo IATA (substring, upper).
_CIA_NOME_ALIASES = {
    "ETHIOPIAN": "ET",
    "AEROLINEAS": "AR", "AEROLÍNEAS": "AR", "ARGENTINAS": "AR",
    "AIR EUROPA": "UX", "AIREUROPA": "UX",
}

try:
    from config import AIRPORT_REGIONS
except Exception:
    AIRPORT_REGIONS = {}


def _region_key(dest):
    region = AIRPORT_REGIONS.get(dest, "")
    if region == "america_sul":
        return "america_sul_norte" if dest in AMSUL_NORTE else "america_sul_sul"
    return region


# British e Qatar tambem sao Avios (mesma moeda da Iberia). O mapa lista os
# valores Avios sob american/finnair/iberia; entao pra classificar british/
# qatar usamos as mesmas faixas da "iberia".
_AVIOS_ALIAS = {"british": "iberia", "qatar": "iberia"}


def classify(source, dest, cabin, miles):
    """
    Classifica um award pela faixa do termometro.
    Retorna: 'espetacular'|'muito_bom'|'bom'|'normal'|'caro'|'pessimo'|'acima'
             ou None quando nao ha dado (deixa o fallback decidir).
    """
    if cabin not in ("economy", "business", "first"):
        return None  # premium: sem regua no painel -> fallback
    src = _AVIOS_ALIAS.get(source, source)  # british/qatar -> iberia (Avios)
    region = _region_key(dest)
    table = TIERS.get(region, {}).get(cabin)
    if not table:
        return None
    for tier in TIER_ORDER:
        ceil = table.get(tier, {}).get(src)
        if ceil is not None and miles <= ceil:
            return tier
    # source existe na tabela mas passou de tudo -> acima do pessimo
    if any(src in table.get(t, {}) for t in TIER_ORDER):
        return "acima"
    return None  # source nao coberto nessa regiao -> fallback


def tier_label(tier):
    return TIER_LABELS.get(tier, "")


def emit_via(source):
    """Programas BR (nomes bonitos) que emitem a cia/programa 'source'.
    Nao sugere nada se o proprio source ja for um programa brasileiro."""
    if source in _PROGRAMAS_BR:
        return []
    progs = EMITIR_VIA.get(source, [])
    return [_PROGRAMA_BR_NOME[p] for p in progs if p in _PROGRAMA_BR_NOME]


def reflect_warning(source):
    """Aviso quando o PROGRAMA (source) anda instavel/nao refletindo award.
    Retorna a nota (str) ou '' quando esta normal."""
    return NAO_REFLETE.get(source, "")


def reflect_warning_carrier(airlines):
    """Aviso quando a CIA OPERADORA anda instavel.
    'airlines' = iteravel de codigos IATA e/ou nomes (dos campos *Airlines).
    Retorna a 1a nota encontrada ou '' se nenhuma cia estiver na lista."""
    for a in airlines or []:
        tok = str(a).strip().upper()
        if not tok:
            continue
        if tok in NAO_REFLETE_CIA:          # match por codigo IATA (ex: "ET")
            return NAO_REFLETE_CIA[tok]
        for nome, code in _CIA_NOME_ALIASES.items():  # match por nome (substring)
            if nome in tok:
                return NAO_REFLETE_CIA[code]
    return ""


# ═══════════════════════════════════════════════════════════════════════════
# RÉGUA DO TERMÔMETRO DO RUDI — painel.dia23.com.br/termometro (Curso VMM)
# ═══════════════════════════════════════════════════════════════════════════
# Lida em 25/11/2026. Valores JÁ SÃO POR TRECHO e em milhas de cada programa
# (o painel converte tudo em R$ pelo milheiro de venda e devolve o equivalente
# em milhas), que é exatamente como o bot compara. Mapeamento 1:1 das faixas:
#     COMPRE AGORA -> espetacular | EXCELENTE -> muito_bom | BOM -> bom
# Só essas três são enviadas (SEND_TIERS); NORMAL/CARO/PÉSSIMO ficam de fora.
#
# Cobre 17 programas (antes a régua tinha 10) em 6 regiões. As faixas em R$ são
# iguais para todos os programas da região — o que muda é quantas milhas de cada
# programa compram aquele valor.
REGUA_PAINEL = {
    "europa": {
        "economy": {
            "espetacular": {"azul": 101_662, "copa": 24_805, "iberia": 27_367, "latam": 56_612, "smiles": 90_800, "tap": 30_680, "virginatlantic": 20_144},
            "muito_bom": {"azul": 115_209, "copa": 28_110, "iberia": 31_014, "latam": 64_156, "smiles": 102_900, "tap": 34_768, "virginatlantic": 22_829},
            "bom": {"azul": 127_679, "copa": 31_153, "iberia": 34_370, "latam": 71_100, "smiles": 114_038, "tap": 38_531, "virginatlantic": 25_300},
        },
        "business": {
            "espetacular": {"aeroplan": 42_269, "american": 35_721, "azul": 219_174, "british": 59_000, "copa": 53_477, "flyingblue": 42_298, "iberia": 59_000, "latam": 122_050, "lufthansa": 34_884, "qatar": 59_000, "smiles": 195_757, "tap": 66_143, "united": 40_361, "virginatlantic": 43_429},
            "muito_bom": {"aeroplan": 62_135, "american": 52_510, "azul": 322_185, "british": 86_730, "copa": 78_611, "flyingblue": 62_178, "iberia": 86_730, "latam": 179_413, "lufthansa": 51_279, "qatar": 86_730, "smiles": 287_763, "tap": 97_230, "united": 59_331, "virginatlantic": 63_841},
            "bom": {"aeroplan": 83_076, "american": 70_208, "azul": 430_773, "british": 115_961, "copa": 105_106, "flyingblue": 83_135, "iberia": 115_961, "latam": 239_882, "lufthansa": 68_562, "qatar": 115_961, "smiles": 384_749, "tap": 130_000, "united": 79_327, "virginatlantic": 85_358},
        },
    },
    "eua": {
        "economy": {
            "espetacular": {"aeroplan": 12_632, "american": 10_675, "azul": 65_498, "copa": 15_981, "latam": 36_474, "qatar": 17_632, "smiles": 58_500, "united": 12_062},
            "muito_bom": {"aeroplan": 15_007, "american": 12_682, "azul": 77_814, "copa": 18_986, "latam": 43_332, "qatar": 20_947, "smiles": 69_500, "united": 14_329},
            "bom": {"aeroplan": 17_079, "american": 14_434, "azul": 88_562, "copa": 21_608, "latam": 49_317, "qatar": 23_840, "smiles": 79_100, "united": 16_309},
        },
        "business": {
            "espetacular": {"aeroplan": 34_142, "alaska": 26_968, "american": 28_853, "azul": 177_034, "british": 47_656, "copa": 43_195, "delta": 38_073, "finnair": 43_141, "flyingblue": 34_166, "iberia": 47_656, "latam": 98_584, "lufthansa": 28_177, "qatar": 47_656, "smiles": 158_120, "tap": 53_426},
            "muito_bom": {"aeroplan": 40_656, "alaska": 32_114, "american": 34_359, "azul": 210_814, "british": 56_750, "copa": 51_437, "delta": 45_337, "finnair": 51_373, "flyingblue": 40_685, "iberia": 56_750, "latam": 117_395, "lufthansa": 33_553, "qatar": 56_750, "smiles": 188_291, "tap": 63_620},
            "bom": {"aeroplan": 55_307, "alaska": 43_687, "american": 46_740, "azul": 286_783, "british": 77_200, "copa": 69_973, "delta": 61_675, "finnair": 69_886, "flyingblue": 55_346, "iberia": 77_200, "latam": 159_699, "lufthansa": 45_644, "qatar": 77_200, "smiles": 256_143, "tap": 86_546},
        },
    },
    "america_sul_sul": {
        "economy": {
            "espetacular": {"azul": 36_947, "latam": 20_575, "qatar": 9_946, "smiles": 33_000},
            "muito_bom": {"azul": 46_690, "latam": 26_000, "qatar": 12_569, "smiles": 41_702},
            "bom": {"azul": 56_495, "latam": 31_460, "qatar": 15_208, "smiles": 50_459},
        },
        "business": {
            "espetacular": {"aeroplan": 11_827, "azul": 61_326, "british": 16_509, "finnair": 14_945, "iberia": 16_509, "latam": 34_150, "qatar": 16_509, "smiles": 54_774, "tap": 18_507, "united": 11_293},
            "muito_bom": {"aeroplan": 14_359, "azul": 74_454, "british": 20_043, "finnair": 18_144, "iberia": 20_043, "latam": 41_461, "qatar": 20_043, "smiles": 66_500, "tap": 22_469, "united": 13_711},
            "bom": {"aeroplan": 15_438, "azul": 80_053, "british": 21_550, "finnair": 19_508, "iberia": 21_550, "latam": 44_578, "qatar": 21_550, "smiles": 71_500, "tap": 24_158, "united": 14_742},
        },
    },
    "america_sul_norte": {
        "economy": {
            "espetacular": {"azul": 37_409, "iberia": 10_070, "latam": 20_832, "qatar": 10_070, "smiles": 33_412},
            "muito_bom": {"azul": 54_288, "iberia": 14_614, "latam": 30_231, "qatar": 14_614, "smiles": 48_488},
            "bom": {"azul": 67_126, "iberia": 18_070, "latam": 37_380, "qatar": 18_070, "smiles": 59_954},
        },
        "business": {
            "espetacular": {"aeroplan": 27_725, "finnair": 35_034, "latam": 80_056, "qatar": 38_700, "smiles": 128_403},
            "muito_bom": {"aeroplan": 31_656, "finnair": 40_000, "latam": 91_405, "qatar": 44_186, "smiles": 146_606},
            "bom": {"aeroplan": 35_231, "finnair": 44_517, "latam": 101_728, "qatar": 49_176, "smiles": 163_162},
        },
    },
    "america_central": {
        "economy": {
            "espetacular": {"american": 8_741, "azul": 53_629, "copa": 13_085, "latam": 29_864, "qatar": 14_437, "smiles": 47_900},
            "muito_bom": {"american": 10_273, "azul": 63_031, "copa": 15_379, "latam": 35_100, "qatar": 16_968, "smiles": 56_297},
            "bom": {"american": 12_761, "azul": 78_295, "copa": 19_103, "latam": 43_600, "qatar": 21_076, "smiles": 69_930},
        },
        "business": {
            "espetacular": {"aeroplan": 12_459, "azul": 64_602, "flyingblue": 12_468, "smiles": 57_700},
            "muito_bom": {"aeroplan": 18_731, "azul": 97_127, "flyingblue": 18_745, "smiles": 86_750},
            "bom": {"aeroplan": 26_177, "azul": 135_735, "flyingblue": 26_196, "smiles": 121_233},
        },
    },
    "asia": {
        "economy": {
            "espetacular": {"iberia": 50_698, "latam": 104_875, "qatar": 50_698, "smiles": 168_210},
            "muito_bom": {"iberia": 54_147, "latam": 112_010, "qatar": 54_147, "smiles": 179_654},
            "bom": {"iberia": 54_925, "latam": 113_620, "qatar": 54_925, "smiles": 182_236},
        },
        "business": {
            "espetacular": {"aeroplan": 60_895, "flyingblue": 60_938, "iberia": 85_000, "latam": 175_835, "lufthansa": 50_256, "qatar": 85_000},
            "muito_bom": {"aeroplan": 78_949, "flyingblue": 79_005, "iberia": 110_200, "latam": 227_965, "lufthansa": 65_155, "qatar": 110_200},
            "bom": {"aeroplan": 119_916, "flyingblue": 120_000, "iberia": 167_383, "latam": 346_255, "lufthansa": 98_964, "qatar": 167_383},
        },
    },
}


# Primeira Classe — painel: /termometro/primeira/<regiao> (só 3 regiões têm dado)
REGUA_PAINEL_PRIMEIRA = {
    "europa": {
        "first": {
            "espetacular": {"american": 62_500, "british": 103_230, "iberia": 103_230, "latam": 213_546, "lufthansa": 61_034, "qatar": 103_230},
            "muito_bom": {"american": 66_599, "british": 110_000, "iberia": 110_000, "latam": 227_551, "lufthansa": 65_037, "qatar": 110_000},
            "bom": {"american": 72_653, "british": 120_000, "iberia": 120_000, "latam": 248_237, "lufthansa": 70_950, "qatar": 120_000},
        },
    },
    "eua": {
        "first": {
            "espetacular": {"finnair": 79_081, "iberia": 87_357, "qatar": 87_357, "smiles": 289_844},
            "muito_bom": {"finnair": 81_907, "iberia": 90_478, "qatar": 90_478, "smiles": 300_200},
            "bom": {"finnair": 90_927, "iberia": 100_443, "qatar": 100_443, "smiles": 333_260},
        },
    },
    "asia": {
        "first": {
            "espetacular": {"aeroplan": 41_559, "american": 35_121, "british": 58_009, "iberia": 58_009, "latam": 120_000, "qatar": 58_009},
            "muito_bom": {"aeroplan": 66_494, "american": 56_194, "british": 92_814, "iberia": 92_814, "latam": 192_000, "qatar": 92_814},
            "bom": {"aeroplan": 70_997, "american": 60_000, "british": 99_101, "iberia": 99_101, "latam": 205_004, "qatar": 99_101},
        },
    },
}

for _reg, _cab in REGUA_PAINEL_PRIMEIRA.items():
    REGUA_PAINEL.setdefault(_reg, {}).update(_cab)


# Iberia / British / Qatar (Avios) FICAM FORA da régua do painel: eles têm tabela
# própria por BANDA DE DISTÂNCIA com baixa e alta temporada (distance_service.
# FARE_TABLE), que o painel não consegue representar — lá é um valor único em
# reais por região. Tirando-os daqui, o classify devolve None e o processor cai
# no _is_award_distance, que usa a tabela oficial. (Decisão do usuário, 25/11.)
_AVIOS_FORA = ("iberia", "british", "qatar")


def _aplicar_regua_painel():
    """
    Sobrepõe a régua do painel nos programas que ela cobre. Remove o programa de
    TODAS as faixas antigas antes de regravar: se sobrasse um valor velho numa
    faixa mais alta, ele continuaria deixando passar alerta caro.
    """
    for regiao, cabines in REGUA_PAINEL.items():
        for cabine, faixas in cabines.items():
            alvo = TIERS.setdefault(regiao, {}).setdefault(cabine, {})
            programas = {p for valores in faixas.values() for p in valores}
            for faixa in alvo.values():
                for p in programas:
                    faixa.pop(p, None)
            for nome, valores in faixas.items():
                alvo.setdefault(nome, {}).update(valores)


_aplicar_regua_painel()


def _remover_avios_do_termometro():
    """
    Tira iberia/british/qatar de TODAS as faixas do termômetro — inclusive os
    valores antigos que já estavam na tabela base. Com eles fora, classify()
    devolve None e o processor usa _is_award_distance (tabela oficial por banda
    de distância, com baixa e alta temporada).
    """
    for cabines in TIERS.values():
        for faixas in cabines.values():
            for faixa in faixas.values():
                for p in _AVIOS_FORA:
                    faixa.pop(p, None)


_remover_avios_do_termometro()
