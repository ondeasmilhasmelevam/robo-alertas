"""
Formatador v6 — Agrupado + Taxas reais + Alerta de queda COM DATAS
====================================================================
Correcao: format_price_drop agora inclui datas disponiveis.
"""
from collections import defaultdict

try:
    from processor import airport_display, FUN_FACTS, source_display
except ImportError:
    def airport_display(c): return (c, "")
    def source_display(s): return (s, s)
    FUN_FACTS = {}

try:
    from emission_tips import get_emission_tip, MILHEIRO_CUSTO
except ImportError:
    def get_emission_tip(s,r="",c=""): return ""
    MILHEIRO_CUSTO = {}

if not MILHEIRO_CUSTO:
    MILHEIRO_CUSTO = {
        "iberia":49,"british":49,"qatar":49,"finnair":49,
        "smiles":16,"azul":13,"latam":24,"tap":49,"flyingblue":49,
        "aeroplan":49,"american":49,"united":49,"delta":49,
        "copa":52,"virginatlantic":49,"alaska":49,"emirates":49,
        "turkish":49,"singapore":49,"lufthansa":49,"etihad":49,"qantas":49,
    }

PASSAGEM_PAGA = {
    "europa_business":18000,"europa_premium":10000,"europa_economy":4000,
    "eua_business":15000,"eua_premium":8000,"eua_economy":3500,
    "asia_business":22000,"asia_premium":12000,"asia_economy":6000,
    "america_sul_business":5000,"america_sul_premium":2500,"america_sul_economy":1500,
    "america_central_business":8000,"america_central_premium":4000,"america_central_economy":2500,
    "africa_business":18000,"africa_premium":10000,"africa_economy":5000,
    "oceania_business":25000,"oceania_premium":14000,"oceania_economy":7000,
    "brasil_business":3000,"brasil_premium":1500,"brasil_economy":800,
}

MONTHS_PT = {
    "01":"JAN","02":"FEV","03":"MAR","04":"ABR","05":"MAI","06":"JUN",
    "07":"JUL","08":"AGO","09":"SET","10":"OUT","11":"NOV","12":"DEZ",
}


def fmt_miles(m): return f"{m:,}".replace(",",".")

def fmt_tax(t):
    if not t or t == 0: return "R$ 0"
    if isinstance(t, float):
        return f"R$ {t:,.2f}".replace(",","X").replace(".",",").replace("X",".")
    if t > 1000:
        reais = t / 100
        return f"R$ {reais:,.2f}".replace(",","X").replace(".",",").replace("X",".")
    return f"R$ {t}"

def fmt_dates(dates):
    if not dates: return ""
    # Dedup por data — mantém o MAIOR nº de assentos visto (evita "11, 11, 11...").
    seats_by_date = {}
    for d in dates:
        dt = d.get("date","")
        if not dt or len(dt) < 10: continue
        if len(dt.split("-")) != 3: continue
        seats = d.get("seats",0) or 0
        if dt not in seats_by_date or seats > seats_by_date[dt]:
            seats_by_date[dt] = seats
    by_month = defaultdict(list)
    for dt in sorted(seats_by_date):
        y, m, day = dt.split("-")
        dn = str(int(day))
        seats = seats_by_date[dt]
        mk = f"{MONTHS_PT.get(m,m)}/{y[2:]}"
        if 1 <= seats <= 4:
            by_month[mk].append(f"{dn}({seats})")
        else:
            by_month[mk].append(dn)
    return "\n".join(f"{mk}: {', '.join(days)}" for mk, days in by_month.items())


