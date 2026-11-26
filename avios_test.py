# -*- coding: utf-8 -*-
"""
Teste de calibração da Avios.com — roda no TERMINAL depois do login.
Sobe o Chrome real (perfil já logado), conecta via CDP, abre a página de
resultados de uma rota/data e mostra:
  - o que o JSON interceptado trouxe (disponibilidade por cabine)
  - os preços que apareceram no DOM (pra bater com o que você vê na tela)

Uso:
    python avios_test.py                 (GIG->MAD 2026-10-22)
    python avios_test.py GRU LIS 2026-11-15
    python avios_test.py --auto          (não espera ENTER; pra automação)
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import avios_api


def main():
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    origin = pos[0] if len(pos) > 0 else "GIG"
    dest = pos[1] if len(pos) > 1 else "MAD"
    date = pos[2] if len(pos) > 2 else "2026-10-22"

    print("=" * 60)
    print(f" TESTE AVIOS  {origin}->{dest}  {date}")
    print("=" * 60)

    proc = avios_api.start_chrome(
        avios_api.build_results_url(origin, dest, date), log=print
    )
    pw, browser, ctx = avios_api.connect()
    page = avios_api.get_page(ctx)
    try:
        availability, precos, raw, body, dom_flights = avios_api.fetch_route(
            page, origin, dest, date, log=print, wait_ms=10000
        )

        print("\n--- VOOS LIDOS DA TELA (DOM) ---")
        if dom_flights:
            for fl in dom_flights:
                print(f"  Voo {fl['carrier']}{fl['flight'][2:]}:")
                for fr in fl["fares"]:
                    st = (f"{fr['avios']} Avios / {fr['seats']} assentos"
                          if fr["available"] else "Agotado/indisponível")
                    print(f"     {fr['family']:8s} ({fr['cabin']:8s}) -> {st}")
        else:
            print("  (não consegui ler voos do DOM)")

        print("\n--- RESUMO POR CABINE (melhor opção) ---")
        best = avios_api.best_by_cabin(dom_flights)
        if best:
            for cab, info in best.items():
                print(f"  {cab:9s} {info['avios']} Avios ({info['seats']} assentos) "
                      f"voo {info['carrier']}{info['flight'][2:]}")
        else:
            print("  (nada disponível)")

        print("\n--- (debug) números crus no DOM ---")
        print("  ", precos if precos else "(nenhum)")

        with open("avios_debug.txt", "w", encoding="utf-8") as f:
            f.write("URL: " + avios_api.build_results_url(origin, dest, date) + "\n\n")
            f.write("=== RAW JSON INTERCEPTADO ===\n")
            f.write((raw or "(nada)") + "\n\n")
            f.write("=== BODY TEXT (primeiros 6000 chars) ===\n")
            f.write((body or "")[:6000])
        print("\n📄 Detalhes crus salvos em avios_debug.txt")

    finally:
        try:
            pw.stop()
        except Exception:
            pass
        if "--auto" not in sys.argv:
            try:
                input("\n>>> ENTER pra fechar o navegador... ")
            except EOFError:
                pass
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    main()
