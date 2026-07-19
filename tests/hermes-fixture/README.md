# Hermes Runtime Fixture（TEST ONLY）

這是一個供 Controller 黑箱 E2E 使用的合成服務。它不是 Hermes、不是正式 LLM，
也不得連接 Production。所有回應與結構化事件都帶有
`classification: SYNTHETIC_TEST_ONLY`、`fixture_type: SYNTHETIC` 與
`test_only: true`。

服務使用 Python 3.13、FastAPI 與 Uvicorn，具有獨立 Dockerfile、精確鎖版的
runtime/test dependencies，Container 內以 UID/GID `10001:10001` 執行。

## Modes

以 `FIXTURE_MODE` 選擇固定行為：

| Mode | Process | `/health` | LLM probe | 用途 |
|---|---|---|---|---|
| `HEALTHY` | 持續執行 | 200 / AVAILABLE | AVAILABLE | 正常 Start、Status、冪等測試 |
| `SLOW_START` | 持續執行 | 延遲前 503，達到精確延遲後 200 | 延遲前 unavailable | Lock 與 Start Timeout |
| `UNHEALTHY` | 持續執行 | 503 / Hermes unavailable | AVAILABLE | 證明 Running 不等於 Healthy |
| `CRASH` | 結構化記錄後以指定 non-zero code 結束 | 無 | 無 | Crash/失敗流程 |
| `SECRET_LOG` | 持續執行並在 startup log 一次合成 Secret | 200 | AVAILABLE | Log redaction |
| `PERSISTENT` | 持續執行 | marker 完整時 200，缺少或損毀時 503 | AVAILABLE | Restart Volume persistence |

`SLOW_START` 不使用 sleep 阻塞 HTTP server；其 readiness 由 monotonic clock 與
`FIXTURE_START_DELAY_SECONDS` 決定，因此 Controller 可做有上限的 polling。
`CRASH` 是唯一會在啟動路徑 sleep 的模式，預設 delay 為 0。

## Endpoints

- `GET /metadata`：TEST ONLY metadata、支援 modes 與 probe paths。
- `GET /health`：Hermes health gate；200 只表示該 mode 的 Hermes 條件成立。
- `GET /llm/health`：固定 LLM probe。
- `GET /v1/models`：OpenAI-compatible deterministic model listing。
- `POST /v1/chat/completions`：OpenAI-compatible non-streaming deterministic response。
- `PUT /test-only/persistent-marker`：只在 `PERSISTENT` mode 寫入固定 marker；
  caller 無法指定 path 或內容。
- `GET /test-only/persistent-marker`：回 marker present/valid/SHA-256，不回內容或路徑。

Streaming 與未知 model 會回固定的 OpenAI-style error。此服務不呼叫網路、不讀取
Knowledge，也不執行任何任意 command。

## Environment

| Variable | Default | 說明 |
|---|---|---|
| `FIXTURE_MODE` | `HEALTHY` | 上表六種 mode 之一；大小寫不敏感 |
| `FIXTURE_HOST` | `0.0.0.0` | Uvicorn bind host |
| `FIXTURE_PORT` | `8000` | Uvicorn/Container health port |
| `FIXTURE_INSTANCE_ID` | `hermes-fixture-001` | 回應與事件中的 synthetic instance ID |
| `FIXTURE_RUN_ID` | `local` | E2E run namespace；若缺省會讀 `POC_TEST_RUN` |
| `FIXTURE_MODEL_NAME` | `synthetic-test-model` | `/v1` 固定 model ID |
| `SPEC_VERSION` | `0.1.0` | 報告用 frozen spec version |
| `FIXTURE_START_DELAY_SECONDS` | `30` | `SLOW_START` readiness delay；非負有限數字 |
| `FIXTURE_CRASH_DELAY_SECONDS` | `0` | `CRASH` 結束前 delay |
| `FIXTURE_CRASH_EXIT_CODE` | `42` | `CRASH` exit code，1–255 |
| `FIXTURE_TEST_SECRET` | `TEST_SECRET_123456` | `SECRET_LOG` 唯一一次輸出的合成 Secret |
| `FIXTURE_MARKER_PATH` | `/state/runtime-014.marker` | 絕對路徑；應位於 named volume |
| `FIXTURE_MARKER_VALUE` | `RUNTIME-014-PERSISTENT-MARKER` | 固定 marker；不透過 API 回傳 |

無效 mode、port、delay、exit code、相對 marker path 或空白必要字串會在程序啟動時
直接失敗，避免測試悄悄採用錯誤設定。

## RUNTIME-014 without Docker access

`PERSISTENT` mode **不會在 startup 自動重建 marker**，避免 Volume 遺失時產生假陽性：

1. 將 named volume 掛載到 `/state`，啟動 `PERSISTENT` fixture。
2. 測試 setup 經 test-only HTTP endpoint 執行
   `PUT /test-only/persistent-marker`；它只會寫入環境預先固定的值。
3. 確認 `/health` 為 200，再透過 Controller Restart API 執行生命週期操作。
4. Poll Controller 至 HEALTHY。Restart 後 fixture 的 `/health` 只有在原 marker
   仍存在且 byte-for-byte 相符時才會回 200；Runner 無須讀 Docker API/Volume。
5. 若測試網路允許直接 fixture probe，可額外用
   `GET /test-only/persistent-marker` 保存 SHA-256 證據；這不是生命週期成功的替代判定。

所有 lifecycle action 仍必須經 Controller API；marker endpoint 只建立與觀察案例前置
條件。

## Build and run

在本目錄執行：

```sh
docker build -t hermes-runtime-fixture:test .
docker run --rm --read-only --tmpfs /tmp \
  --mount type=volume,source=hermes-fixture-state,target=/state \
  -e FIXTURE_MODE=HEALTHY \
  -e FIXTURE_RUN_ID=example-run \
  -p 127.0.0.1:18000:8000 \
  hermes-runtime-fixture:test
```

正式 Controller E2E 不應發布 fixture host port；上例只供人工本機 smoke test。

## Unit tests

使用 CPython 3.13：

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install --no-deps -r requirements-test.lock
.venv/bin/python -m pytest
```

`requirements.lock` 與 `requirements-test.lock` 已列出 direct/transitive exact pins；
Docker build 也使用 `--no-deps`，避免 resolver 引入未鎖定版本。