# ═══════════════════════════════════════════════════
# FORMATO 1: Alerta individual (compatibilidade)
# ═══════════════════════════════════════════════════
def format_alert_premium(alert, volta=None, show_fun_fact=True):
    orig_name, orig_flag = airport_display(alert["origin"])
    dest_name, dest_flag = airport_display(alert["destination"])
    mi = alert["miles"]; ti = alert.get("tax",0)
    source = alert["source"]; cabin = alert["cabin"]

    L = []
    tl = alert.get("tier_label", "")
    if tl:
        L.append(tl)
    L.append(f"\u2708\ufe0f {orig_name} ({alert['origin']}) {orig_flag} \u279c {dest_name} ({alert['destination']}) {dest_flag}")
    L.append("")
    L.append(f"\U0001f4ba {alert.get('cabin_name',cabin)} | {alert.get('companhia',source)} ({alert.get('programa',source)})")
    ev = alert.get("emit_via") or []
    if ev:
        L.append(f"\U0001f4b3 Emita via: {' ou '.join(ev)}")
    wr = alert.get("warn_reflect", "")
    if wr:
        L.append(f"⚠️ Pode nao estar refletindo award — confirme antes de emitir ({wr})")
    ag = alert.get("aegean", "")
    if ag:
        L.append(f"⭐ {ag}")
    sw = alert.get("sweet", "")
    if sw:
        L.append(f"🎯 {sw}")
    ue = alert.get("upgrade_exec", 0)
    if ue:
        L.append(f"🔼 Executiva também disponível ({fmt_miles(ue)} mi) — dá pra pedir "
                 f"a econômica e tentar UPGRADE (no Smiles costuma sair mais barato)")
    L.append("")
    L.append(f"\U0001f4b0 IDA: {fmt_miles(mi)} milhas + {fmt_tax(ti)}")

    total = mi
    if volta:
        mv = volta["miles"]; tv = volta.get("tax",0)
        L.append(f"\U0001f4b0 VOLTA: {fmt_miles(mv)} milhas + {fmt_tax(tv)}")
        total = mi + mv
        L.append(f"\U0001f4b0 TOTAL: {fmt_miles(total)} milhas + {fmt_tax(ti+tv)}")
    L.append("")

    # Custo real
    cm = MILHEIRO_CUSTO.get(source, 49)
    cr = (total / 1000) * cm
    region = alert.get("region","")
    cs = "economy" if cabin == "economy" else "business"
    pp = PASSAGEM_PAGA.get(f"{region}_{cs}", 0)
    if cr > 100:
        L.append(f"\U0001f4b5 Custo estimado: ~R$ {cr:,.0f}".replace(",","."))
        cash_brl = alert.get("cash_brl")
        if cash_brl:
            cu = alert.get("cash_usd") or 0
            car = alert.get("cash_carrier", "")
            L.append(f"\U0001f4b5 Passagem paga (Rove): ~US$ {cu:.0f} / R$ {cash_brl:,}".replace(",", ".")
                     + (f" — {car}" if car else ""))
            if cash_brl > cr:
                eco = ((cash_brl - cr) / cash_brl) * 100
                if eco > 5:
                    L.append(f"✅ Resgatando você economiza ~{eco:.0f}%")
        elif pp > 0 and cr < pp:
            eco = ((pp - cr) / pp) * 100
            if eco > 5:
                L.append(f"\U0001f4b5 Economia vs paga: ~{eco:.0f}%")
        L.append("")

    di = fmt_dates(alert.get("dates",[]));
    if di: L.append("\U0001f4c5 Datas de Ida:"); L.append(di)
    if volta:
        dv = fmt_dates(volta.get("dates",[]))
        if dv: L.append(""); L.append("\U0001f4c5 Datas de Volta:"); L.append(dv)

    if show_fun_fact:
        f = FUN_FACTS.get(alert["destination"],"")
        if f: L.append(""); L.append(f"\U0001f4a1 {f}")

    return "\n".join(L)


