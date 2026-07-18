# Consulta Base

Aplicacao local para consulta direta por CNPJ usando os CSVs salvos no projeto.

## Dados esperados

Os arquivos devem existir com estes nomes:

- `data/MAPA PARQUE.csv`
- `data/PARQUE MOVEL.csv`
- `data/PARQUE FIXA.csv`
- `data/RECOMENDAÇÃO FIXA.csv` (opcional, habilita ofertas no detalhamento de BL)
- `data/RECOMENDAÇÃO MÓVEL.csv` (opcional, habilita ofertas por linha no detalhamento móvel)

Ao iniciar, a aplicacao verifica esses caminhos e mostra qual arquivo esta ausente quando algum deles nao existe.

## Executar

```powershell
python app.py
```

Depois acesse:

```text
http://127.0.0.1:8000
```

A primeira inicializacao pode demorar um pouco porque a aplicacao cria um cache SQLite local em `.cache/consulta_base.sqlite3`.

## Publicar em VPS

Requisitos:

- Python 3.10 ou superior.
- Permissao de escrita em `data/` e `.cache/`. A aplicacao inicia sem CSV e o administrador envia as bases pelo painel.

Variaveis recomendadas em producao:

```bash
HOST=127.0.0.1
PORT=8000
PUBLIC_BASE_URL=https://seu-dominio.com.br
SESSION_COOKIE_SECURE=auto
MAX_UPLOAD_BYTES=314572800
APP_TIMEZONE=America/Sao_Paulo
ADMIN_EMAIL=admin@seu-dominio.com.br
ADMIN_NAME='Nome do Administrador'
ADMIN_PASSWORD='troque-esta-senha'
SMTP_HOST=smtp.seu-provedor.com
SMTP_PORT=587
SMTP_USER=usuario-smtp
SMTP_PASSWORD='senha-smtp'
SMTP_FROM=no-reply@seu-dominio.com.br
SMTP_TLS=1
```

Observacoes importantes:

- Se usar Nginx como proxy reverso, mantenha `HOST=127.0.0.1` e exponha somente o Nginx para a internet.
- Se for expor a aplicacao diretamente sem Nginx, use `HOST=0.0.0.0`, mas o recomendado e usar Nginx com HTTPS.
- Configure `PUBLIC_BASE_URL` para que os links de confirmacao de e-mail e redefinicao de senha saiam com o dominio correto.
- Use `SESSION_COOKIE_SECURE=auto` para que o cookie de sessao use `Secure` somente quando a requisicao chegar como HTTPS via `X-Forwarded-Proto`.
- Use `SESSION_COOKIE_SECURE=1` apenas quando todo acesso estiver em HTTPS. Em teste por HTTP direto, use `auto` ou `0`.
- A sessão de login dura no máximo 2 horas. Um novo login da mesma conta invalida automaticamente a sessão anterior, inclusive em outro dispositivo.
- O painel administrativo envia os CSVs por `POST /api/admin/data/upload`; o envio exige usuario `ADMIN` e pode ser feito em etapas.
- Os CSVs de `data/` são ignorados pelo Git e pelo contexto de build do Docker. A imagem não contém bases operacionais.
- No Docker Compose, o volume nomeado `app-data` preserva os arquivos enviados pelo painel fora do repositório, inclusive após reconstruir o contêiner.
- Não use `docker compose down -v` em produção: a opção `-v` remove os volumes `app-data` e `app-cache`.
- MAPA PARQUE, PARQUE MOVEL e PARQUE FIXA são obrigatórias para liberar consultas. As duas bases de recomendação são opcionais e podem ser enviadas depois.
- `MAX_UPLOAD_BYTES` define o limite do endpoint de upload. O padrao e 300 MB.
- `APP_TIMEZONE` define o fuso usado nos relatorios diarios e mensais. O padrao e `America/Sao_Paulo`.
- A pagina `/admin/relatorios` aceita os perfis `ADMIN`, `GESTOR` e `SUPERVISOR`: o administrador ve todas as equipes, o gestor ve os supervisores vinculados a ele e as respectivas equipes, enquanto o supervisor ve somente a propria equipe.
- Novos cadastros precisam confirmar o e-mail por um link valido por 24 horas antes de poderem ser aprovados pelo administrador. Sem SMTP configurado, as mensagens locais ficam em `.cache/email_verification_outbox/`.
- Defina `ADMIN_EMAIL`, `ADMIN_NAME` e `ADMIN_PASSWORD` antes da primeira inicializacao. Se `.cache/auth.sqlite3` ja existir, essas variaveis nao recriam o administrador.
- Sem `ADMIN_PASSWORD`, a primeira inicializacao gera uma senha aleatoria em `.cache/admin_credentials.txt`. No Docker, consulte com `docker compose exec app cat /app/.cache/admin_credentials.txt`.
- Nao suba a pasta `.cache/` de ambiente local para a VPS se quiser criar credenciais limpas em producao.

Exemplo de systemd:

```ini
[Unit]
Description=Consulta Base A7 Connect
After=network.target

[Service]
WorkingDirectory=/opt/consulta-base
Environment=HOST=127.0.0.1
Environment=PORT=8000
Environment=PUBLIC_BASE_URL=https://seu-dominio.com.br
Environment=SESSION_COOKIE_SECURE=auto
Environment=MAX_UPLOAD_BYTES=314572800
Environment=APP_TIMEZONE=America/Sao_Paulo
Environment=ADMIN_EMAIL=admin@seu-dominio.com.br
Environment=ADMIN_NAME=Nome do Administrador
Environment=ADMIN_PASSWORD=troque-esta-senha
ExecStart=/usr/bin/python3 /opt/consulta-base/app.py
Restart=always
RestartSec=5
User=www-data
Group=www-data

[Install]
WantedBy=multi-user.target
```

Exemplo de Nginx:

```nginx
server {
    listen 80;
    server_name seu-dominio.com.br;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name seu-dominio.com.br;

    ssl_certificate /etc/letsencrypt/live/seu-dominio.com.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/seu-dominio.com.br/privkey.pem;

    client_max_body_size 350m;
    proxy_read_timeout 1800s;
    proxy_send_timeout 1800s;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
    }
}
```

Checklist antes de ligar em producao:

```bash
python -m py_compile app.py
python -m unittest discover -s tests
python app.py
```

Depois acesse `/login`, entre como administrador, envie as bases em `/admin/usuarios` e confira `/api/status` autenticado.
