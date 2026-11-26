"""
Motor v6 — Agrupamento + Taxas reais + Alerta de queda COM DATAS
==================================================================
Correcao: alertas de queda agora buscam datas na API e exibem no alerta.
"""
import logging, time, json
from datetime import datetime, timedelta
from collections import defaultdict

from seats_api import SeatsAeroClient
from processor import process_results, get_destination_region, CABIN_FIELDS, CABIN_NAMES, parse_cost, source_display, get_smart_pricing, is_award, airport_display
from formatter import format_alert_premium, format_alert_grouped, format_price_drop, format_alert_ida_volta
from telegram_bot import TelegramBot
from history import AlertHistory
from price_records import PriceRecords
from melhores_destinos import fetch_md_promos, send_md_for_channel
from emission_tips import get_emission_tip, get_priority_programs

try:
    from config import SOURCES
except: SOURCES = []

logger = logging.getLogger("miles_bot")

_price_records = None
def get_price_records():
    global _price_records
    if _price_records is None: _price_records = PriceRecords()
    return _price_records


def _analyze_viagem(alert, volta, sp):
    """Analisa se ida+volta faz sentido."""
    ida = alert["miles"]
    vol = volta["miles"] if volta else 0
    if not volta or vol == 0:
        return {"send":True,"mode":"so_ida","reason":"Sem volta"}

    ev_ida = sp.evaluate(alert["origin"],alert["destination"],alert["source"],alert["cabin"],ida)
    ev_vol = sp.evaluate(alert["destination"],alert["origin"],alert["source"],alert["cabin"],vol)
    ic = ev_ida["classification"]; vc = ev_vol["classification"]
    ig = ic in ("espetacular","muito_bom","bom","desconhecido")
    vg = vc in ("espetacular","muito_bom","bom","desconhecido")
    ib = ic in ("caro","outlier"); vb = vc in ("caro","outlier")

    ratio = max(ida,vol)/min(ida,vol) if min(ida,vol)>0 else 1

    if ig and vg and ratio<3: return {"send":True,"mode":"ida_volta","reason":f"Equilibrada {ratio:.1f}x"}
    if ig and vb: return {"send":True,"mode":"so_ida","reason":f"Volta inflada ({vc})"}
    if vg and ib: return {"send":True,"mode":"so_volta","reason":f"Ida inflada ({ic})"}
    if ratio>3:
        if ida<=vol: return {"send":True,"mode":"so_ida","reason":f"Ratio {ratio:.1f}x"}
        else: return {"send":True,"mode":"so_volta","reason":f"Ratio {ratio:.1f}x"}
    if ib and vb: return {"send":False,"mode":"skip","reason":"Ambos ruins"}
    if ratio<2.5: return {"send":True,"mode":"ida_volta","reason":f"Normal {ratio:.1f}x"}
    if ida<=vol: return {"send":True,"mode":"so_ida","reason":"Borderline"}
    return {"send":True,"mode":"so_volta","reason":"Borderline"}


def _detect_price_drops(sp, origins, regions, cabin, callback=None):
    """Detecta quedas significativas de preco comparando com historico."""
    drops = []
    data = sp.data if hasattr(sp,'data') else {}

    for key, entry in data.items():
        stats = entry.get("stats",{})
        if stats.get("count",0) < 5: continue

        prices = entry.get("prices",[])
        if len(prices) < 2: continue

        origin = entry.get("origin","")
        dest = entry.get("destination","")
        source = entry.get("source","")
        ecabin = entry.get("cabin","")

        if ecabin != cabin: continue
        if origin not in origins: continue
        if get_destination_region(dest) not in regions: continue

        # Comparar ultimo preco com a media dos ultimos 10
        recent = [p["cost"] for p in prices[-1:]]
        older = [p["cost"] for p in prices[-11:-1]]

        if not recent or not older: continue

        current = recent[0]
        avg_old = sum(older) / len(older)

        if avg_old > 0:
            drop_pct = ((avg_old - current) / avg_old) * 100
            if drop_pct >= 25:  # Queda de 25% ou mais
                # SÓ alerta se o preço final também for bom em ABSOLUTO
                # (evita "queda" de 74k->38k num Rio-SP, que ainda é caríssimo).
                if not is_award(current, source, origin, dest, ecabin):
                    continue
                drops.append({
                    "origin":origin,"destination":dest,"source":source,
                    "cabin":ecabin,"current":current,
                    "previous":int(avg_old),"drop_pct":drop_pct,
                })

    drops.sort(key=lambda x: x["drop_pct"], reverse=True)
    return drops[:5]  # Top 5 maiores quedas