# ═══════════════════════════════════════════════════
# FORMATO 2: Alerta AGRUPADO (varios programas)
# ═══════════════════════════════════════════════════
def format_alert_grouped(origin, destination, cabin, cabin_name, programs_data, region="", show_fun_fact=True):
    orig_name, orig_flag = airport_display(origin)
    dest_name, dest_flag = airport_display(destination)

    L = []
    L.append(f"\u2708\ufe0f {orig_name} ({origin}) {orig_flag} \u279c {dest_name} ({destination}) {dest_flag}")
    L.append(f"\U0001f4ba {cabin_name}")
    L.append("")

    programs_data.sort(key=lambda x: x["miles_ida"])

    for i, p in enumerate(programs_data):
        mi = p["miles_ida"]; ti = p.get("tax_ida", 0)
        mv = p.get("miles_volta", 0); tv = p.get("tax_volta", 0)
        source = p["source"]

        tag = " (melhor)" if i == 0 and len(programs_data) > 1 else ""
        badge = f" {p['tier_label']}" if p.get("tier_label") else ""

        L.append(f"\U0001f3f7\ufe0f {p['programa']}{tag}{badge}")
        L.append(f"   IDA: {fmt_miles(mi)} milhas + {fmt_tax(ti)}")
        if mv > 0:
            total = mi + mv; tt = ti + tv
            L.append(f"   VOLTA: {fmt_miles(mv)} milhas + {fmt_tax(tv)}")
            L.append(f"   TOTAL: {fmt_miles(total)} milhas + {fmt_tax(tt)}")
        else:
            total = mi

        cm = MILHEIRO_CUSTO.get(source, 49)
        cr = (total / 1000) * cm
        if cr > 100:
            L.append(f"   Custo: ~R$ {cr:,.0f}".replace(",","."))
        cash_brl = p.get("cash_brl")
        if cash_brl:
            car = p.get("cash_carrier", "")
            L.append(f"   \U0001f4b5 Pago (Rove): ~R$ {cash_brl:,}".replace(",", ".") + (f" — {car}" if car else ""))

        ev = p.get("emit_via") or []
        if ev:
            L.append(f"   \U0001f4b3 Emita via: {' ou '.join(ev)}")

        wr = p.get("warn_reflect", "")
        if wr:
            L.append(f"   ⚠️ Pode nao refletir award — confirme ({wr})")

        ag = p.get("aegean", "")
        if ag:
            L.append(f"   ⭐ {ag}")

        sw = p.get("sweet", "")
        if sw:
            L.append(f"   🎯 {sw}")

        ue = p.get("upgrade_exec", 0)
        if ue:
            L.append(f"   🔼 Executiva disponível ({fmt_miles(ue)} mi) — pedir econômica e tentar upgrade")

        dates = p.get("dates_ida", [])
        if dates:
            seen = set(); by_m = defaultdict(list)
            for d in dates:
                dt = d.get("date","")
                if not dt or len(dt)<10 or dt in seen: continue
                parts = dt.split("-")
                if len(parts) != 3: continue
                seen.add(dt)
                y,m,day = parts
                by_m[f"{MONTHS_PT.get(m,m)}/{y[2:]}"].append(str(int(day)))
            date_parts = [f"{mk}: {', '.join(ds[:8])}" + ("..." if len(ds)>8 else "") for mk,ds in by_m.items()]
            if date_parts:
                L.append(f"   Datas: {' | '.join(date_parts[:3])}")

        L.append("")

    best = programs_data[0]
    best_total = best["miles_ida"] + best.get("miles_volta", 0)
    cm = MILHEIRO_CUSTO.get(best["source"], 49)
    cr = (best_total / 1000) * cm
    cs = "economy" if cabin == "economy" else "business"
    pp = PASSAGEM_PAGA.get(f"{region}_{cs}", 0)
    if pp > 0 and cr < pp and cr > 100:
        eco = ((pp - cr) / pp) * 100
        if eco > 5:
            L.append(f"\U0001f4b5 Passagem paga: ~R$ {pp:,} | Economia: ~{eco:.0f}%".replace(",","."))
            L.append("")

    if show_fun_fact:
        f = FUN_FACTS.get(destination, "")
        if f: L.append(f"\U0001f4a1 {f}")

    return "\n".join(L)


# ═══════════════════════════════════════════════════
# FORMATO 3: Alerta de QUEDA de preco — AGORA COM DATAS
# ═══════════════════════════════════════════════════
def format_price_drop(origin, destination, source, cabin, cabin_name,
                      current_price, previous_price, drop_pct,
                      dates_ida=None, dates_volta=None):
    """
    Alerta de queda de preco COM datas disponiveis.
    dates_ida/dates_volta: lista de dicts [{"date":"2026-07-15","seats":2}, ...]
    """
    orig_name, orig_flag = airport_display(origin)
    dest_name, dest_flag = airport_display(destination)
    _, programa = source_display(source)

    L = []
    L.append("\U0001f4c9\U0001f4c9 QUEDA DE PRECO! \U0001f4c9\U0001f4c9")
    L.append("")
    L.append(f"\u2708\ufe0f {orig_name} ({origin}) {orig_flag} \u279c {dest_name} ({destination}) {dest_flag}")
    L.append(f"\U0001f4ba {cabin_name} | {programa}")
    L.append("")
    L.append(f"\U0001f4b0 Antes: {fmt_miles(previous_price)} milhas")
    L.append(f"\U0001f4b0 Agora: {fmt_miles(current_price)} milhas")
    L.append(f"\U0001f4c9 Queda: {drop_pct:.0f}%")

    # ── DATAS DE IDA ──
    if dates_ida:
        di = fmt_dates(dates_ida)
        if di:
            L.append("")
            L.append("\U0001f4c5 Datas de Ida:")
            L.append(di)

    # ── DATAS DE VOLTA ──
    if dates_volta:
        dv = fmt_dates(dates_volta)
        if dv:
            L.append("")
            L.append("\U0001f4c5 Datas de Volta:")
            L.append(dv)

    L.append("")
    L.append("\u26a1 Corra! Quedas assim duram pouco!")

    return "\n".join(L)


# Compatibilidade
def format_alert(alert, show_fun_fact=True):
    return format_alert_premium(alert, volta=None, show_fun_fact=show_fun_fact)

def format_alert_ida_volta(alert, volta, show_fun_fact=True):
    return format_alert_premium(alert, volta=volta, show_fun_fact=show_fun_fact)
