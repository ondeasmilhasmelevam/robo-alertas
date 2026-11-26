# -*- coding: utf-8 -*-
"""Teste: varredura por rota nas cabines pedidas (economy + business)."""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import avios_api

origin = sys.argv[1] if len(sys.argv) > 1 else "GIG"
dest = sys.argv[2] if len(sys.argv) > 2 else "MAD"
months = int(sys.argv[3]) if len(sys.argv) > 3 else 4
cabins = ("economy", "business")

url0 = avios_api.build_results_url(origin, dest, year=2026, month=8, journey="Return")
proc = avios_api.start_chrome(url0, log=print)
pw, browser, ctx = avios_api.connect()
page = avios_api.get_page(ctx)
try:
    print(f"\n=== SCAN ROTA {origin}->{dest} {cabins} ({months} meses) ===")
    res = avios_api.scan_route(page, origin, dest, cabins=cabins, months=months, log=print)
    print(f"\nDatas com disponibilidade ({len(res)}):")
    for d in sorted(res):
        parts = []
        for cab in cabins:
            if cab in res[d]:
                parts.append(f"{cab}={res[d][cab]['avios']} ({res[d][cab]['seats']}a)")
        print(f"  {d}  " + "  ".join(parts))
finally:
    try:
        pw.stop()
    except Exception:
        pass
    if proc is not None:
        try:
            proc.terminate()
        except Exception:
            pass
