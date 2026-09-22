# FLAMORIS Intelligence MCP

MCP-native, provider-neutral intelligence gateway for FLAMORIS.

**Status: repository created; runtime implementation is not initialized yet.**

Part of the [FLAMORIS AI](https://github.com/flamoris-jp/flamoris-ai) family.

FLAMORIS Intelligence MCP is intended to expose language, reasoning, coding, and related intelligence capabilities through a stable MCP boundary while keeping local and remote model/provider details behind adapters.

It is not the persistent Agent, not the generative-media gateway, and not the owner of FLAMORIS product documents.

## Intended scope

The repository is planned to cover:

- MCP-facing intelligence tools and resources;
- provider-neutral request and result contracts;
- local and remote model/provider adapters;
- model/provider capability discovery where useful;
- routing between suitable intelligence providers;
- bounded task coordination and execution metadata within intelligence requests;
- scheduling or multi-agent execution only when an explicit Issue establishes the required contract, without taking ownership of persistent Agent identity or memory;
- health, diagnostics, and capability reporting appropriate to the intelligence boundary.

The exact transport, provider set, persistence model, runtime language, and public tool surface are not defined by this initial repository setup.

## Ecosystem boundaries

```text
FLAMORIS application / Studio
          │
          ├──────────────► flamoris-intelligence-mcp
          │                 language / reasoning / coding
          │
          └──────────────► flamoris-generation-mcp
                            image / video / music / voice

flamoris-ai-agent
          │
          ├──────────────► flamoris-intelligence-mcp
          └──────────────► flamoris-generation-mcp
```

These are boundaries, not mandatory layers.

### FLAMORIS AI Agent

[flamoris-ai-agent](https://github.com/flamoris-jp/flamoris-ai-agent) is the planned authority for conversations, memory, knowledge context, prompts, tools, and persistent agent behavior.

Intelligence MCP may execute requests for the Agent, but must not silently become a second owner of Agent memory or conversation state.

### FLAMORIS Generation MCP

[flamoris-generation-mcp](https://github.com/flamoris-jp/flamoris-generation-mcp) owns generative-media and closely related media-analysis workflows, jobs, and assets.

Intelligence MCP is deliberately separate from image, video, music, voice, and media-domain analysis that participates in Generation MCP's workflow/job/asset lifecycle.

### Product repositories

FLAMORIS 2D, Cutwork, Kachinco, Studio, and other applications remain authoritative for their own project/document state and editing behavior.

Intelligence MCP may assist those products through explicit MCP contracts but must not maintain competing product state.

### FLAMORIS Commons

Generic MCP foundations, logging, diagnostics, security primitives, and other non-AI-specific infrastructure belong in [FLAMORIS Commons](https://github.com/flamoris-jp/flamoris-commons) or its dedicated shared repositories.

## Design principles

1. **MCP is the FLAMORIS-facing boundary**
   - Applications and agents should consume stable intelligence capabilities instead of provider-specific APIs where practical.
   - Provider details stay behind adapters.

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

**現在はリポジトリ作成済みで、runtime実装はまだ初期化していません。**

local modelとremote providerの違いをadapterの内側へ閉じ込め、FLAMORIS側には安定したMCP境界を提供することを目的にします。

### 担当する予定のもの

- MCPから利用するintelligence tool / resource
- provider-neutralなrequest / result contract
- local / remote provider adapter
- model / provider capability discovery
- provider routing
- boundedなtask coordination / execution metadata
- 必要性が実装で確認された場合のscheduling / multi-agent execution
- health / diagnostics

### 担当しないもの

- **Conversation / Memory / Prompt / Agent policy**  
  → `flamoris-ai-agent`

- **画像・動画・音楽・音声のgeneration、および密接なmedia-domain analysisのworkflow / job / asset**  
  → `flamoris-generation-mcp`

- **2D / Cutwork / Kachinco / Studioなどの制作データ**  
  → 各製品リポジトリ

つまり、Intelligence MCPは「頭脳へつなぐ交換機」であって、人格の記憶庫でも制作ファイル倉庫でもない、という線を守ります。🧠

### ライセンス

このリポジトリのコードとドキュメントは、明記がない限りApache License 2.0です。

AI model、model weights、dataset、provider-hosted asset、第三者由来prompt、生成outputなどには別のライセンスや利用条件が適用される場合があります。それぞれ確認してください。