def _fetch_dates_for_drop(client, origin, destination, source, cabin, current_price):
    """
    Busca datas disponiveis na API para um alerta de queda.
    Retorna (dates_ida, dates_volta).
    Cada lista: [{"date":"2026-07-15","seats":2}, ...]
    """
    fields = CABIN_FIELDS.get(cabin, CABIN_FIELDS["business"])

    # ── BUSCAR DATAS DE IDA ──
    # Teto baseado no MENOR preço DISPONÍVEL AGORA (não no preço histórico da
    # queda). Antes usava current_price*1.10; se o preço subiu um pouco, cortava
    # TODAS as datas e o alerta saía sem datas.
    dates_ida = []
    try:
        results = client.cached_search(
            origin=origin, destination=destination,
            cabin=cabin, sources=source, take=500
        )
        rows = []
        for r in results:
            route = r.get("Route",{})
            rs = r.get("Source", route.get("Source",""))
            if rs != source: continue
            if not r.get(fields["avail"], False): continue
            cost = parse_cost(r.get(fields["cost"]))
            if cost is None or cost == 0: continue
            date = r.get("Date","")
            if isinstance(date, str) and "T" in date: date = date.split("T")[0]
            seats = r.get(fields["seats"], 0) or 0
            rows.append({"date": date, "seats": seats, "cost": cost})
        if rows:
            tol = min(x["cost"] for x in rows) * 1.10  # 10% acima do menor vivo
            dates_ida = [x for x in rows if x["cost"] <= tol]
    except Exception as e:
        logger.error(f"Erro ao buscar datas ida para queda {origin}->{destination}: {e}")

    dates_ida.sort(key=lambda x: x.get("date",""))

    # ── BUSCAR DATAS DE VOLTA ──
    dates_volta = []
    try:
        results_volta = client.cached_search(
            origin=destination, destination=origin,
            cabin=cabin, sources=source, take=500
        )
        # Pegar o menor preco da volta
        volta_costs = []
        for r in results_volta:
            route = r.get("Route",{})
            rs = r.get("Source", route.get("Source",""))
            if rs != source: continue
            if not r.get(fields["avail"], False): continue
            cost = parse_cost(r.get(fields["cost"]))
            if cost is None or cost == 0: continue
            volta_costs.append(cost)

        if volta_costs:
            min_volta = min(volta_costs)
            volta_tolerance = min_volta * 1.10

            for r in results_volta:
                route = r.get("Route",{})
                rs = r.get("Source", route.get("Source",""))
                if rs != source: continue
                if not r.get(fields["avail"], False): continue
                cost = parse_cost(r.get(fields["cost"]))
                if cost is None or cost == 0: continue
                if cost > volta_tolerance: continue

                date = r.get("Date","")
                if isinstance(date, str) and "T" in date: date = date.split("T")[0]
                seats = r.get(fields["seats"], 0) or 0
                dates_volta.append({"date": date, "seats": seats, "cost": cost})

    except Exception as e:
        logger.error(f"Erro ao buscar datas volta para queda {destination}->{origin}: {e}")

    dates_volta.sort(key=lambda x: x.get("date",""))

    return dates_ida, dates_volta


