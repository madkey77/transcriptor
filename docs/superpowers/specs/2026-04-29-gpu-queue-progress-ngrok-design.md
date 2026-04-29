# Transcriptor — GPU + Fila + Progresso Real + Domínio Fixo ngrok

**Data:** 2026-04-29
**Status:** Aprovado para implementação
**Branch alvo:** continua em `feat/expose-via-ngrok` ou nova feature branch

## 1. Objetivo

Quatro melhorias coordenadas no Transcriptor:

1. Rodar WhisperX e diarization em **GPU NVIDIA** (RTX 4060 Ti 8GB, CUDA disponível na máquina).
2. Permitir upload de **vários arquivos** com fila **estritamente serial** (1 transcrição por vez).
3. Mostrar **progresso real** (% durante a transcrição) + estágios + logs ao vivo.
4. Usar o **domínio estático ngrok** já criado (`egret-awake-vaguely.ngrok-free.app`).

Premissa-chave: aplicação roda numa máquina pessoal, com WSL2, exposta via ngrok pra acesso remoto pessoal. Restart do backend pode ocorrer; perder fila pendente é aceitável.

## 2. Não-objetivos

- Cancelamento de transcrição em andamento.
- Persistência de fila entre restarts.
- Concorrência paralela (>1 GPU job por vez).
- Migrações de schema do DB.
- Refatoração do `TranscriptionView`/`HistoryList`.
- Fallback de CPU automático (usuário escolheu fail-fast em GPU).

## 3. Arquitetura — visão geral

Quatro mudanças, isoladas por arquivo:

| Mudança | Arquivos | Tipo |
|---|---|---|
| GPU + float16 | `backend/src/transcription/whisperx_service.py`, `diarization.py`, `utils/config.py` | Configuração |
| Fila serial | `backend/src/transcription/queue.py` (novo), `api/main.py`, `api/routes/transcribe.py` | Lógica nova |
| Progresso real | `backend/src/transcription/whisperx_service.py`, `progress.py` | Instrumentação |
| Domínio ngrok | `run.sh` | Config script |
| UI multi-fila | `frontend/src/components/upload/*`, `App.tsx`, `hooks/useQueue.ts` | Reorganização UI |

## 4. Fluxo de dados

```
Browser                  FastAPI                    Worker (asyncio task)
   │                        │                              │
   │ POST /api/transcribe   │                              │
   │ (file 1, 2, 3, ...)    │                              │
   ├───────────────────────▶│ cria DB row (status=pending) │
   │                        │ enfileira (queue.put)        │
   │  202 + {id, position}  │                              │
   │◀───────────────────────┤                              │
   │                        │                              │ ◀── queue.get() loop
   │                        │                              │
   │ GET /api/transcribe/   │                              │ inicia job ativo
   │     {id}/progress (SSE)│                              │ → atualiza ProgressManager:
   │◀───── stage events ────┼──────────────────────────────┤   - stage: loading_audio
   │◀── progress events ────┤                              │   - stage: transcribing + pct
   │◀────── log events ─────┤                              │   - stage: diarizing
   │◀──── complete event ───┤                              │   - stage: saving
   │                        │                              │   - complete
   │                        │                              │ ◀── próximo da fila
   │ DELETE /api/transcribe/│                              │
   │   {id}  (só pending)   │                              │
   │ 204                    │ remove da queue + DB         │
   │◀───────────────────────┤                              │
```

## 5. Componentes

### 5.1 Backend

| Arquivo | Responsabilidade | Interface |
|---|---|---|
| `transcription/queue.py` *(novo)* | Fila serial em memória + worker. | `enqueue(id, content) -> int (position)`, `cancel(id) -> bool`, `start_worker()`, `stop_worker()`, `position(id) -> int \| None` |
| `transcription/whisperx_service.py` *(mod)* | Carrega modelo em CUDA + emite progresso por batch. | `transcribe(path, on_progress: Callable[[float], None] \| None) -> dict` |
| `transcription/progress.py` *(mod)* | `EventType.PROGRESS` + `update_progress(id, stage, pct)`. | métodos novos |
| `api/routes/transcribe.py` *(mod)* | Upload chama `queue.enqueue`. Adiciona `DELETE /{id}`. Resposta de POST inclui `position`. | endpoints HTTP |
| `api/main.py` *(mod)* | Lifespan inicia/para o worker e marca jobs órfãos como `failed` no startup. | — |
| `utils/config.py` *(mod)* | Adiciona `device`, `compute_type`, `queue_max_size`. | Settings |

**Fila — comportamento detalhado:**

- `asyncio.Queue(maxsize=settings.queue_max_size)` global.
- Worker é uma `asyncio.Task` iniciada no `lifespan` startup; `await queue.get()` em loop.
- Para cada item, chama `processor.process(content, id)` (já existe — síncrono, rodado via `loop.run_in_executor` para não bloquear o event loop).
- `cancel(id)` percorre uma lista interna de IDs pendentes (mantida em paralelo com a queue) e remove. Se já estiver em execução, retorna `False`.
- Worker tem `try/except` global; em caso de exceção marca o job atual como `failed` e segue. Se a task em si crashar (improvável com try interno), `lifespan` registra e reinicia.

