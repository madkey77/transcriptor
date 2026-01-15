# Planejamento: Expor Transcriptor API para Internet

## Visão Geral

Este documento descreve as alterações necessárias no código e os passos para expor a API de transcrição para acesso via internet, de forma segura e para uso pessoal.

**Método escolhido**: Cloudflare Tunnel (gratuito, seguro, sem abrir portas)

---

## Parte 1: Alterações no Código (Para IA implementar)

### 1.1 Adicionar Autenticação por API Key

**Arquivo**: `backend/src/api/middleware.py`

Criar um middleware de autenticação que:
- Verifica header `X-API-Key` em todas as requisições para `/api/*`
- Permite acesso sem autenticação para `/` e `/static/*` (frontend)
- A API key é definida via variável de ambiente `TRANSCRIPTOR_API_KEY`
- Se a variável não estiver definida, autenticação é desabilitada (modo desenvolvimento)

```python
# Pseudocódigo
API_KEY = os.environ.get("TRANSCRIPTOR_API_KEY")

@app.middleware("http")
async def auth_middleware(request, call_next):
    if API_KEY and request.url.path.startswith("/api/"):
        provided_key = request.headers.get("X-API-Key")
        if provided_key != API_KEY:
            return JSONResponse(status_code=401, content={"error": "Invalid API key"})
    return await call_next(request)
```

### 1.2 Atualizar Frontend para Enviar API Key

**Arquivo**: `backend/static/app.js`

- Adicionar campo de API key no localStorage
- Incluir header `X-API-Key` em todas as requisições fetch
- Criar tela de login simples se API key não estiver configurada
- Permitir usuário salvar/alterar API key nas configurações

```javascript
// Pseudocódigo
const apiKey = localStorage.getItem('transcriptor_api_key');

async function fetchWithAuth(url, options = {}) {
    if (apiKey) {
        options.headers = { ...options.headers, 'X-API-Key': apiKey };
    }
    return fetch(url, options);
}
```

### 1.3 Adicionar Tela de Configuração de API Key

**Arquivo**: `backend/static/index.html`

Adicionar:
- Modal/tela para inserir API key na primeira vez
- Botão de configurações no header para alterar API key
- Mensagem de erro amigável quando API key é inválida

### 1.4 Atualizar Upload de Arquivo para Incluir API Key

**Arquivo**: `backend/static/app.js`

O upload usa XMLHttpRequest, precisa adicionar o header:
```javascript
xhr.setRequestHeader('X-API-Key', apiKey);
```

### 1.5 Atualizar EventSource (SSE) para Autenticação

**Problema**: EventSource nativo não suporta headers customizados.

**Solução**: Passar API key como query parameter para o endpoint de progress:
- Backend aceita `?api_key=XXX` como alternativa ao header para o endpoint `/api/transcribe/{id}/progress`
- Frontend envia: `new EventSource(/api/transcribe/${id}/progress?api_key=${apiKey})`

**Arquivo backend**: `backend/src/api/routes/transcribe.py`
```python
@router.get("/{transcription_id}/progress")
async def stream_progress(
    transcription_id: str,
    api_key: Optional[str] = None,  # Query param alternativo
    db: Session = Depends(get_db)
):
    # Validar api_key se AUTH estiver habilitado
```

### 1.6 Configuração de Host

**Arquivo**: Instruções de execução

Mudar comando de execução para:
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

### 1.7 Criar Script de Inicialização

**Arquivo**: `backend/start.sh`

```bash
#!/bin/bash
export TRANSCRIPTOR_API_KEY="${TRANSCRIPTOR_API_KEY:-}"
cd /caminho/para/backend
source venv/bin/activate
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

---

## Parte 2: Configuração do Servidor (Passos do Usuário)

### 2.1 Requisitos do Servidor

- **Sistema**: Linux (Ubuntu 22.04 recomendado)
- **RAM**: Mínimo 8GB (16GB recomendado)
- **GPU**: NVIDIA com CUDA (opcional, mas muito mais rápido)
- **Armazenamento**: 20GB+ livres
- **Software**: Python 3.11+, ffmpeg, CUDA toolkit (se usar GPU)

### 2.2 Instalação do Projeto

```bash
# 1. Clonar/copiar o projeto para o servidor
cd /opt
git clone <repo> transcriptor
# ou copiar via scp/rsync

