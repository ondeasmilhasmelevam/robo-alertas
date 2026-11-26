# -*- coding: utf-8 -*-
"""Dry-run do runner: varre GIG-MAD e MOSTRA os alertas (não envia)."""
import sys, json
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import avios_runner

cfg = json.load(open("channels_config.json", encoding="utf-8"))
origin = sys.argv[1] if len(sys.argv) > 1 else "GIG"
dest = sys.argv[2] if len(sys.argv) > 2 else "MAD"
months = int(sys.argv[3]) if len(sys.argv) > 3 else 4
routes = [(origin, dest)]

alerts = avios_runner.run_once(cfg, log=print, send=False, routes=routes, months=months)
print(f"\n===== {len(alerts)} ALERTA(S) QUE SERIAM ENVIADOS =====")
for a in alerts:
    print("-" * 40)
    print(avios_runner.format_alert(a))