def run_cycle_for_channel(client, bot, channel, origins, max_alerts, callback=None):
    name = channel["name"]
    regions = channel["regions"]
    cabins = channel["cabins"]
    chat_id = channel["chat_id"]
    channel_programs = channel.get("programs", SOURCES)

    pr = get_price_records(); sp = get_smart_pricing()

    def log(msg):
        logger.info(f"[{name}] {msg}")
        if callback: callback(f"[{name}] {msg}")

    log(f"Iniciando busca | Regioes: {', '.join(regions)} | Cabines: {', '.join(cabins)} | {len(channel_programs)} programas")

    bot_ch = bot.for_chat(chat_id)
    hfile = f"historico_{name.replace(' ','_').replace('/','_').replace(chr(92),'_').lower()}.json"
    history = AlertHistory(hfile)

    # Preço PAGO (Rove): popula o cache 1x por canal, se ligado. Tolerante a erro.
    try:
        import rove_api
        if rove_api.load_cfg().get("rove_enabled"):
            rove_api.build_cash_cache(regions, channel.get("origins", origins), log=log)
    except Exception as e:
        log(f"Rove indisponível (segue sem preço pago): {e}")

    all_alerts = []
    source_stats = {}

    for cabin in cabins:
        log(f"--- {CABIN_NAMES.get(cabin,cabin)} ---")
        ordered = get_priority_programs(regions[0] if regions else "", cabin, channel_programs)

        for source in ordered:
            sk = f"{source}/{cabin}"
            source_stats[sk] = {"raw":0,"filtered":0,"awards":0,"error":None}
            t0 = time.time()
            try:
                results = client.bulk_availability(source=source,cabin=cabin,origin_region="South America",take=1000)
                filtered = [r for r in results if r.get("Route",{}).get("OriginAirport",r.get("OriginAirport","")) in origins]
                source_stats[sk]["raw"]=len(results); source_stats[sk]["filtered"]=len(filtered)

                if filtered:
                    alerts = process_results(results=filtered,origin_airports=origins,cabin=cabin)
                    alerts = [a for a in alerts if get_destination_region(a["destination"]) in regions]
                    source_stats[sk]["awards"]=len(alerts)
                    all_alerts.extend(alerts)

                el = round(time.time()-t0,1)
                s=source_stats[sk]
                if s["filtered"]>0 or s["awards"]>0:
                    log(f"  {source:18s} | {s['raw']:4d} bruto | {s['filtered']:3d} origem | {s['awards']:2d} awards | {el}s")
            except Exception as e:
                source_stats[sk]["error"]=str(e)
                log(f"  {source:18s} | ERRO: {e}")
            time.sleep(0.8)

    log(f"Total: {len(all_alerts)} awards")

    # Erros
    errs = {k:v for k,v in source_stats.items() if v.get("error")}
    if errs:
        for k,v in errs.items(): log(f"  ERRO {k}: {v['error']}")

    # SmartPricing stats
    sps = sp.get_summary()
    log(f"SmartPricing: {sps['total_routes']} rotas | {sps['routes_with_baseline']} com baseline")

    # Filtrar novos
    new_alerts = [a for a in all_alerts if history.is_new(a)]
    log(f"{len(new_alerts)} novos de {len(all_alerts)}")

    # ═══ FILTRO INTELIGENTE: só envia se preço for igual ou melhor que o último enviado ═══
    worthy_alerts = []
    blocked_count = 0
    for a in new_alerts:
        if history.is_price_worth_sending(a):
            worthy_alerts.append(a)
        else:
            blocked_count += 1
    if blocked_count > 0:
        log(f"{blocked_count} alertas bloqueados (preço pior que o melhor recente)")
    new_alerts = worthy_alerts

    if not new_alerts and not any(c in cabins for c in cabins):
        log("Nenhum alerta novo.")

    # ═══ AGRUPAMENTO ═══════════════════════════════
    route_groups = defaultdict(list)
    for a in new_alerts:
        rk = (a["origin"], a["destination"], a["cabin"])
        route_groups[rk].append(a)

    top_alerts = []
    for rk, group in route_groups.items():
        group.sort(key=lambda x: x["miles"])
        top_alerts.extend(group[:5])

    biz_routes = defaultdict(list)
    eco_routes = defaultdict(list)
    first_routes = defaultdict(list)

    for a in top_alerts:
        rk = (a["origin"], a["destination"])
        if a["cabin"] == "business": biz_routes[rk].append(a)
        elif a["cabin"] == "economy": eco_routes[rk].append(a)
        else: first_routes[rk].append(a)

    def sort_routes(routes_dict):
        items = list(routes_dict.items())
        items.sort(key=lambda x: min(a["miles"] for a in x[1]))
        return items[:max_alerts]

    routes_to_send = sort_routes(biz_routes) + sort_routes(eco_routes) + sort_routes(first_routes)

    if not routes_to_send:
        log("Nenhuma rota para enviar.")
        # Verificar quedas mesmo sem novos alertas
        for cabin in cabins:
            drops = _detect_price_drops(sp, origins, regions, cabin, callback)
            for drop in drops:
                # Verificar se ja enviou
                if not history.is_new({"origin":drop["origin"],"destination":drop["destination"],
                    "source":drop["source"]+"_drop","cabin":drop["cabin"],"miles":drop["current"]}):
                    continue

                # ── BUSCAR DATAS NA API ──
                log(f"  Buscando datas para queda {drop['origin']}->{drop['destination']} {drop['source']}...")
                dates_ida, dates_volta = _fetch_dates_for_drop(
                    client, drop["origin"], drop["destination"],
                    drop["source"], drop["cabin"], drop["current"]
                )
                log(f"  Datas ida: {len(dates_ida)} | Datas volta: {len(dates_volta)}")
                if not dates_ida and not dates_volta:
                    log("  (sem datas disponíveis — queda velha, pulando)")
                    continue

                msg = format_price_drop(
                    drop["origin"], drop["destination"], drop["source"],
                    drop["cabin"], CABIN_NAMES.get(drop["cabin"],""),
                    drop["current"], drop["previous"], drop["drop_pct"],
                    dates_ida=dates_ida if dates_ida else None,
                    dates_volta=dates_volta if dates_volta else None,
                )
                if bot_ch.send_message(msg):
                    # Marcar como enviado
                    history.mark_sent({"origin":drop["origin"],"destination":drop["destination"],
                        "source":drop["source"]+"_drop","cabin":drop["cabin"],"miles":drop["current"],
                        "dates":[]})
                    time.sleep(2)
                    log(f"  QUEDA: {drop['origin']}->{drop['destination']} {drop['source']} -{drop['drop_pct']:.0f}% ({fmt_m(drop['previous'])} -> {fmt_m(drop['current'])})")
                time.sleep(1)
        return 0

    log(f"Rotas para enviar: {len(routes_to_send)}")

    # Buscar voltas
    log("Buscando voltas...")
    return_flights = _find_returns(client, top_alerts, cabins)
    log(f"Volta para {len(return_flights)} rotas")

    # Enviar
    sent = 0
    all_sent_alerts = []

    for (orig, dest), alerts_group in routes_to_send:
        cabin = alerts_group[0]["cabin"]
        cabin_name = alerts_group[0].get("cabin_name", cabin)

        if len(alerts_group) >= 2:
            # FORMATO AGRUPADO
            programs_data = []
            for a in alerts_group:
                key = (a["destination"], a["origin"], a["source"])
                volta = return_flights.get(key)

                analysis = _analyze_viagem(a, volta, sp)
                if not analysis["send"]: continue

                pd = {
                    "source":a["source"],"programa":a.get("programa",""),
                    "companhia":a.get("companhia",""),
                    "miles_ida":a["miles"],"tax_ida":a.get("tax",0),
                    "dates_ida":a.get("dates",[]),
                    "tier_label":a.get("tier_label",""),"emit_via":a.get("emit_via",[]),
                    "warn_reflect":a.get("warn_reflect",""),"aegean":a.get("aegean",""),
                    "sweet":a.get("sweet",""),"upgrade_exec":a.get("upgrade_exec",0),
                    "cash_usd":a.get("cash_usd"),"cash_brl":a.get("cash_brl"),"cash_carrier":a.get("cash_carrier",""),
                }
                if analysis["mode"] == "ida_volta" and volta:
                    pd["miles_volta"] = volta["miles"]
                    pd["tax_volta"] = volta.get("tax",0)
                    pd["dates_volta"] = volta.get("dates",[])
                else:
                    pd["miles_volta"] = 0; pd["tax_volta"] = 0

                programs_data.append(pd)
                all_sent_alerts.append(a)

                pr.check_and_update(a["origin"],a["destination"],a["source"],a["cabin"],a["miles"])

            if programs_data:
                msg = format_alert_grouped(orig, dest, cabin, cabin_name, programs_data, region=alerts_group[0].get("region",""))
                if bot_ch.send_message(msg): sent += 1
                time.sleep(2)
        else:
            # FORMATO INDIVIDUAL
            a = alerts_group[0]
            key = (a["destination"], a["origin"], a["source"])
            volta = return_flights.get(key)

            analysis = _analyze_viagem(a, volta, sp)
            if not analysis["send"]: continue

            if analysis["mode"] == "ida_volta" and volta:
                msg = format_alert_ida_volta(a, volta)
            else:
                msg = format_alert_premium(a, volta=None)

            ri = pr.check_and_update(a["origin"],a["destination"],a["source"],a["cabin"],a["miles"])
            if ri["is_record"]:
                msg = "\U0001f525\U0001f525 PRECO RECORDE!\n\n" + msg
            elif ri["is_near_record"]:
                msg = "\u26a1 Proximo do recorde!\n\n" + msg

            tip = get_emission_tip(a["source"],a.get("region",""),a["cabin"])
            if tip: msg += f"\n\n\U0001f4a1 {tip}"

            if bot_ch.send_message(msg): sent += 1
            all_sent_alerts.append(a)
            time.sleep(2)

    # Marcar como enviados
    history.mark_batch(all_sent_alerts)
    history.cleanup(days=14)

    log(f"Enviados: {sent} mensagens")

    # ═══ ALERTA DE QUEDA ═══════════════════════════
    for cabin in cabins:
        drops = _detect_price_drops(sp, origins, regions, cabin, callback)
        for drop in drops:
            # Verificar se ja enviou
            if not history.is_new({"origin":drop["origin"],"destination":drop["destination"],
                "source":drop["source"]+"_drop","cabin":drop["cabin"],"miles":drop["current"]}):
                continue

            # ── BUSCAR DATAS NA API ──
            log(f"  Buscando datas para queda {drop['origin']}->{drop['destination']} {drop['source']}...")
            dates_ida, dates_volta = _fetch_dates_for_drop(
                client, drop["origin"], drop["destination"],
                drop["source"], drop["cabin"], drop["current"]
            )
            log(f"  Datas ida: {len(dates_ida)} | Datas volta: {len(dates_volta)}")
            if not dates_ida and not dates_volta:
                log("  (sem datas disponíveis — queda velha, pulando)")
                continue

            msg = format_price_drop(
                drop["origin"], drop["destination"], drop["source"],
                drop["cabin"], CABIN_NAMES.get(drop["cabin"],""),
                drop["current"], drop["previous"], drop["drop_pct"],
                dates_ida=dates_ida if dates_ida else None,
                dates_volta=dates_volta if dates_volta else None,
            )
            if bot_ch.send_message(msg):
                sent += 1
                # Marcar como enviado
                history.mark_sent({"origin":drop["origin"],"destination":drop["destination"],
                    "source":drop["source"]+"_drop","cabin":drop["cabin"],"miles":drop["current"],
                    "dates":[]})
                log(f"  QUEDA: {drop['origin']}->{drop['destination']} {drop['source']} -{drop['drop_pct']:.0f}% ({fmt_m(drop['previous'])} -> {fmt_m(drop['current'])})")
            time.sleep(2)

    return sent


