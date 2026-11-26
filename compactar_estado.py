# -*- coding: utf-8 -*-
"""
compactar_estado.py — enxuga os arquivos de estado que crescem sem parar.
==========================================================================
O `pricing_history.json` passou de 10 MB porque guarda até 100 preços por rota,
com data em microssegundos e JSON indentado. Rodando na nuvem isso é commitado /
cacheado a cada ciclo, então vale manter pequeno.

O que faz (sem perder o que importa):
  • mantém só os N preços mais recentes de cada rota (padrão 40)
  • corta a data no segundo (microssegundo não serve pra nada aqui)
  • grava compacto, sem indentação

Uso:
    python compactar_estado.py              # aplica (padrão 40 por rota)
    python compactar_estado.py --manter 60  # outro limite
    python compactar_estado.py --simular    # só mostra o ganho, não grava
"""
import argparse
import json
import os

ARQUIVOS = ("pricing_history.json", "price_records.json")


def _mb(caminho):
    return os.path.getsize(caminho) / 1024 / 1024 if os.path.exists(caminho) else 0.0


def compactar(manter=40, simular=False):
    total_antes = total_depois = 0.0
    for arq in ARQUIVOS:
        if not os.path.exists(arq):
            continue
        antes = _mb(arq)
        total_antes += antes
        try:
            with open(arq, encoding="utf-8") as f:
                dados = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"  {arq}: não consegui ler ({e}) — deixando como está")
            total_depois += antes
            continue

        if isinstance(dados, dict):
            for registro in dados.values():
                if not isinstance(registro, dict):
                    continue
                precos = registro.get("prices")
                if isinstance(precos, list):
                    if len(precos) > manter:
                        registro["prices"] = precos[-manter:]
                    for p in registro["prices"]:
                        if isinstance(p, dict) and isinstance(p.get("date"), str):
                            p["date"] = p["date"][:19]   # 2026-11-25T16:39:11

        texto = json.dumps(dados, separators=(",", ":"), ensure_ascii=False)
        if not simular:
            tmp = arq + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(texto)
            os.replace(tmp, arq)      # troca atômica: não corrompe se cair no meio
            depois = _mb(arq)
        else:
            depois = len(texto.encode()) / 1024 / 1024
        total_depois += depois
        print(f"  {arq:<24} {antes:6.2f} MB -> {depois:6.2f} MB")

    if total_antes:
        economia = (1 - total_depois / total_antes) * 100
        print(f"  {'TOTAL':<24} {total_antes:6.2f} MB -> {total_depois:6.2f} MB "
              f"({economia:.0f}% menor){'  [simulação]' if simular else ''}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Enxuga os arquivos de estado do bot.")
    ap.add_argument("--manter", type=int, default=40, help="preços por rota (padrão 40)")
    ap.add_argument("--simular", action="store_true", help="só mostra, não grava")
    args = ap.parse_args()
    compactar(args.manter, args.simular)
