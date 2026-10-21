# Checklist de configuração (passo a passo)

Tudo aqui é gratuito e nenhum passo pede cartão de crédito. Tempo total: cerca de 20 minutos.

## 1. Bot do Telegram (5 min)

1. No Telegram, abra uma conversa com **@BotFather** e envie `/newbot`.
2. Escolha um nome e um usuário (precisa terminar em `bot`). O BotFather devolve o **token**
   (parece `123456789:AAE...`). **Trate como senha.**
3. Abra a conversa com o seu bot novo e envie `oi` (o bot só consegue falar com quem falou primeiro).
4. Copie `.env.example` para `.env` e preencha só o token:

   ```powershell
   Copy-Item .env.example .env
   notepad .env        # preencha TELEGRAM_BOT_TOKEN
   ```

5. Descubra o seu `chat_id`:

   ```powershell
   .\.venv\Scripts\python.exe -m radar get-chat-id
   ```

   Cole o número em `TELEGRAM_CHAT_ID` no `.env`.

## 2. Testar na sua máquina (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
.\.venv\Scripts\python.exe -m radar check-config
.\scripts\run_local.ps1 --dry-run     # mostra a prévia do alerta, sem gravar nem enviar
.\scripts\run_local.ps1               # execução completa: grava em .\data_local e manda o Telegram
```

A primeira execução completa leva uns 3 a 6 minutos: o robô espera 4 segundos entre chamadas
porque o PNCP bloqueia (HTTP 429) quem consulta rápido demais.

## 3. GitHub (repositório público)

1. O repositório público é `victor-ozores/Radar-PNCP`.
2. A branch `data` (órfã) guarda os dados; o workflow grava nela. Já vem criada, com a carga da
   primeira execução local (campo `trigger = local` em `pipeline_runs`).
3. Em **Settings > Secrets and variables > Actions > New repository secret**, cadastre:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
4. Em **Actions**, rode manualmente o workflow **Pipeline diário**:
   - 1ª vez: `modo = bootstrap` (carga inicial das propostas abertas, ~20 a 40 min);
   - depois: `modo = daily`. Confira a mensagem no Telegram e o commit novo na branch `data`.
5. Teste o alerta de falha: rode **Pipeline diário** com `simulate_failure = true`.
   A mensagem 🚨 deve chegar no Telegram.

## 4. Painel online (GitHub Pages, grátis)

O Power BI foi descartado: a licença gratuita não atualiza sozinha. O painel é uma página estática
em `site/` que lê `export/painel.json` da branch `data`.

1. No repositório: **Settings > Pages > Build and deployment > Source = GitHub Actions**. Sem esse
   passo o workflow **Painel (GitHub Pages)** falha no último passo (*deploy*).
2. Em **Actions**, rode **Painel (GitHub Pages)** (ou faça um push que mude algo em `site/`).
   Ao terminar, o endereço aparece no passo *deploy*: `https://victor-ozores.github.io/Radar-PNCP/`.
3. A página só mostra editais depois que o `painel.json` existir na branch `data`, o que acontece
   na primeira execução do **Pipeline diário** com o código novo. Antes disso ela avisa que não
   conseguiu carregar (erro 404), o que é esperado.

Fonte dos dados do painel (pública, sem login):
`https://raw.githubusercontent.com/victor-ozores/Radar-PNCP/data/export/painel.json`

Para mexer na página no seu computador, veja *Painel online* no README.

## 5. Vigia externo (Healthchecks.io, grátis)

O heartbeat do GitHub também é agendado: se o agendador do GitHub parar, ele para junto. O vigia
externo cobre isso.

1. Crie uma conta no plano **Hobbyist** (grátis, sem cartão) em healthchecks.io.
2. Crie um check com **Schedule = Cron**, **Cron Expression = `17 10 * * *`**, **Time Zone = UTC**
   (o relógio do GitHub; é 07:17 em Brasília) e **Grace Time = 7 hours**, e ligue a integração de
   e-mail (ou outra) no check. Prefira Cron a *Simple*: no Simple o prazo conta a partir do último
   ping, e uma execução manual no meio do dia adiaria o alerta.
   **Por que 7 h:** na primeira medição (20/10/2026) as execuções agendadas do GitHub chegaram de
   3 h 09 a 5 h 25 atrasadas. Com 3 h de folga o check ficou DOWN sem falha real. Reveja esse
   valor depois de algumas semanas, com mais dados.
3. Copie o **ping URL** (`https://hc-ping.com/...`) e cadastre como secret `HEALTHCHECK_URL` em
   *Settings > Secrets and variables > Actions*. **Trate como segredo**: quem tem o endereço pode
   mandar um aviso falso. Nunca coloque no código, no README ou em commit.
4. Rode **Pipeline diário** (`modo = daily`). O passo *Avisar o vigia externo* deve terminar com
   "Vigia externo avisado (HTTP 200)" e o check no site deve ficar verde (*up*).

O aviso só é enviado quando a execução diária termina bem. Sem o secret, o passo é ignorado.
