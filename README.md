# QR Atlas

Aplicação web para criar QR Codes dinâmicos no seu domínio, mudar o destino sem reimprimir e acompanhar acessos. O código contém apenas `BASE_URL/q/slug`; nunca contém a URL final. Enquanto o domínio, a rota e o registro no banco estiverem ativos, o QR Code continua válido.

## Stack

Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL (produção), SQLite (desenvolvimento), Jinja2, Bootstrap 5, Chart.js, qrcode, Pillow e Uvicorn. O app gera PNG, SVG e PDF localmente. Bootstrap e Chart.js são carregados por CDN no navegador; o redirecionamento e os QR Codes não dependem deles.

## Início rápido com Docker Compose

1. Copie `.env.example` para `.env`.
2. Edite `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `POSTGRES_PASSWORD` e `SECRET_KEY`. Use segredos longos e aleatórios. Para Docker local, mantenha `BASE_URL=http://localhost:8000` e `ENVIRONMENT=development`.
3. Execute:

   ```bash
   docker compose up -d --build
   docker compose logs -f app
   ```

O Compose inicia PostgreSQL, aplica `alembic upgrade head`, cria o administrador inicial se ele ainda não existe e inicia o servidor. Acesse `http://localhost:8000`, `/login`, `/dashboard`, `/qrcodes/create` e `/docs`. O login usa `ADMIN_EMAIL` e `ADMIN_PASSWORD`. A senha não é atualizada automaticamente após a criação da conta. Para trocar a senha, faça isso por um procedimento administrativo seguro no banco ou adicione um fluxo de troca de senha antes de expor o app a usuários adicionais.

**Atenção:** não mude `BASE_URL` após imprimir códigos, a menos que mantenha o endereço antigo acessível. O slug também deve permanecer estável. O destino, por outro lado, pode ser alterado a qualquer momento.

## Instalação local sem Docker

Requer Python 3.12+.

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
# .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env  # no Windows PowerShell: Copy-Item .env.example .env
```

Configure `ADMIN_EMAIL`, `ADMIN_PASSWORD` e `SECRET_KEY` em `.env`. O valor padrão de `DATABASE_URL=sqlite:///./qrtracker.db` usa SQLite. Para PostgreSQL, crie um banco e informe, por exemplo, `DATABASE_URL=postgresql+psycopg://usuario:senha@localhost:5432/qrtracker`. O usuário do banco deve ter permissão para criar tabelas e índices.

```bash
alembic upgrade head
python -m app.cli seed-admin
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

O comando `seed-admin` é idempotente: cria o usuário somente na primeira execução. Novas migrations podem ser criadas com `alembic revision --autogenerate -m "descrição"`, revisadas e aplicadas com `alembic upgrade head`. Não use `Base.metadata.create_all()` em produção.

Para trocar a senha administrativa existente, atualize `ADMIN_PASSWORD` no ambiente do serviço, reinicie ou recrie o contêiner para carregar o novo valor e execute `python -m app.cli reset-admin-password` dentro dele. Alterar apenas a variável não muda o hash já salvo no banco. Trocar `SECRET_KEY` invalida as sessões atuais.

### Escanear com o celular na rede local

`localhost` só funciona no próprio dispositivo. Para escanear com um celular, use o IP do computador na rede Wi-Fi em `BASE_URL` (por exemplo, `http://192.168.1.10:8000`) e inicie o servidor com `--host 0.0.0.0`. O computador e o celular devem estar na mesma rede. Recarregue a página do QR Code e baixe a imagem novamente após alterar `BASE_URL`: imagens antigas continuam contendo o endereço anterior. Um IP local pode mudar e não funciona fora da rede; para QR Codes permanentes e públicos, use um domínio estável com HTTPS.

## Uso

- `/qrcodes/create`: nome, URL final, campanha, origem, descrição, status, slug e UTMs.
- `/qrcodes`: busca por nome, slug, campanha ou URL; filtros por status, campanha e criação; paginação e ações de duplicar, ativar, desativar e excluir.
- `/qrcodes/{id}`: QR Code, URL permanente, download em 500, 1000 ou 2000 pixels, estatísticas e acessos recentes.
- `/reports`: filtros por QR Code, campanha e datas, exportações CSV e XLSX.
- `/docs`: API REST com autenticação HTTP Basic. No Swagger, clique em **Authorize** e use o e-mail e a senha do administrador. A API e o painel devem ser usados por HTTPS em produção.

Os endpoints administrativos da API são `GET/POST /api/qrcodes`, `GET/PUT/DELETE /api/qrcodes/{id}`, `GET /api/qrcodes/{id}/stats`, `GET /api/dashboard/stats` e `GET /api/scans`. Um exemplo:

