# -*- coding: utf-8 -*-
"""
Login único da Avios.com — roda no TERMINAL uma vez.
Abre um Chrome NORMAL (perfil dedicado .avios_profile/, com porta de depuração).
Como é um Chrome de verdade (não aberto pelo Playwright), o captcha do login
funciona normalmente. Você loga na sua conta, e a sessão fica salva no perfil.

Uso:
    python avios_login.py
"""
import time
import avios_api


def main():
    print("=" * 60)
    print(" LOGIN AVIOS.COM")
    print("=" * 60)
    print("Vai abrir um Chrome normal. Faça login na sua conta Avios/Iberia.")
    print("O captcha vai aparecer certinho (é um Chrome de verdade).")
    print("Quando terminar (logado, vendo seu saldo), volte AQUI e aperte ENTER.\n")

    proc = avios_api.start_chrome(
        "https://www.avios.com/es-ES/spend-avios/search-reward-flights", log=print
    )

    input("\n>>> Depois de logar no navegador, aperte ENTER aqui... ")

    # dá um tempinho pro Chrome gravar os cookies no perfil antes de fechar
    print("Salvando sessão...")
    time.sleep(2)
    if proc is not None:
        try:
            proc.terminate()
        except Exception:
            pass
    print("Perfil salvo em:", avios_api.PROFILE_DIR)
    print("Pronto! Agora me avise que eu rodo o teste. ✅")


if __name__ == "__main__":
    main()
