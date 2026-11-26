"""
Base de Conhecimento: Melhores Programas por Rota
====================================================
Baseado em tabelas reais do mercado de milhas brasileiro.
Usado para: priorizar buscas + dica de emissao no alerta.
"""

# Onde emitir mais barato por companhia aerea operadora
# Chave: companhia que OPERA o voo -> programa mais barato para emitir
BEST_EMISSION = {
    "azul": "azul",
    "gol": "smiles",
    "latam": "latam",
    "american": "american",
    "delta": "latam",
    "united": "azul",
    "emirates": "emirates",
    "turkish": "azul",
    "qatar": "iberia",
    "singapore": "singapore",
    "air france": "flyingblue",
    "klm": "flyingblue",
    "lufthansa": "aeroplan",
    "swiss": "aeroplan",
    "tap": "tap",
    "iberia": "iberia",
    "british": "british",
    "copa": "azul",
    "finnair": "finnair",
    "virgin atlantic": "virginatlantic",
    "air canada": "aeroplan",
    "aeromexico": "flyingblue",
    "south african": "smiles",
    "qantas": "latam",
    "etihad": "azul",
    "avianca": "smiles",
    "ethiopian": "smiles",
    "jal": "latam",
    "cathay": "finnair",
    "malaysia": "qatar",
    "royal air maroc": "finnair",
}

# Melhores programas por REGIAO + CABINE
# Ordenados do melhor para o pior (prioridade na busca)
BEST_PROGRAMS_BY_REGION = {
    "brasil_economy": ["azul", "smiles", "latam"],
    "brasil_business": ["azul", "smiles", "latam"],

    "europa_economy": ["iberia", "tap", "flyingblue", "latam", "azul", "smiles", "finnair"],
    "europa_business": ["iberia", "tap", "flyingblue", "virginatlantic", "latam", "azul", "smiles", "finnair"],

    "eua_economy": ["latam", "smiles", "azul", "american", "united", "delta", "copa"],
    "eua_business": ["latam", "smiles", "azul", "copa", "american", "united", "delta", "virginatlantic"],

    "asia_economy": ["iberia", "qatar", "turkish", "emirates", "flyingblue", "finnair"],
    "asia_business": ["iberia", "qatar", "turkish", "emirates", "flyingblue", "finnair", "singapore"],

    "america_sul_economy": ["smiles", "latam", "azul", "american", "qatar", "turkish"],
    "america_sul_business": ["smiles", "latam", "azul", "turkish", "qatar", "american"],

    "america_central_economy": ["smiles", "copa", "azul", "united", "delta", "flyingblue", "latam"],
    "america_central_business": ["copa", "smiles", "azul", "united", "delta", "latam"],

    "africa_economy": ["smiles", "tap", "flyingblue", "turkish", "emirates"],
    "africa_business": ["smiles", "tap", "flyingblue", "turkish", "emirates"],

    "oceania_economy": ["latam", "qatar", "qantas"],
    "oceania_business": ["latam", "qatar", "qantas", "delta"],
}

# Dicas textuais por programa para incluir no alerta
PROGRAM_TIPS = {
    "iberia": "Iberia Avios tem as melhores tarifas por distancia para Europa.",
    "smiles": "Smiles e otimo para nacionais, Am. Sul e parceiros como AA e Delta.",
    "azul": "Azul Fidelidade: otimo para nacionais e voos diretos para Europa/EUA.",
    "latam": "LATAM Pass: excelente para Am. Sul, EUA, Africa do Sul e Oceania.",
    "tap": "TAP Miles&Go: bom para Portugal e Europa via Lisboa.",
    "flyingblue": "Flying Blue: bom para Europa e Africa com Air France/KLM.",
    "copa": "ConnectMiles: otimo para Caribe e Am. Central via Panama.",
    "american": "AAdvantage: bom para EUA e emissoes oneworld.",
    "united": "MileagePlus: bom para EUA e Star Alliance.",
    "delta": "SkyMiles: use para EUA com tabela fixa de executiva.",
    "emirates": "Skywards: bom para Dubai e conexoes para Asia.",
    "turkish": "Miles&Smiles: bom para Am. Sul (executiva) e conexoes via Istambul.",
    "qatar": "Privilege Club: otimo para Oriente Medio, Asia e Oceania. Taxas via Iberia sao menores.",
    "virginatlantic": "Virgin Atlantic: boas tarifas para Europa e EUA.",
    "finnair": "Finnair Plus: bom para EUA/Asia via Helsinki e voos Royal Air Maroc.",
    "british": "British Avios: bom para voos diretos ao Reino Unido.",
    "aeroplan": "Aeroplan: bom para Star Alliance (Lufthansa, Swiss, Air Canada).",
    "alaska": "Alaska Atmos: bom para oneworld e parceiros.",
    "singapore": "KrisFlyer: premium para Asia em executiva/primeira.",
    "etihad": "Etihad Guest: use Azul para emitir primeira classe mais barato.",
    "qantas": "Qantas: use LATAM Pass para emitir voos Qantas mais barato.",
}