```bash
curl -u 'admin@example.com:SUA_SENHA' -H 'Content-Type: application/json' \
  -d '{"name":"Recepção","destination_url":"https://example.com/","campaign":"Loja"}' \
  http://localhost:8000/api/qrcodes
```

O painel usa sessão assinada com cookie HttpOnly e SameSite=Lax. Formulários que alteram dados têm token CSRF. A API usa HTTP Basic, sem autenticação por cookie. O endpoint público `GET /q/{slug}` retorna 302 sem página intermediária. Cada acesso admitido pelo limite de taxa gera um registro; acessos do mesmo QR, IP e navegador em até 30 segundos são marcados com `is_unique_scan=false`. Os gráficos de scans totais incluem essas repetições; os cards de scans únicos as excluem. QR Codes inativos respondem com 410 e não registram scan. A exclusão é lógica (`deleted_at`) e preserva o histórico.

## Privacidade e localização

`ANONYMIZE_IP=true` armazena o IP IPv4 sem o último octeto e IPv6 com prefixo /48. O app mantém um HMAC do IP para reduzir duplicatas. Não pede GPS e não faz consulta de geolocalização por rede a cada scan. Para estimar país, estado e cidade, instale um banco GeoLite2 City local e configure `GEOIP_DB_PATH` com o caminho do arquivo `.mmdb` acessível ao app. Sem esse arquivo, esses campos ficam vazios. Para cumprir sua política de privacidade e LGPD, defina prazo de retenção, aviso de privacidade e base legal apropriados à sua operação. Os dados de acesso e exports são visíveis apenas a administradores.

## Produção

Defina `ENVIRONMENT=production`, um `SECRET_KEY` aleatório de pelo menos 32 caracteres, `BASE_URL=https://qr.seudominio.com` e `DATABASE_URL` PostgreSQL. O app rejeita produção sem HTTPS em `BASE_URL`, segredo forte ou PostgreSQL. Configure DNS `A/AAAA` para o servidor e um proxy reverso com certificado TLS. Exponha publicamente apenas 443/80 no proxy; mantenha PostgreSQL privado. O cookie de sessão é `Secure` quando `ENVIRONMENT=production`.

### VPS Ubuntu

Instale Docker Engine e o plugin Compose, copie o projeto, configure `.env` e execute `docker compose up -d --build`. Coloque Nginx ou Caddy na frente da porta 8000 e emita um certificado TLS. Um bloco Nginx básico para o subdomínio:

```nginx
server {
    listen 80;
    server_name qr.seudominio.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Depois configure HTTPS com Certbot e redirecione HTTP para HTTPS. Em uma VPS, altere o mapeamento de portas do Compose para `127.0.0.1:8000:8000`, evitando acesso direto ao Uvicorn. Ative `TRUST_PROXY_HEADERS=true` somente nessa configuração, com o proxy como único caminho até o app. Faça backups regulares do volume PostgreSQL e teste a restauração. Nunca remova o domínio ou a rota `/q/{slug}` de códigos já distribuídos.

### Railway

Crie um serviço PostgreSQL e um serviço da aplicação a partir do `Dockerfile`. Configure `DATABASE_URL` com a URL interna do PostgreSQL, `SECRET_KEY`, `BASE_URL` (domínio público HTTPS), `ENVIRONMENT=production`, `ADMIN_EMAIL` e `ADMIN_PASSWORD`. O comando do Dockerfile aplica migrations e cria o primeiro administrador. Mapeie o domínio no serviço web e confirme que ele responde em HTTPS. Ajuste a porta do serviço para 8000, conforme a configuração da plataforma.

### Render

Crie um PostgreSQL e um Web Service usando o `Dockerfile`. Configure as mesmas variáveis acima e defina `BASE_URL` para o domínio HTTPS da aplicação. Aponte o domínio personalizado e confirme que a plataforma entrega HTTPS ao navegador. O banco deve ser persistente; a aplicação não guarda arquivos de QR no disco.

O `Dockerfile` usa `PORT` quando a plataforma o define; caso contrário, usa 8000.

## Testes

```bash
pytest -q
```

Os testes usam SQLite em memória e cobrem autenticação, CSRF, criação, downloads, redirecionamento, deduplicação, mudança de destino, UTMs, estados 404/410, exclusão lógica, validação de URL, dashboard e relatórios. Para verificar migrations localmente, execute `alembic upgrade head` com um banco de teste vazio e `alembic check`.

## Estrutura

```text
app/
  main.py, config.py, database.py, cli.py
  models/, schemas/, routes/, services/, templates/, static/, utils/
migrations/versions/
tests/
Dockerfile, docker-compose.yml, alembic.ini, requirements.txt, .env.example
```
