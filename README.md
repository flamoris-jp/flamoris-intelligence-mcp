# FLAMORIS Intelligence MCP

Provider-neutral external intelligence MCP facade for FLAMORIS. Part of [FLAMORIS AI](https://github.com/flamoris-jp/flamoris-ai).

## Role and current implementation

Target external path: **ChatGPT -> MCP Hub -> Intelligence MCP -> approved internal intelligence capability**. Internal Studio, Agent and AI Runtime callers use non-MCP execution interfaces in the corrected architecture. This is a target boundary: existing callers have not been migrated by this documentation PR.

The current Python implementation exposes six tools: `system.health`, `capabilities.list/get`, `models.list/get` and synchronous `inference.execute`. It includes the llama.cpp adapter and configured opt-in [OpenAI Responses adapter](docs/OPENAI_RESPONSES.md). It stores no durable Agent conversation/memory and does not start/stop GPU runtimes. Actual provider/model availability and deployment acceptance are separate from code and offline tests.

[AI #18](https://github.com/flamoris-jp/flamoris-ai/issues/18) and [local #10](https://github.com/flamoris-jp/flamoris-intelligence-mcp/issues/10) supersede the old internal-gateway architecture. The first later implementation task is removal of internal MCP coupling, not deletion of this external facade or automatic duplication of provider adapters. No code, tool schema or live configuration changes in this documentation pass. Generation Controller remains unimplemented.

## Contracts and boundaries

Read [CONTRACT.md](docs/CONTRACT.md) for current request/result schemas, limits, errors, cancellation and trust. [OPENAI_RESPONSES.md](docs/OPENAI_RESPONSES.md) records the current remote adapter/configuration, not a mandate that Agent calls MCP internally.

Agent owns optional personality, conversation/memory, principal/session and context/export policy. An external personality capability may reach Agent through a separately reviewed internal call; raw inference does not require it. Internal execution adapter ownership is decided against actual callers, not by creating a new central gateway by default.

Generation MCP is a separate external facade. Generation-domain requests, jobs, references and assets do not belong here; future Controller ownership is deferred under AI #18. ComfyWorkFlow means ComfyUI graph/JSON, ExecuteFlow means Runtime inference flow, and the existing compiled ExecutionPlan remains distinct. None is an obligatory layer for an ordinary API call.

Products retain their own document/editing state. GPU Node Manager retains host-wide lifecycle control. Generic MCP/logging/security foundations belong in Commons or dedicated shared packages. No component acquires domain authority merely because it provides a transport.

## Install and run: existing implementation reference

These are current package commands, not rollout instructions for the architecture correction. Python 3.11+ is required. The MCP process needs no GPU/model weights; its provider must be independently configured and reachable.

```sh
python -m venv .venv
# Activate the environment before installing.
python -m pip install -e '.[dev]'
flamoris-intelligence-mcp
```

stdio is the default; stdout is reserved for MCP. Explicit loopback HTTP:

```sh
flamoris-intelligence-mcp --transport streamable-http --host 127.0.0.1 --port 8767 --mcp-path /mcp
```

`python -m flamoris_intelligence_mcp` accepts the same options. CLI settings override environment. HTTP has no application authentication; retain loopback/SDK Host-Origin checks and a separately reviewed authenticated boundary for remote access. Do not publish an unauthenticated listener. One process has a shared admission budget; multiple workers do not create a shared GPU reservation.

See [Docker deployment](docs/DOCKER.md) for existing non-root/read-only Linux deployment and acceptance. Container liveness does not establish provider readiness. No deployment is performed by this PR.

## Current configuration

All suffixes below use `FLAMORIS_INTELLIGENCE_`. No `.env` file is automatically loaded.

| Suffix | Default | Meaning |
| --- | --- | --- |
| `PROVIDER_URL` | `http://127.0.0.1:8081` | Trusted llama.cpp base URL, no `/v1` suffix |
| `PROVIDER_API_KEY` | unset | Optional provider bearer credential |
| `MODELS` | example below | Configured public IDs and served aliases |
| `TIMEOUT_SECONDS` | 120 | Whole inference deadline, at most 300 |
| `HEALTH_TIMEOUT_SECONDS` | 5 | Health deadline, at most 30 |
| `MAX_INPUT_BYTES` | 65536 | Combined input/instruction ceiling, at most 262144 |
| `MAX_RESPONSE_BYTES` | 1048576 | Provider JSON ceiling, at most 4194304 |
| `MAX_OUTPUT_BYTES` | 262144 | Final text ceiling, at most response ceiling/1048576 |
| `MAX_CONCURRENCY` | 1 | Per-process in-flight admission, 1-16 |
| `TRANSPORT` | `stdio` | `stdio` or `streamable-http` |
| `HTTP_HOST` | `127.0.0.1` | `127.0.0.1` or `::1` only |
| `HTTP_PORT` | 8767 | Port 1-65535 |
| `MCP_PATH` | `/mcp` | Literal route without trailing slash except `/` |

Default model registry:

```json
[{"id":"gpt-oss-20b","provider_model":"gpt-oss-20b","context_tokens":32768,"max_output_tokens":4096}]
```

Use the alias actually served by the provider and limits supported by it. Selection does not activate models or switch GPU runtimes. Discovery is not proof that weights are loaded. OpenAI-specific keys, model entries and configured cost bounds remain in [the adapter document](docs/OPENAI_RESPONSES.md); they are not moved by this correction.

Provider endpoints/credentials are operator configuration, not caller-selected URLs or conversation data. Calls disclose input to the configured provider; remote use is explicit, not fallback. Redirects, environment proxies and implicit inference retries are disabled. No durable prompt/output storage is added; provider-side retention is a separate concern.

## Development and acceptance

```sh
python -m pytest -q
ruff check .
ruff format --check .
python -m build
```

Normal tests use fakes and do not require GPUs, weights, paid APIs or secrets. Transport, package and container tests do not certify model quality or live readiness. Explicit manual smoke references remain `python examples/smoke.py --model gpt-oss-20b` and `python examples/smoke.py --url http://127.0.0.1:8767/mcp --model gpt-oss-20b`; do not run them as part of this documentation pass. Record actual acceptance in the owning Issue, independently of CI.

## 日本語

Intelligence MCPはChatGPTがMCP Hub経由で使う外部入口です。Studio/Agent/Runtime内部の共通Gatewayにはしません。現在のMCP実装や呼び出し元は文書だけでは移行されていません。

次のIntelligence整備では内部MCP依存を削除する範囲と代替の最小内部契約を先に確認します。外部MCP、既存providerの有効な処理、認可・上限・秘匿・不確定結果の扱いまで消す指示ではありません。Generation Controllerはまだ実装しません。

## Policy and license

Follow the [FLAMORIS repository policy](https://github.com/flamoris-jp/flamoris-commons/blob/main/docs/repository-policy.md). Keep provider-specific behavior explicit where it cannot honestly fit a common contract, preserve bounded execution, and do not add hidden routing or fallback.

Code and documentation are licensed under [Apache License 2.0](LICENSE), unless otherwise noted. Model weights, datasets, provider assets, third-party prompts and generated output may have separate terms. Software is provided as-is without guaranteed individual support; repository documents, Issues, tests and source are the primary self-support references.