**Progresso por chunk — comportamento detalhado:**

- `WhisperXService.transcribe()` recebe `on_progress: Callable[[float], None] | None`.
- Antes da chamada a `_whisper_model.transcribe(audio, batch_size=8, language=...)`:
  - Monkey-patch local de `whisperx.asr.tqdm` (ou `tqdm.tqdm` no módulo relevante) com uma subclasse que captura `update(n)` e `total`, calculando `pct = current / total` e chamando `on_progress(pct)`.
  - Restaura o original no `finally`.
- Se o monkey-patch falhar (atributo não existe, versão diferente), loga `warn` uma vez e segue sem progresso (fallback indeterminado na UI).
- O `on_progress` é fornecido pelo `processor`, que chama `progress_manager.update_progress(id, "transcribing", pct)`.

### 5.2 Frontend

| Arquivo | Responsabilidade |
|---|---|
| `components/upload/FileDropzone.tsx` *(mod)* | `maxFiles: undefined`, `onFilesSelect(files: File[])`. |
| `components/upload/QueueList.tsx` *(novo)* | Renderiza `QueueItem`s ordenados por `created_at`. Empty state. |
| `components/upload/QueueItem.tsx` *(novo)* | Card de 1 item: status badge, barra de progresso (real ou indeterminada), estágio, botões X / Abrir / Tentar de novo, painel de logs colapsável. |
| `hooks/useQueue.ts` *(novo)* | Lê history filtrando `pending`/`processing` recentes; expõe `items`, `enqueue(file)`, `remove(id)`, `retry(id)`. |
| `hooks/useProgressStream.ts` *(re-habilitar)* | Já existe comentado em `App.tsx:13,33-38`; aceita `id` por item; handler para event `progress`. |
| `services/transcription.ts` *(mod)* | `cancelTranscription(id)`, types do evento `progress`. |
| `App.tsx` *(mod)* | View `upload` passa a renderizar `<FileDropzone>` + `<QueueList>`. `currentTranscriptionId` continua existindo, mas é setado apenas pela ação "Abrir" (em `QueueItem` concluído ou em `HistoryList`). O fluxo "upload → progresso → auto-redireciona" some — o usuário fica na fila e abre quando quiser. |

## 6. Contratos de API

### 6.1 `POST /api/transcribe` *(modificado)*

```jsonc
// Request: multipart/form-data com 1 arquivo (cliente faz POST por arquivo)
// Response 202:
{
  "id": "uuid",
  "status": "pending",
  "filename": "audio.mp3",
  "position": 2          // 0 = ativo, 1+ = aguardando
}
// 429 quando fila cheia: {"detail": "Queue full"}
```

### 6.2 `DELETE /api/transcribe/{id}` *(novo)*

- `204` se item estava `pending` e foi removido.
- `409` se item está `processing` ou já terminou (`completed`/`failed`).
- `404` se não existe.

### 6.3 `GET /api/transcribe/{id}/progress` *(modificado)*

Adiciona evento `progress`:

```python
# src/transcription/progress.py
class EventType(str, Enum):
    STAGE = "stage"
    LOG = "log"
    PROGRESS = "progress"   # novo
    COMPLETE = "complete"
    ERROR = "error"
```

Payload:

```json
{ "event": "progress", "stage": "transcribing", "pct": 0.42, "description": "Transcrevendo… 42%" }
```

Mantidos sem mudança: `GET /{id}/status`, `GET /{id}`, `PATCH /{id}/speakers`, `GET /{id}/download`, rotas de history.

### 6.4 Configuração nova (`backend/src/utils/config.py`)

```python
device: str = "cuda"          # forçado; falha se cuda indisponível
compute_type: str = "float16"
queue_max_size: int = 100
```

### 6.5 `run.sh` *(modificado)*

```bash
NGROK_DOMAIN="${NGROK_DOMAIN:-egret-awake-vaguely.ngrok-free.app}"
ngrok http --domain="$NGROK_DOMAIN" 8000 --log=stdout >"$NGROK_LOG" 2>&1 &
```

## 7. UX / UI da fila

Aplicando regras do `ui-ux-pro-max` Quick Reference:

- `multi-step-progress` + `progressive-loading` → barra de progresso real + label do estágio em cada item.
- `empty-states` → "Nenhuma transcrição na fila — solte arquivos acima para começar".
- `inline-validation` → erros por arquivo, exibidos no card.
- `destructive-emphasis` → botão X (remover) com cor de perigo, separado dos demais.
- `aria-live` polite + `error-clarity` → leitor de tela anuncia mudanças de estado.
- `stagger-sequence` (30–50ms) → entrada animada da lista; respeita `prefers-reduced-motion`.
- `touch-target-size` ≥44px nos botões X/Abrir/Tentar.
- `state-clarity` → badges com contraste ≥4.5:1 (slate-50 sobre cores semânticas).

