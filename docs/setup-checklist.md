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

## 4. Power BI (teste cedo)

O Power BI Service pode exigir e-mail corporativo ou escolar, e a publicação na web pode estar
bloqueada pelo administrador do tenant. Antes de montar o painel:

1. Entre em app.powerbi.com com o e-mail da UNICID.
2. Publique um CSV pequeno e veja se aparece **Atualização agendada** e **Publicar na web**.
3. Anote o resultado no README (seção "Painel"). Se não funcionar, o plano B é o `.pbix` no
   repositório mais prints e um GIF.

Fonte dos dados para o painel (pública, sem login):
`https://raw.githubusercontent.com/victor-ozores/Radar-PNCP/data/export/editais.csv`