# 2. Criar ambiente virtual
cd /opt/transcriptor/backend
python3 -m venv venv
source venv/bin/activate

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Instalar ffmpeg
sudo apt update && sudo apt install ffmpeg -y

# 5. Configurar API key (gerar uma senha forte)
export TRANSCRIPTOR_API_KEY="sua-chave-secreta-aqui-use-senha-forte"

# 6. Testar execução
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

### 2.3 Criar Serviço Systemd (Execução Automática)

```bash
sudo nano /etc/systemd/system/transcriptor.service
```

Conteúdo:
```ini
[Unit]
Description=Transcriptor API
After=network.target

[Service]
Type=simple
User=seu_usuario
WorkingDirectory=/opt/transcriptor/backend
Environment="TRANSCRIPTOR_API_KEY=sua-chave-secreta-aqui"
ExecStart=/opt/transcriptor/backend/venv/bin/uvicorn src.api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Ativar e iniciar serviço
sudo systemctl daemon-reload
sudo systemctl enable transcriptor
sudo systemctl start transcriptor

# Verificar status
sudo systemctl status transcriptor

# Ver logs
sudo journalctl -u transcriptor -f
```

---

## Parte 3: Configuração do Cloudflare Tunnel

### 3.1 Criar Conta e Configurar Domínio

1. Criar conta gratuita em [cloudflare.com](https://cloudflare.com)
2. Adicionar um domínio (pode ser subdomínio gratuito via [freenom](https://freenom.com) ou comprar um barato)
3. Apontar nameservers do domínio para Cloudflare

### 3.2 Instalar Cloudflared no Servidor

```bash
# Baixar e instalar cloudflared
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# Autenticar (abre link no navegador)
cloudflared tunnel login
```

### 3.3 Criar Tunnel

```bash
# Criar tunnel
cloudflared tunnel create transcriptor

# Isso gera um arquivo de credenciais em ~/.cloudflared/

# Criar arquivo de configuração
nano ~/.cloudflared/config.yml
```

Conteúdo do `config.yml`:
```yaml
tunnel: transcriptor
credentials-file: /home/seu_usuario/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: transcriptor.seudominio.com
    service: http://localhost:8000
  - service: http_status:404
```

### 3.4 Configurar DNS

```bash
# Criar registro DNS automaticamente
cloudflared tunnel route dns transcriptor transcriptor.seudominio.com
```

### 3.5 Executar Tunnel como Serviço

```bash
# Instalar como serviço
sudo cloudflared service install

# Iniciar
sudo systemctl start cloudflared
sudo systemctl enable cloudflared
```

### 3.6 Testar Acesso

Acessar `https://transcriptor.seudominio.com` no navegador.

---

## Parte 4: Segurança Adicional (Opcional)

### 4.1 Limitar Taxa de Requisições (Rate Limiting)

Adicionar no middleware para evitar abuso:
- Máximo 10 uploads por hora por IP
- Máximo 100 requisições por minuto por IP

### 4.2 Cloudflare Access (Camada Extra)

No painel Cloudflare:
1. Ir em Zero Trust > Access > Applications
2. Criar aplicação para o domínio
3. Configurar política de acesso (email, one-time PIN, etc.)

Isso adiciona uma tela de login antes mesmo de chegar na API.

### 4.3 Backup do Banco de Dados

Criar cron job para backup diário:
```bash
0 3 * * * cp /opt/transcriptor/backend/data/transcriptor.db /opt/transcriptor/backups/transcriptor_$(date +\%Y\%m\%d).db
```

---

## Resumo de Arquivos a Modificar

| Arquivo | Alteração |
|---------|-----------|
| `backend/src/api/middleware.py` | Adicionar middleware de autenticação |
| `backend/src/api/routes/transcribe.py` | Aceitar api_key como query param no SSE |
| `backend/static/index.html` | Adicionar modal de API key e botão config |
| `backend/static/app.js` | Enviar API key em todas requisições |
| `backend/static/styles.css` | Estilos para modal de API key |
| `backend/start.sh` (novo) | Script de inicialização |

---

## Checklist Final

- [ ] Implementar autenticação por API key no backend
- [ ] Atualizar frontend para enviar API key
- [ ] Adicionar tela de configuração de API key
- [ ] Testar localmente com API key
- [ ] Configurar servidor (instalar dependências)
- [ ] Criar serviço systemd
- [ ] Instalar e configurar Cloudflare Tunnel
- [ ] Testar acesso externo
- [ ] Configurar backups
