# Código de Streaming para Telegram

Bot do Telegram que entrega, sob demanda, o **código contido no email mais
recente** de serviços de streaming (Netflix, Disney+, etc.) enviados para sua
caixa de entrada do Gmail.

## Como funciona

1. Você (ou quem estiver autorizado) envia ao bot o **nome de um serviço**
   configurado, ex.: `netflix`.
2. O bot busca na sua caixa do Gmail o **email mais recente** daquele remetente.
3. O email é formatado (remetente, assunto, data e corpo) e respondido no chat
   de quem pediu, quebrado em mensagens de até 4096 caracteres se necessário.

Mensagens padrão:
- `/start` ou `/help`: lista os serviços disponíveis.
- Nome do serviço (ex.: `netflix`): responde com o último email dele.
- Serviço inexistente: responde com a lista de serviços configurados.

## Estrutura

```
src/email_telegram_bot/
├── main.py                       # ponto de entrada: wiring + loop do bot
├── config.py                     # leitura/validação de variáveis de ambiente
├── gmail/client.py               # OAuth 2.0 + busca do email mais recente
├── gmail/parser.py               # payload da API do Gmail -> EmailMessage
├── telegram/client.py            # Bot API: sendMessage/getUpdates, split
├── telegram/bot.py               # despacho de comandos e respostas
└── services/code_requests.py     # apelido -> remetente -> último email
```

## Pré-requisitos

- Python 3.12+
- Conta Gmail (a sua, onde chegam os códigos)
- Conta Telegram

## 1. Configurar o Google Cloud e habilitar a Gmail API

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/) e crie um
   projeto (ex.: `email-telegram-bot`).
2. Em **APIs & Services > Library**, busque por **Gmail API** e clique em
   **Enable**.
3. Em **APIs & Services > OAuth consent screen**:
   - Escolha o tipo **External** e preencha as informações mínimas.
   - Adicione seu próprio email em **Test users** (modo *Testing* é suficiente).
4. Em **APIs & Services > Credentials**, clique em **Create credentials >
   OAuth client ID**:
   - Application type: **Desktop app**.
   - Faça **Download JSON** do client criado.
5. Salve o arquivo como `credentials.json` na raiz do projeto (ou aponte
   `GOOGLE_CREDENTIALS_PATH` para ele).

O escopo solicitado é o mínimo possível:
`https://www.googleapis.com/auth/gmail.readonly` (somente leitura).

## 2. Criar o bot no Telegram (BotFather)

1. Conversa com [@BotFather](https://t.me/BotFather) e envie `/newbot`.
2. Escolha um nome e um username (terminando em `bot`).
3. O BotFather retorna o **token** do bot, algo como `123456789:AAAA...`.
   Esse é o `TELEGRAM_BOT_TOKEN`.

## 3. Descobrir o chat ID dos usuários autorizados

Com o bot rodando, qualquer pessoa que mandar mensagem e tiver o chat ID
registrado no log:

1. Deixe `ALLOWED_CHAT_IDS` vazio no `.env` e inicie o bot.
2. Envie uma mensagem ao bot; ele responde "não autorizado" e o terminal
   registra `Rejected request from unauthorized chat <ID>`.
3. Copie o `<ID>` para `ALLOWED_CHAT_IDS` no `.env` e reinicie o bot.

Isso é importante porque o bot entrega códigos: sem whitelist, qualquer pessoa
que achar o bot poderia consultá-lo.

## 4. Configurar o `.env`

```bash
cp .env.example .env
```

| Variável | Obrigatória | Descrição |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | sim | Token do BotFather |
| `SERVICE_SENDERS` | sim | Mapeamento `alias=remetente`, separado por vírgula. Ex.: `netflix=info@message.netflix.com,displex=no-reply@myproject.disneyplus.com` |
| `ALLOWED_CHAT_IDS` | não | IDs de chat autorizados, separados por vírgula. Vazio = todos podem usar (não recomendado) |
| `GOOGLE_CREDENTIALS_PATH` | não | Caminho do `credentials.json` (padrão: `credentials.json`) |
| `GOOGLE_TOKEN_PATH` | não | Onde o token OAuth é salvo (padrão: `token.json`) |

O filtro usa a parte do endereço no header `From` do email
(ex.: `montadores@empresa.com` em `"Montadores Ltda <montadores@empresa.com>"`).
O apelido (alias) é o que os usuários digitarão no Telegram; não diferencia
maiúsculas de minúsculas.

## 5. Instalar as dependências

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 6. Executar

```bash
email-telegram-bot
```

ou

```bash
python -m email_telegram_bot.main
```

Na primeira consulta a uma conta ainda autenticada, uma janela do navegador
abrirá para o consentimento OAuth 2.0; o token fica em `token.json` e é
reutilizado/renovado automaticamente depois.

Logs são enviados para stdout, incluindo pedidos autorizados/rejeitados e erros.

## 7. Executar os testes

```bash
pytest
```

Os testes não dependem de rede nem de credenciais: a Gmail API e a Telegram API
são simuladas com `unittest.mock`.