# ═══════════════════════════════════════════════════════════════
# [MAPA "Para onde viajar com cada programa de fidelidade"]
# ═══════════════════════════════════════════════════════════════

# Custo REAL de acumulo por milheiro (R$). Usado no "Custo estimado" do alerta.
# Valores = meio da faixa informada no mapa.
MILHEIRO_CUSTO = {
    "azul":        12,   # R$11–13,5
    "smiles":      15,   # R$14–16
    "gol":         15,
    "latam":       24,   # R$23,5–25
    "tap":         37,   # R$35–40 (Clube C6)  << estava 49, errado
    "iberia":      52,   # R$49–55 (Avios)
    "british":     52,
    "qatar":       52,
    "finnair":     52,
    "american":    52,
    "copa":        52,   # R$50–55
    "aegean":      68,   # R$68
    "aireuropa":   63,   # 10 euros
    # demais programas: estimativa padrao
    "flyingblue":  49, "aeroplan": 49, "united": 49, "delta": 49,
    "virginatlantic": 49, "alaska": 49, "emirates": 49, "turkish": 49,
    "singapore":   49, "lufthansa": 49, "etihad": 49, "qantas": 49,
}

# Regioes onde cada programa REALMENTE compensa (sweet spots do mapa).
REGIAO_FORTE = {
    "smiles":    {"brasil", "america_sul"},
    "latam":     {"brasil", "eua", "africa", "oceania", "america_sul", "europa"},
    "azul":      {"brasil", "america_central", "eua", "america_sul"},
    "iberia":    {"europa", "asia", "oceania"},
    "qatar":     {"asia", "oceania", "europa", "eua"},
    "british":   {"europa"},
    "finnair":   {"eua", "europa", "asia"},
    "copa":      {"america_central", "asia"},
    "tap":       {"europa"},
    "aegean":    {"europa", "asia"},
    "aireuropa": {"europa", "asia"},
}

# Combinacoes que o mapa diz NAO valerem a pena.
REGIAO_FRACA = {
    "smiles": {"europa"},   # "para EUA e Europa nao costumam ser atraentes"
}

# Observacao curta por programa (aparece junto do sweet spot).
OBS_PROGRAMA = {
    "british":   "só compensa em voo DIRETO pro Reino Unido",
    "azul":      "internacionais próprios saem só 1–3 meses antes",
    "qatar":     "nos voos Qatar, emitir pela Ibéria tem taxa menor",
    "tap":       "melhor saindo de BEL, NAT, CWB, BSB, FLN ou POA",
    "aegean":    "executiva via Star Alliance",
}

_REGIAO_NOME = {
    "brasil": "Brasil", "europa": "Europa", "eua": "EUA/Canadá",
    "asia": "Ásia/Or. Médio", "america_sul": "América do Sul",
    "america_central": "Am. Central/Caribe", "africa": "África",
    "oceania": "Oceania",
}


def sweet_spot_tip(source, region):
    """Diz se o programa é FORTE (sweet spot) ou FRACO naquela região.
    Retorna texto curto pro alerta, ou '' quando não há nada a dizer."""
    if not source or not region:
        return ""
    nome = _REGIAO_NOME.get(region, region)
    if region in REGIAO_FRACA.get(source, ()):
        return f"Pra {nome} esse programa costuma NÃO ser atraente — compare antes"
    if region in REGIAO_FORTE.get(source, ()):
        obs = OBS_PROGRAMA.get(source, "")
        return f"Sweet spot: forte pra {nome}" + (f" ({obs})" if obs else "")
    return ""


def get_emission_tip(source, destination_region="", cabin="economy"):
    """Retorna dica de emissao para incluir no alerta."""
    tip = PROGRAM_TIPS.get(source, "")
    return tip


def get_priority_programs(region, cabin="economy", selected_programs=None):
    """
    Retorna programas ordenados por prioridade para uma regiao.
    Util para ordenar a busca (buscar os melhores primeiro).
    """
    cabin_suffix = "economy" if cabin == "economy" else "business"
    key = f"{region}_{cabin_suffix}"
    priority = BEST_PROGRAMS_BY_REGION.get(key, [])

    if not selected_programs:
        return priority

    # Filtrar apenas os programas selecionados, mantendo ordem de prioridade
    ordered = [p for p in priority if p in selected_programs]
    # Adicionar programas selecionados que nao estao na lista de prioridade
    remaining = [p for p in selected_programs if p not in ordered]
    return ordered + remaining