def fmt_m(m): return f"{m:,}".replace(",",".")


def _find_returns(client, alerts, cabins):
    ret = {}; seen = set()
    sp = get_smart_pricing()

    for a in alerts:
        k = (a["destination"],a["origin"],a["source"],a["cabin"])
        if k in seen: continue
        seen.add(k)
        dest,origin,source,cabin = k
        fields = CABIN_FIELDS.get(cabin, CABIN_FIELDS["business"])

        results = client.cached_search(origin=dest,destination=origin,cabin=cabin,sources=source,take=500)
        if not results: time.sleep(0.5); continue

        entries = []
        for r in results:
            route = r.get("Route",{})
            rs = r.get("Source",route.get("Source",""))
            if rs != source: continue
            if not r.get(fields["avail"],False): continue
            cost = parse_cost(r.get(fields["cost"]))
            if cost is None or cost==0: continue
            date = r.get("Date","")
            if isinstance(date,str) and "T" in date: date = date.split("T")[0]
            seats = r.get(fields["seats"],0) or 0
            tax = r.get(fields["tax"],0) or 0
            entries.append({"date":date,"seats":seats,"cost":cost,"tax":tax})
            sp.record_price(dest,origin,source,cabin,cost)

        if entries:
            entries.sort(key=lambda x:x["date"])
            mn = min(e["cost"] for e in entries)
            tol = mn * 1.10
            good = [e for e in entries if e["cost"]<=tol] or [e for e in entries if e["cost"]==mn]
            taxes = [e["tax"] for e in good if e["tax"]>0]
            mt = taxes[0] if taxes else 0
            comp,prog = source_display(source)
            ret[(dest,origin,source)] = {
                "origin":dest,"destination":origin,"source":source,
                "companhia":comp,"programa":prog,
                "cabin":cabin,"cabin_name":CABIN_NAMES.get(cabin,cabin),
                "miles":mn,"tax":mt,"tax_currency":"BRL",
                "dates":[{"date":e["date"],"seats":e["seats"]} for e in good],
            }
        time.sleep(0.5)

    sp.save_periodically()
    return ret


