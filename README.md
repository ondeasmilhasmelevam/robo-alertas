# Onde As Milhas Me Levam — robô de alertas

Robô que procura passagens com milhas em promoção e manda pros grupos do Telegram.
Roda sozinho na nuvem (GitHub Actions), de graça, sem precisar abrir nada no computador.

## Horários (hora de Brasília)

| Hora  | O que faz                                  |
|-------|--------------------------------------------|
| 21h   | varredura completa                         |
| 0h    | varredura completa                         |
| 2h    | varredura completa                         |
| 3h    | varredura completa                         |
| 6h    | varredura completa                         |

O GitHub pode atrasar alguns minutos quando está cheio — é normal, não é erro.
Pra forçar uma busca fora de hora: aba **Actions** → **Busca de alertas** → **Run workflow**.

## O filtro (régua)

Só sai alerta que a régua do painel classifica como **boa, muito boa ou espetacular**.
Se não existe régua pra aquela rota/cabine, **não sai alerta** (`exigir_regua: true` no
`rules_config.json`). Avios (Iberia / British / Qatar) não passa pela régua do painel:
usa a tabela oficial de distância, só a tarifa de baixa temporada (`avios_chart.py`).

## Os arquivos

| Arquivo | Pra que serve |
|---|---|
| `run_cycle.py` | roda **um** ciclo e sai. É o que a nuvem chama. |
| `engine.py` | o motor: busca, filtra, formata e envia |
| `termometro.py` | a régua de preços (painel + programas) |
| `distance_service.py` | distância entre aeroportos + tarifa Avios por banda |
| `avios_chart.py` | tabela oficial de milhas por rota (Iberia/British/Qatar) |
| `processor.py` | decide se é oferta de verdade (modo estrito) |
| `channels_config.json` | canais, origens, cabines, programas — **não vai pro git** |
| `compactar_estado.py` | enxuga o histórico de preços quando ele cresce |
| `avios_*.py` | varredura do site da Avios — **só roda no PC** (precisa do Chrome logado) |

## Segredos

Nada de chave em texto puro no repositório. Na nuvem tudo vem dos **Secrets** do GitHub
(`Settings → Secrets and variables → Actions`), e o `channels.py` troca pelo valor da
variável de ambiente quando ela existe:

| Secret | De onde vem |
|---|---|
| `CHANNELS_CONFIG` | o conteúdo inteiro do `channels_config.json` |
| `SEATS_API_KEY` | seats.aero |
| `TELEGRAM_BOT_TOKEN` | BotFather |
| `AVIOS_ADMIN_CHAT` | seu chat privado pra avisos técnicos (opcional) |

## O estado

- `historico_*.json` (pequenos) — ficam **no repositório**, o robô grava de volta a cada
  execução. É o que evita repetir o mesmo alerta.
- `pricing_history.json` / `price_records.json` (4,6 MB) — ficam no **cache do Actions**,
  não no git.

## Rodar no computador

```
python run_cycle.py --teste          # mostra na tela, não manda no Telegram
python run_cycle.py --canal Europa   # só um canal
python painel.py                     # a janela de sempre
```
