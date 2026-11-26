# Como colocar o robô pra rodar na nuvem

Três coisas. Uns 5 minutos.

---

## 1) Criar o repositório (você, no navegador)

Abra **https://github.com/organizations/ondeasmilhasmelevam/repositories/new**

- **Repository name:** `robo-alertas`
- **Public** ← precisa ser público. É o que dá minuto de graça pra sempre no
  GitHub Actions. Privado dá 2.000 min/mês e o robô estouraria isso.
- **NÃO** marque "Add a README file", "Add .gitignore" nem licença. O repositório
  tem que nascer vazio, senão dá conflito na hora de subir.
- Create repository.

> Pode ser na sua conta pessoal (`w-marcal/robo-alertas`) em vez da organização.
> Se escolher assim, troque o endereço no passo 2.

---

## 2) Subir o código

Cole no PowerShell, uma linha por vez:

```powershell
cd "C:\Sistema Viagem\Onde As Milhas Me Levam"
```

```powershell
git remote add origin https://github.com/ondeasmilhasmelevam/robo-alertas.git
```

```powershell
git push -u origin main
```

Se pedir login, é o do GitHub mesmo.

---

## 3) Guardar as chaves (Secrets)

As chaves **não** estão no código (de propósito — o repositório é público).
Elas vão num cofre do GitHub.

Primeiro copie o arquivo de configuração pra área de transferência:

```powershell
Get-Content "C:\Sistema Viagem\Onde As Milhas Me Levam\channels_config.json" -Raw | Set-Clipboard
```

Agora abra
**https://github.com/ondeasmilhasmelevam/robo-alertas/settings/secrets/actions**
e clique em **New repository secret**:

- **Name:** `CHANNELS_CONFIG`
- **Secret:** Ctrl+V (é o arquivo inteiro que você acabou de copiar)
- Add secret.

Pronto. Esse único segredo já carrega a chave da seats.aero, o token do bot do
Telegram e os chat_id dos grupos.

> Quiser trocar uma chave depois sem mexer no arquivo todo? Crie um segredo
> separado com o nome dela (`SEATS_API_KEY`, `TELEGRAM_BOT_TOKEN`, …). O que
> está no segredo separado vence o que está no `CHANNELS_CONFIG`.

---

## 4) Testar antes de deixar solto

**https://github.com/ondeasmilhasmelevam/robo-alertas/actions**

→ **Busca de alertas** → **Run workflow** → marque **teste** → **Run workflow**.

Em modo teste ele procura de verdade mas **não manda nada pro Telegram** — só
escreve na tela o que teria mandado. Clique na execução pra acompanhar.

Se ficou bom, roda de novo **sem** marcar teste, e a partir daí ele vai sozinho
às 21h, 0h, 2h, 3h e 6h (hora de Brasília).

---

## O que fica fora da nuvem

A varredura do site da **Avios** continua só no computador: ela precisa de um
Chrome logado na sua conta e passa por um "não sou robô" que não existe dentro
do servidor do GitHub. Você roda pelo botão do painel quando quiser.