def run_melhores_destinos(bot, channels, callback=None):
    def log(msg):
        logger.info(msg)
        if callback: callback(msg)
    md_chs = [c for c in channels if c.get("enabled",True) and c.get("melhores_destinos",False)]
    if not md_chs: return 0
    log(""); log("="*40); log("Melhores Destinos...")
    try:
        promos = fetch_md_promos(callback=callback)
        if not promos: log("[MD] Nenhuma promo"); return 0
        total = 0
        for ch in md_chs:
            total += send_md_for_channel(promos, bot, ch, callback=callback)
        return total
    except Exception as e: log(f"[MD] Erro: {e}"); return 0


# ═══════════════════════════════════════════════════════════════
# VARREDURA AGENDADA — IBERIA / BRITISH / QATAR (21h)
# ═══════════════════════════════════════════════════════════════

SCHEDULED_SCAN_SOURCES = ["iberia", "british", "qatar"]

def run_iberia_scan(client, bot, channels, origins, max_alerts, callback=None):
    """
    Varredura rápida focada em Iberia, British Airways e Qatar.
    Roda nos canais que têm esses programas habilitados.
    """
    def log(msg):
        logger.info(msg)
        if callback: callback(msg)

    log("")
    log("=" * 50)
    log("✈️  VARREDURA IBERIA/BRITISH/QATAR — Liberação 21h")
    log("=" * 50)

    total_enviados = 0

    for channel in channels:
        if not channel.get("enabled", True):
            continue

        ch_programs = channel.get("programs", SOURCES)
        # Verificar se canal tem iberia, british ou qatar habilitados
        scan_programs = [s for s in SCHEDULED_SCAN_SOURCES if s in ch_programs]
        if not scan_programs:
            continue

        name = channel["name"]
        regions = channel["regions"]
        cabins = channel["cabins"]
        chat_id = channel["chat_id"]

        bot_ch = bot.for_chat(chat_id)
        hfile = f"historico_{name.replace(' ','_').replace('/','_').replace(chr(92),'_').lower()}.json"
        history = AlertHistory(hfile)
        pr = get_price_records()
        sp = get_smart_pricing()

        log(f"[{name}] Scan 21h | Programas: {', '.join(scan_programs)} | Cabines: {', '.join(cabins)}")

        all_alerts = []

        for cabin in cabins:
            for source in scan_programs:
                t0 = time.time()
                try:
                    results = client.bulk_availability(source=source, cabin=cabin, origin_region="South America", take=1000)
                    filtered = [r for r in results if r.get("Route", {}).get("OriginAirport", r.get("OriginAirport", "")) in origins]

                    if filtered:
                        alerts = process_results(results=filtered, origin_airports=origins, cabin=cabin)
                        alerts = [a for a in alerts if get_destination_region(a["destination"]) in regions]
                        all_alerts.extend(alerts)

                    elapsed = time.time() - t0
                    log(f"[{name}]   {source:18s} | {len(results)} bruto | {len(filtered)} origem | {len(alerts) if filtered else 0} awards | {elapsed:.1f}s")
                    time.sleep(0.5)

                except Exception as e:
                    log(f"[{name}]   {source} ERRO: {e}")

        if not all_alerts:
            log(f"[{name}] Nenhum award na varredura 21h")
            continue

        # Filtrar novos e com preço válido
        new_alerts = [a for a in all_alerts if history.is_new(a)]
        worthy_alerts = [a for a in new_alerts if history.is_price_worth_sending(a)]

        log(f"[{name}] {len(all_alerts)} awards | {len(new_alerts)} novos | {len(worthy_alerts)} para enviar")

        if not worthy_alerts:
            continue

        # Agrupar e enviar (mesmo fluxo do ciclo normal)
        route_groups = defaultdict(list)
        for a in worthy_alerts:
            rk = (a["origin"], a["destination"], a["cabin"])
            route_groups[rk].append(a)

        top_alerts = []
        for rk, group in route_groups.items():
            group.sort(key=lambda x: x["miles"])
            top_alerts.extend(group[:5])

        top_alerts.sort(key=lambda x: x["miles"])
        top_alerts = top_alerts[:max_alerts]

        # Buscar voltas.
        # CONSERTADO 26/11/2026: aqui chamava search_return_flights(), que nao
        # existe em lugar nenhum — a varredura morria com NameError toda vez
        # que achava alguma passagem. Usa a mesma _find_returns() do ciclo
        # completo, cuja chave e (destino, origem, programa) — sem a cabine.
        log(f"[{name}] Buscando voltas...")
        return_flights = _find_returns(client, top_alerts, cabins)
        log(f"[{name}] Volta para {len(return_flights)} rotas")

        # Formatar e enviar
        from formatter import format_alert_ida_volta
        enviados = 0
        for a in top_alerts:
            try:
                volta = return_flights.get((a["destination"], a["origin"], a["source"]))
                # Mesmo criterio do ciclo completo: ida inflada ou os dois
                # lados caros nao vao pro grupo.
                analise = _analyze_viagem(a, volta, sp)
                if not analise["send"]:
                    log(f"[{name}] pulado {a['origin']}->{a['destination']} "
                        f"{a['source']}: {analise['reason']}")
                    continue
                if analise["mode"] == "so_ida":
                    volta = None
                msg = format_alert_ida_volta(a, volta)
                if bot_ch.send_message(msg):
                    history.mark_sent(a)
                    # CONSERTADO 26/11/2026: chamava pr.check_and_update(a),
                    # mas a funcao pede os campos separados (igual no ciclo
                    # completo, linhas 389 e 409). Dava TypeError e o alerta
                    # ja enviado nao entrava no registro de recorde.
                    pr.check_and_update(a["origin"], a["destination"],
                                        a["source"], a["cabin"], a["miles"])
                    enviados += 1
            except Exception as e:
                log(f"[{name}] Erro envio: {e}")

        log(f"[{name}] Enviados: {enviados} alertas (varredura 21h)")
        total_enviados += enviados

    log(f"Varredura 21h concluída | Total: {total_enviados} alertas")
    return total_enviados


