# Tech Stack規格

> 文件目的：凍結PoC的建議實作技術、版本系列、Dependency Lock與Docker Image組成，避免平台與測試實作者選用互不相容的工具。
>
> 適用角色：平台實作者、測試實作者、Build與環境管理者。
>
> 文件狀態：Draft v0.1；實際Patch版本須以內部Registry可取得且經核准的版本鎖定。

## 技術總表

| 層級 | 技術 | 版本基準 | 用途 |
|---|---|---|---|
| Frontend | React＋TypeScript | React 19.2.x | Portal UI |
| Frontend Build | Vite | 與React 19相容穩定版 | Build靜態資產 |
| UI | Material UI | 鎖定穩定版 | 表格、表單、狀態與通知 |
| Server State | TanStack Query | 鎖定穩定版 | API狀態與Cache |
| Form | React Hook Form＋Zod | 鎖定穩定版 | 表單與前端驗證 |
| Portal Backend | Python＋FastAPI | Python 3.13 | API、Task、History、Evaluation |
| ASGI | Uvicorn | 鎖定版本 | FastAPI Runtime |
| Schema | Pydantic v2 | 鎖定版本 | Request/Response驗證 |
| HTTP | HTTPX | 鎖定版本 | 呼叫Controller與Hermes |
| ORM | SQLAlchemy 2.x | 2.0系列 | Persistence |
| Migration | Alembic | 鎖定版本 | DB Schema版本 |
| PoC DB | SQLite 3 | Python Runtime支援版 | 單機資料保存 |
| Controller | Python＋FastAPI | Python 3.13 | Docker控制API |
| Docker Client | Docker SDK for Python | 鎖定版本 | Docker Engine API，不使用Shell |
| Runtime | Docker Engine＋Compose v2 | 內部核准版本 | Container部署 |
| UI E2E | Playwright＋TypeScript | 1.61.x且Image/Package一致 | Portal黑箱E2E |
| Controller E2E | pytest＋HTTPX | 鎖定版本 | Controller黑箱E2E |
| Frontend Unit | Vitest＋Testing Library | 鎖定版本 | Component Test |
| Python Test | pytest＋pytest-asyncio | 鎖定版本 | Unit/Integration Test |
| Python Quality | Ruff＋mypy | 鎖定版本 | Lint、Format、Type Check |
| Frontend Quality | ESLint＋Prettier＋tsc | 鎖定版本 | Lint、Format、Type Check |
| Report | JUnit XML＋Playwright HTML/Trace | — | 自動化證據 |

## Portal Image

`portal/Dockerfile`採Multi-stage：

```text
Stage frontend-build
  Base: node:24-bookworm-slim（內部Mirror）
  npm ci
  npm run build

Stage runtime
  Base: python:3.13-slim（內部Mirror）
  安裝requirements.lock
  複製Backend
  複製Frontend dist
  建立非root使用者
  啟動Uvicorn
```

PoC由FastAPI提供React靜態資產，因此不增加Nginx Container。

## Controller Image

`controller/Dockerfile`使用`python:3.13-slim`，只包含FastAPI、Uvicorn、Pydantic、HTTPX、Docker SDK與Log所需依賴。不得安裝Docker CLI作為操作捷徑。

## Test Images

| Image | Base | 說明 |
|---|---|---|
| Portal E2E | Playwright Noble固定Patch版的內部Mirror | Package版本必須與Image一致 |
| Controller E2E | `python:3.13-slim` | pytest、HTTPX、JUnit、Coverage |
| Hermes Fixture | `python:3.13-slim` | FastAPI/Uvicorn模擬健康與失敗模式 |
| Test Docker Engine | 核准且固定版的隔離Daemon或Rootless環境 | 不可使用正式Docker Context |

## Dependency規則

- JavaScript使用`package-lock.json`與`npm ci`。
- Python使用精確版本的`requirements.lock`；不得只有寬鬆Range。
- Docker Base Image不得使用`latest`。
- 正式交付建議同時固定Image Digest。
- 所有套件與Base Image需事先Mirror到內部Registry或Artifact Repository。
- Build不得臨時連外取得依賴。

## API與資料格式

- REST JSON API。
- OpenAPI 3.1作為介面Contract。
- JSON Schema 2020-12作為Agent與Domain Response Contract。
- 時間使用UTC RFC 3339字串。
- ID使用UUID或不可猜測字串；測試Fixture可使用固定ID。
- Log使用JSON Lines並包含`correlation_id`、`task_id`或`instance_id`。

## 明確不採用

| 技術 | v0.1不採用原因 |
|---|---|
| Kubernetes | 單機PoC不需要 |
| PostgreSQL | SQLite足以支援單Portal Writer |
| Redis/RabbitMQ/Celery | 尚無大規模背景工作 |
| Redux | UI狀態不複雜 |
| Nginx | FastAPI可提供PoC靜態資產 |
| 任意Agent Framework抽象層 | 先驗證Hermes，不增加多Runtime抽象 |
| Vector Database | 先驗證既有Hermes讀檔與Knowledge能力 |

## 升級條件

- 多Portal Worker或多人高併發：SQLite改PostgreSQL。
- 任務長時間排隊：加入Queue及Worker。
- 多Hermes Instance：加入Template Registry與動態Provisioning。
- 正式多人使用：加入OIDC/SSO、RBAC與集中Audit。
