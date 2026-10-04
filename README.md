# FLAMORIS Intelligence MCP

MCP-native, provider-neutral **external intelligence facade** for FLAMORIS.

**Status: Phase 1 Python runtime implemented and mock-tested. Live deployment acceptance remains a separate check.**

Part of the [FLAMORIS AI](https://github.com/flamoris-jp/flamoris-ai) family.

FLAMORIS Intelligence MCP exposes language, reasoning, coding, and related intelligence capabilities to external MCP clients through a stable boundary while keeping local and remote model/provider details behind adapters. Its primary FLAMORIS path is `ChatGPT -> MCP Hub -> Intelligence MCP`.

It is not the persistent Agent, not the generative-media gateway, and not the owner of FLAMORIS product documents.

See [assistant settings and model integration](docs/OPENAI_RESPONSES.md) for the opt-in extension and migration gates.

## Phase 1

The runtime exposes six tools: `system.health`, `capabilities.list/get`,
`models.list/get`, and synchronous `inference.execute`. The first adapter targets
llama.cpp's OpenAI-compatible chat endpoint, with GPT-OSS 20B as the example model.
The server stores no Agent conversation/memory and never starts/stops a runtime.

See [the public contract](docs/CONTRACT.md) for request/result schemas, errors,
limits, cancellation, trust boundaries, and downstream integration gates.
Implementation authority: [Issue #3](https://github.com/flamoris-jp/flamoris-intelligence-mcp/issues/3).
Track coordination: [FLAMORIS AI Track B](https://github.com/flamoris-jp/flamoris-ai/issues/6).

## Install and run

Python 3.11+ is required. The MCP host needs no GPU or model weights. Install from
this repository; llama.cpp must already be independently configured and reachable.

```sh
python -m venv .venv
# Activate the environment for your shell, then:
python -m pip install -e '.[dev]'
flamoris-intelligence-mcp
```

The default is stdio; stdout is reserved for MCP. Configure the MCP host to launch
this installed command. Explicit HTTP mode binds loopback only:

```sh
flamoris-intelligence-mcp --transport streamable-http --host 127.0.0.1 --port 8767 --mcp-path /mcp
```

The module entrypoint `python -m flamoris_intelligence_mcp` accepts the same options.
CLI options override the environment. HTTP has no application authentication; only
trusted local callers should reach it. External authentication/proxy deployment is
outside Phase 1. Do not publish this listener through an unauthenticated tunnel.
SDK Host/Origin checks stay enabled. One process means one shared admission limit;
multiple workers are not a shared GPU reservation system.

## Docker (Linux)

A multi-stage Python 3.12 image and `compose.yaml` provide a non-root, read-only
deployment without GPU libraries or model weights. Linux host networking preserves
the loopback-only listener while reaching the independently managed host provider.
The container healthcheck verifies MCP discovery independently of provider readiness.
See [Docker deployment and live acceptance](docs/DOCKER.md) for setup, network/trust
boundaries, configuration, update/restart, and the real GPT-OSS smoke procedure.

## Configuration

All variables below use the prefix `FLAMORIS_INTELLIGENCE_`. No `.env` file is
loaded automatically; supply environment variables through your service/client.

| Suffix | Default | Meaning |
| --- | --- | --- |
| `PROVIDER_URL` | `http://127.0.0.1:8081` | Trusted llama.cpp base URL, optional path prefix; no `/v1` suffix |
| `PROVIDER_API_KEY` | unset | Optional provider bearer credential; never exposed in discovery |
| `MODELS` | see below | JSON array of configured public IDs and served aliases |
| `TIMEOUT_SECONDS` | 120 | Whole inference deadline, positive and at most 300 |
| `HEALTH_TIMEOUT_SECONDS` | 5 | Health deadline, positive and at most 30 |
| `MAX_INPUT_BYTES` | 65536 | Combined input/instruction UTF-8 bytes, at most 262144 |
| `MAX_RESPONSE_BYTES` | 1048576 | Provider JSON body ceiling, at most 4194304 |
| `MAX_OUTPUT_BYTES` | 262144 | Final text UTF-8 ceiling, at most response ceiling/1048576 |
| `MAX_CONCURRENCY` | 1 | In-flight inference count per process, 1–16; overflow fails immediately |
| `TRANSPORT` | `stdio` | `stdio` or `streamable-http` |
| `HTTP_HOST` | `127.0.0.1` | `127.0.0.1` or `::1` only |
| `HTTP_PORT` | 8767 | Port 1–65535 |
| `MCP_PATH` | `/mcp` | Literal route, e.g. `/api/intelligence`; no trailing slash except `/` |

Default model registry (1–16 unique IDs allowed):

```json
[{"id":"gpt-oss-20b","provider_model":"gpt-oss-20b","context_tokens":32768,"max_output_tokens":4096}]
```

Set `provider_model` to the alias actually served by your llama.cpp deployment.
It is passed only inside the adapter, never returned as a filesystem path in
public discovery. Context/output limits must match the deployed model. Public
model selection never activates/switches models or GPU runtimes. Use [GPU Node Manager](https://github.com/flamoris-jp/flamoris-gpu-node-manager)
for the `llm` runtime lifecycle; this MCP only reports availability and executes.

Calls send the caller's input/instruction to the configured provider. Remote URLs
are an explicit operator choice, not a hidden fallback. Provider redirects and
environment proxies are disabled. No implicit retries occur. The process has no
durable prompt/output storage; provider-side logging remains the operator's concern.

## Manual deployment smoke

This repository does not deploy a service or change LIME runtime state. On a host
where the runtime manager has already activated the LLM, install this package,
configure the provider URL/model registry above, then run:

```sh
python examples/smoke.py --model gpt-oss-20b
```

The script launches the installed stdio MCP, checks health, and performs one small
request through `inference.execute`. Record the tested commit, public model ID,
health, finish reason, and success/failure in Issue #3; exclude hostnames, credentials,
and private prompts. Mock tests do not establish real GPT-OSS quality or deployment
readiness. A live smoke has not been performed by this implementation's CI.

To check an already running HTTP container, use
`python examples/smoke.py --url http://127.0.0.1:8767/mcp --model gpt-oss-20b`.
Both modes check health, models, and capabilities before inference.

## Development

```sh
python -m pytest -q
ruff check .
ruff format --check .
python -m build
```

CI runs on Python 3.11/3.12 without live providers, credentials, GPUs, or weights.
Tests exercise validation, HTTP errors, resource bounds, cancellation, admission,
real stdio/HTTP MCP clients, protocol negotiation, and installed-package behavior.
The official MCP SDK 2.x owns transport infrastructure. No .NET package is required.
No generic FLAMORIS MCP Python package is vendored here.
CI also builds the production image and verifies non-root/read-only startup,
provider-independent health, HTTP discovery, and restart without a GPU or weights.

## Ecosystem boundaries

```text
External MCP:
ChatGPT
   ↓
MCP Hub
   ↓
flamoris-intelligence-mcp
   ↓
approved intelligence capability / provider

Internal FLAMORIS:
Studio / AI Agent / AI Runtime
   ↓
non-MCP internal execution interfaces
```

MCP is an external adapter boundary, not the internal service bus for Studio, Agent, or AI Runtime.

### FLAMORIS AI Agent

[flamoris-ai-agent](https://github.com/flamoris-jp/flamoris-ai-agent) is the persistent Agent authority for conversations, memory, knowledge context, prompts, tools, and long-lived agent behavior. Its bounded Agent MCP surface is already implemented; broader Agent capabilities continue to evolve there.

AI Agent does not use Intelligence MCP as its canonical internal execution dependency. Agent keeps a replaceable non-MCP execution boundary for local Runtime, API, or vendor-runtime targets. Intelligence MCP may expose an external Agent-related capability only through a separately reviewed internal call without becoming Agent state authority.

### FLAMORIS Generation MCP

[flamoris-generation-mcp](https://github.com/flamoris-jp/flamoris-generation-mcp) is the external MCP facade for generative-media capabilities. Generation-domain ownership is being separated under FLAMORIS AI #18; do not infer internal MCP dependencies from this documentation.

Intelligence MCP is deliberately separate from image, video, music, voice, and media-domain analysis that participates in the generation-definition/job/asset lifecycle.

### Product repositories

FLAMORIS 2D, Cutwork, Kachinco, Studio, and other applications remain authoritative for their own project/document state and editing behavior.

Product applications do not use Intelligence MCP as their canonical internal provider gateway. External MCP clients may use this facade without transferring product-state authority.

### FLAMORIS Commons

Generic MCP foundations, logging, diagnostics, security primitives, and other non-AI-specific infrastructure belong in [FLAMORIS Commons](https://github.com/flamoris-jp/flamoris-commons) or its dedicated shared repositories.

## Design principles

1. **MCP is the external ChatGPT-facing boundary**
   - External MCP clients consume stable intelligence capabilities through MCP Hub / Intelligence MCP.
   - Internal Studio, Agent, and AI Runtime dependencies use non-MCP interfaces.
   - Provider details used by this MCP stay behind its adapters.

2. **Provider-neutral does not mean lowest-common-denominator**
   - Define shared contracts where behavior is genuinely common.
   - Expose provider-specific capabilities explicitly when they cannot be represented honestly by the shared contract.

3. **No Agent-memory authority**
   - Request context may be accepted for execution.
   - Persistent conversations, user memory, Agent policy, and knowledge ownership belong to `flamoris-ai-agent`.

4. **No media-generation authority**
   - Image, video, music, and voice generation jobs belong to `flamoris-generation-mcp`.

5. **Local-first without local-only assumptions**
   - Local LLMs and coding models should be first-class providers.
   - Remote services may use the same explicit provider boundary.
   - Do not bake one machine, vendor, or deployment topology into the public architecture.

6. **Bounded execution**
   - Time, concurrency, context size, output size, retries, filesystem access, network access, and resource use should be bounded deliberately.
   - Non-idempotent operations must not be retried invisibly after ambiguous failures.

7. **Inspectability over hidden cleverness**
   - Routing and orchestration decisions should be explainable through metadata or diagnostics where practical.
   - Avoid opaque provider switching that makes debugging or reproducibility impossible.

## Repository policy

This repository follows the shared [FLAMORIS Repository Policy](https://github.com/flamoris-jp/flamoris-commons/blob/main/docs/repository-policy.md).

Intelligence-specific provider, privacy, MCP, and resource-safety rules supplement that shared policy.

## License

Code and documentation in this repository are licensed under the [Apache License 2.0](LICENSE), unless otherwise noted.

AI models, model weights, datasets, provider-hosted assets, prompts supplied by third parties, generated outputs, and other non-code material are not automatically covered by this repository's license. Their applicable licenses and usage terms must be checked separately.

Commercial use of Apache-2.0 licensed FLAMORIS code does not require permission.

FLAMORIS software is provided as-is and does not include guaranteed individual support. AI-assisted self-support is encouraged.

---

## 日本語

FLAMORIS Intelligence MCPは、LLM、推論、Coding AIなどの「知能側」をMCPから扱うためのprovider-neutral gatewayです。

**Phase 1のPython runtimeを実装し、mockによる自動テストを用意しています。実機での受け入れ確認は別途行います。**

local modelとremote providerの違いをadapterの内側へ閉じ込め、FLAMORIS側には安定したMCP境界を提供することを目的にします。

### 現在の実装と将来の範囲

- 現在: health、設定済みmodel/capabilityのdiscovery、同期の`inference.execute`
- 現在: llama.cpp adapter、入力/出力/時間/同時実行数の制限、正規化したエラー
- stdioが既定。明示的にloopback Streamable HTTPも利用可能
- 将来: Issueで定義されたproviderや実行機能の追加

公開契約は [docs/CONTRACT.md](docs/CONTRACT.md) を参照してください。
MCP Hubへの組み込みはこの外部MCP contractを利用します。Studio / AI Agentの内部実行経路はMCPを使わず、別の内部interfaceを利用します。

### 担当しないもの

- **Conversation / Memory / Prompt / Agent policy**  
  → `flamoris-ai-agent`

- **画像・動画・音楽・音声のgeneration、および密接なmedia-domain analysisのgeneration definition / job / asset**  
  → `flamoris-generation-mcp`

- **2D / Cutwork / Kachinco / Studioなどの制作データ**  
  → 各製品リポジトリ

つまり、Intelligence MCPは「頭脳へつなぐ交換機」であって、人格の記憶庫でも制作ファイル倉庫でもない、という線を守ります。🧠

### ライセンス

このリポジトリのコードとドキュメントは、明記がない限りApache License 2.0です。

AI model、model weights、dataset、provider-hosted asset、第三者由来prompt、生成outputなどには別のライセンスや利用条件が適用される場合があります。それぞれ確認してください。


## Architecture correction status

FLAMORIS AI #18 supersedes the earlier internal-consumer direction. The current implementation may still contain provider adapters and historical downstream assumptions, but new internal Agent/Studio dependencies must not be added. The next implementation phase should remove internal MCP-specific coupling first, while preserving this repository's external MCP tools, bounds, privacy controls, and provider behavior.