**Estados visuais por item:**

| Estado | Badge | Barra | Botões |
|---|---|---|---|
| `pending`, position > 0 | "Aguardando (N à frente)" | — | X |
| `pending`, position = 0 | "Iniciando…" | indeterminada | X |
| `processing` (loading_audio/diarizing/saving) | "Processando" + nome do estágio | indeterminada | — |
| `processing` (transcribing com pct) | "Processando" + "Transcrevendo… 42%" | barra real | — |
| `completed` | "Concluído" | 100% | Abrir |
| `failed` | "Falhou" + mensagem | — | Tentar de novo, X (limpa do local) |

**Painel de logs colapsável** abaixo do item ativo: mostra os últimos N eventos `log` do SSE.

## 8. Tratamento de erros

### 8.1 Backend

| Cenário | Comportamento |
|---|---|
| `torch.cuda.is_available() == False` no startup | `WhisperXService.load_model()` levanta `RuntimeError`; app não sobe; log: "CUDA não disponível — instale driver/torch CUDA". |
| GPU OOM em runtime | Job atual `failed` com `"GPU out of memory"`; próximo da fila começa; worker não cai. |
| Worker task crasha | `lifespan` registra error e reinicia o worker (loop em `start_worker`). |
| `POST` com fila cheia | `429 Too Many Requests` + `{"detail": "Queue full"}`. |
| `DELETE` em job ativo ou terminado | `409 Conflict`. |
| Restart com pendentes/processando no DB | Startup marca todos como `failed` com `"Interrupted by restart"`. Não recoloca na fila. |
| Patch do tqdm falhar | Loga `warn` 1x; transcrição segue; UI mostra barra indeterminada. |
| Diarization falha | Comportamento atual: cai para single speaker (`processor.py:84-87`). |

### 8.2 Frontend

| Cenário | Comportamento |
|---|---|
| SSE desconecta | `EventSource` reconecta sozinho. Se o item já terminou, a próxima resposta é o evento final. |
| Aba fechada durante fila | Backend continua. Ao voltar, `useQueue` re-renderiza a partir do `/api/history`. |
| `prefers-reduced-motion` | Stagger e barras animadas viram mudanças discretas. |
| Erro 429 ao enfileirar | Toast `"Fila cheia, aguarde"`; demais arquivos do mesmo drop continuam. |
| Arquivo inválido (formato/tamanho) | Erro inline no card; outros arquivos válidos seguem. |
| 2 abas abertas | Ambas refletem o mesmo estado via SSE + history; sem conflito. |

## 9. Testes

### 9.1 Backend (novos testes pytest)

- `tests/test_queue.py` — enfileira 3, verifica ordem de processamento; `cancel(pending)` → True, item some; `cancel(processing)` → False; fila cheia → exceção; worker reinicia após exceção.
- `tests/test_progress_callback.py` — monkey-patch do tqdm captura `n/total` e dispara `update_progress`; usa mock de `_whisper_model.transcribe`.
- `tests/test_routes_transcribe.py` — `DELETE` retorna 204/409/404 nos casos certos; `POST` retorna `position`; `POST` com fila cheia retorna 429.

### 9.2 Não cobertos por teste automatizado

- GPU real (depende de hardware).
- Mudança de `run.sh` (1 linha de config).
- Componentes React novos (não há suíte de frontend hoje).

### 9.3 Validação manual de aceite

1. `./run.sh` deve imprimir banner com `https://egret-awake-vaguely.ngrok-free.app`.
2. Drop de 3 arquivos: card 1 entra em `processing` com barra avançando 0→100%; cards 2 e 3 ficam "Aguardando (1 à frente)" e "Aguardando (2 à frente)".
3. Botão X no card 3 → some da lista; card 2 segue em `pending`.
4. `nvidia-smi` durante transcribe mostra processo Python usando VRAM.
5. Reload da aba durante card 1 ativo → estado retomado, barra continua avançando.
6. Backend reiniciado durante fila → ao voltar, itens que estavam `pending`/`processing` aparecem como `failed` com mensagem "Interrupted by restart".

## 10. Plano de rollout

Implementação numa única branch (`feat/queue-gpu-progress`), commits separados por área:

1. Config (GPU + ngrok domain).
2. ProgressManager + EventType.PROGRESS + monkey-patch tqdm.
3. TranscriptionQueue + worker no lifespan + endpoint DELETE + ajuste do POST.
4. Cleanup de jobs órfãos no startup.
5. Frontend: FileDropzone multi + QueueList/QueueItem + useQueue + re-habilitar useProgressStream + ajustes em App.tsx.
6. Build do frontend (`npm run build`) e validação manual.

Sem feature flags — uso pessoal, mudança total no fluxo.