# ═══════════════════════════════════════════════════════════════
# RESUMO SEMANAL — sexta-feira
# ═══════════════════════════════════════════════════════════════

_REGIAO_NOME = {
    "brasil": "Brasil", "europa": "Europa", "eua": "EUA / Canadá",
    "asia": "Ásia / Oriente Médio", "america_sul": "América do Sul",
    "america_central": "América Central / Caribe", "africa": "África",
    "oceania": "Oceania",
}


def _hist_file_for(name):
    return f"historico_{name.replace(' ', '_').replace('/', '_').replace(chr(92), '_').lower()}.json"


def run_weekly_summary(bot, channels, days=7, callback=None):
    """
    Resumo BREVE da semana, por canal: oportunidades enviadas nos ultimos
    'days' dias (lidas dos historico_*.json). Enviado ao Telegram e, como
    tudo passa pelo TelegramBot, espelhado automaticamente no Discord.
    """
    def log(msg):
        logger.info(msg)
        if callback:
            callback(msg)

    log("")
    log("=" * 50)
    log("📊 RESUMO SEMANAL — sexta-feira")
    log("=" * 50)

    cutoff = datetime.now() - timedelta(days=days)
    ini = cutoff.strftime("%d/%m")
    fim = datetime.now().strftime("%d/%m")
    total_geral = 0

    for channel in channels:
        if not channel.get("enabled", True):
            continue
        name = channel["name"]
        chat_id = channel["chat_id"]

        try:
            with open(_hist_file_for(name), "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        alerts = data.get("alerts", {}) if isinstance(data, dict) else {}

        # Melhor (menor) milhagem por rota+programa dentro da janela.
        best = {}
        for v in alerts.values():
            try:
                if datetime.fromisoformat(v.get("sent_at", "")) < cutoff:
                    continue
            except Exception:
                continue
            rk = (v.get("route", ""), v.get("source", ""))
            miles = v.get("miles", 0) or 0
            if rk not in best or miles < best[rk]:
                best[rk] = miles

        if not best:
            continue

        total = len(best)
        total_geral += total
        destaques = sorted(best.items(), key=lambda x: x[1])[:6]

        L = ["📊 RESUMO DA SEMANA"]
        regs = ", ".join(_REGIAO_NOME.get(r, r) for r in channel.get("regions", []))
        if regs:
            L.append(regs)
        L.append(f"🗓️ {ini} a {fim}")
        L.append("")
        L.append(f"✈️ {total} oportunidade(s) de destaque")
        L.append("")
        L.append("🔥 Melhores da semana:")
        for (route, source), miles in destaques:
            _, prog = source_display(source.replace("_drop", ""))  # alertas de queda
            parts = route.split("->")
            if len(parts) == 2:
                rota = f"{airport_display(parts[0])[0]} → {airport_display(parts[1])[0]}"
            else:
                rota = route
            m = f"{miles:,}".replace(",", ".")
            L.append(f"• {rota}: {m} milhas ({prog})")
        L.append("")
        L.append("Bons voos! ✈️ — Onde As Milhas Me Levam")
        msg = "\n".join(L)

        try:
            if bot.for_chat(chat_id).send_message(msg):
                log(f"[{name}] Resumo enviado ({total} oportunidades).")
        except Exception as e:
            log(f"[{name}] Erro ao enviar resumo: {e}")
        time.sleep(1)

    log(f"Resumo semanal concluído | {total_geral} oportunidades no total.")
    return total_geral
