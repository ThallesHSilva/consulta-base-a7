# Consulta Base

Aplicacao local para consulta direta por CNPJ usando os CSVs salvos no projeto.

## Dados esperados

Os arquivos devem existir com estes nomes:

- `data/MAPA PARQUE.csv`
- `data/PARQUE MOVEL.csv`
- `data/PARQUE FIXA.csv`

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
- Os 3 arquivos CSV dentro de `data/`, com os nomes exatos listados acima.
- Permissao de escrita na pasta do projeto, pois a aplicacao cria `.cache/consulta_base.sqlite3` e `.cache/auth.sqlite3`.

Variaveis recomendadas em producao:

```bash
HOST=127.0.0.1
PORT=8000
PUBLIC_BASE_URL=https://seu-dominio.com.br
SESSION_COOKIE_SECURE=1
ADMIN_EMAIL=admin@seu-dominio.com.br
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
- Configure `PUBLIC_BASE_URL` para que os links de redefinicao de senha saiam com o dominio correto.
- Use `SESSION_COOKIE_SECURE=1` somente quando o acesso externo estiver em HTTPS.
- Defina `ADMIN_EMAIL` e `ADMIN_PASSWORD` antes da primeira inicializacao. Se `.cache/auth.sqlite3` ja existir, essas variaveis nao recriam o administrador.
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
Environment=SESSION_COOKIE_SECURE=1
Environment=ADMIN_EMAIL=admin@seu-dominio.com.br
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

    client_max_body_size 20m;

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

Depois acesse `/login`, crie/aprove usuarios e confira `/api/status` autenticado.
