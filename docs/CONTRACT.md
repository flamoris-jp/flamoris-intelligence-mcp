# Intelligence MCP Phase 1 contract

Version: package 0.1.0. Owning specification: [Issue #3](https://github.com/flamoris-jp/flamoris-intelligence-mcp/issues/3).

This synchronous contract is intended for raw LLM use by clients, including Studio
and a future Agent execution adapter. It has no conversation/job/session database,
memory, tool loop, generated assets, or runtime switching API. Protocol sessions
are not Agent conversations. Hub routing must preserve the upstream arguments,
structured result, and MCP `isError` flag.

## Tools

| Tool | Arguments | Structured result |
| --- | --- | --- |
| `system.health` | none | `healthy`, version, active requests, providers with availability/error |
| `capabilities.list` | none | `capabilities` array |
| `capabilities.get` | `capability_id` | One capability or normalized error |
| `models.list` | none | `models` array |
| `models.get` | `model_id` | One model or normalized error |
| `inference.execute` | `request` object below | Success or error envelope |

`text.generate`, `reasoning.generate`, and `code.generate` describe the caller's
intent. They use the same inference path and do not install hidden system prompts,
change sampling, or promise specialized model quality. The caller supplies all
instruction context explicitly. `reasoning.generate` returns the final answer;
provider-specific internal reasoning fields are not forwarded or persisted.

Discovery is configuration metadata, works offline, and is not proof of loaded
weights or provider readiness. Provider availability is checked by `system.health`.
That check does not prove every configured model alias is currently served.
`healthy: true` describes this MCP process, independently of provider availability.

## Execution request

```json
{
  "request": {
    "model_id": "gpt-oss-20b",
    "capability_id": "code.generate",
    "input": "Write a Python function that returns the larger of two numbers.",
    "instruction": "Return concise Python code.",
    "max_output_tokens": 256,
    "temperature": 0.2,
    "timeout_seconds": 60
  }
}
```

| Field | Required/default | Bounds |
| --- | --- | --- |
| `model_id` | required | Configured public ID; never a URL or filesystem path |
| `input` | required | Nonblank text; combined UTF-8 byte limit with instruction |
| `instruction` | empty string | Explicit optional system context |
| `capability_id` | `text.generate` | One of the three advertised capabilities |
| `max_output_tokens` | 1024 | Integer, 1 to configured model maximum; hard ceiling 32768 |
| `temperature` | 0.7 | Finite number from 0 to 2 |
| `timeout_seconds` | server deadline | Positive finite number, no greater than server deadline |

Unknown fields and coercions such as string token counts are rejected. No caller
may choose provider URLs, credentials, prompt templates, arbitrary paths, tools,
or hidden retries. Text/code attachments must be read and authorized by the caller
and supplied as bounded text; this server never reads attachment paths or URLs.

Input admission also requires:

`UTF-8 bytes(input + instruction) + 512 + max_output_tokens <= context_tokens`.

This is a deliberately conservative budgeting heuristic with a fixed chat-template
allowance, **not an exact tokenizer or a guarantee for every chat template**. Set
context limits conservatively for the deployed model/template. llama.cpp performs
final token/context validation; a context rejection maps to `provider_rejected`.

## Success result

MCP `structuredContent` and JSON text content carry the same object; `isError` is false.

```json
{
  "ok": true,
  "execution_id": "request-scoped UUID",
  "provider_id": "llamacpp",
  "model_id": "gpt-oss-20b",
  "capability_id": "code.generate",
  "elapsed_ms": 230,
  "text": "def larger(a, b):\n    return max(a, b)",
  "finish_reason": "stop",
  "usage": {"input_tokens": 30, "output_tokens": 15, "total_tokens": 45}
}
```

`finish_reason` is `stop` or `length`. A `length` result may be partial, or empty if
the model used the budget before reaching a final answer. Usage is null when not
provided; otherwise counts must be nonnegative integers, internally consistent,
and within the requested output budget. Counts remain provider-reported metadata,
not independently audited billing data. Additional provider fields, IDs, model
paths, timings, internal reasoning, and raw errors are not copied into results.

The execution ID is only correlation metadata; there is no polling/retrieval API
or durable output store. Studio owns its user-scoped product state, and Agent owns
its conversations/memory. Neither should manufacture an upstream persistent job.

## Error result

Execution errors set MCP `isError: true` and return:

```json
{
  "ok": false,
  "execution_id": "request-scoped UUID",
  "error": {"code": "provider_unavailable", "message": "The configured provider is unavailable."}
}
```

Discovery errors use the same `ok/error` structure without an execution ID.
Protocol-level failures (bad MCP framing, unknown tool, invalid outer arguments)
remain SDK errors. Messages from domain/provider failures are fixed public strings;
they do not include request bodies, URLs, credentials, or provider response bodies.

Codes: `invalid_request`, `unknown_model`, `unknown_capability`, `context_limit`,
`busy`, `provider_unavailable`, `provider_timeout`, `provider_rejected`,
`provider_unauthorized`, `provider_busy`, `invalid_provider_response`,
`response_limit`, `internal_error`.

HTTP 401/403 maps to provider authentication failure, 429 to provider busy, 5xx to
provider unavailable, and other non-200 statuses (including redirects) to provider
rejected. These never trigger automatic retries/fallback. The caller must treat a
timeout/disconnection as ambiguous: inference may already have run remotely.

## Time, concurrency, cancellation, lifecycle

- One process owns one service and a fail-fast inference capacity limit. No queue.
- All clients of that process share capacity. Multiple processes have independent
  limits; deploy a single worker for one shared admission limit. This is not a GPU
  reservation and does not exclude other llama.cpp users or other FLAMORIS services.
- At most one provider health probe runs at a time, separately from inference.
- The deadline covers the provider operation, including a slowly streamed body.
- MCP cancellation, when delivered by the transport, cancels local awaited work,
  closes the outgoing response, and releases local capacity in `finally`.
- A dropped client connection is not a reliable cancellation notification on every
  transport. The server deadline remains the bound; no cancel-by-ID tool is provided.
- Local cancellation/timeout does **not** guarantee remote GPU work has stopped.
  No global provider interrupt is sent, because it could cancel another user.
- Shutdown closes the shared HTTP client. No durable context/cache/database is created.

## Transport and trust

The official MCP Python SDK 2.x owns framing, negotiation, tools, and transports.
stdio is the default. Streamable HTTP is explicitly selected and loopback-only
(`127.0.0.1` or `::1`) with SDK Host/Origin checks, stateless handling, JSON responses,
and a 2 MiB request-body ceiling. No subscription stream/resumption is offered.

HTTP has no application authentication in Phase 1. Local OS users/processes that
can reach it can invoke inference. A future Hub or authenticated proxy must enforce
external caller authentication/authorization and compatible Host/Origin forwarding.
Do not expose the loopback listener through an unauthenticated tunnel.

The [Docker deployment](DOCKER.md) uses Linux host networking, preserving this
loopback-only contract. Its healthcheck negotiates MCP and checks tool discovery
without calling the provider. Container health therefore remains independent of
provider availability; use `system.health` for that separate diagnostic.

Provider HTTP uses only the configured trusted base URL, no redirects or environment
proxies, and identity encoding to avoid compressed-body expansion. Received bytes and
final UTF-8 output are bounded independently. For stdio the SDK parses input before
domain limits apply; use a trusted host and OS process limits for hostile framing.

Prompts/instructions are sent to the operator-configured provider. A remote URL is
an explicit operator choice and must be disclosed to callers. No remote provider is
auto-discovered or selected. Provider-side logging/retention is outside this process;
operators must review llama.cpp/proxy settings. Default application logs do not record
prompts, generated text, or credentials. Do not enable wire/debug logging for private data.

## Downstream gates

- Hub integration: after this contract is reviewed and merged, create the owning Hub
  Issue and add a lazy catalog. Do not implement inference orchestration in Hub.
- Studio: [#2](https://github.com/flamoris-jp/flamoris-studio/issues/2) after merge;
  retain `IIntelligenceGateway` and user isolation. No direct llama.cpp calls.
- Agent: Track C consumes this boundary only after its baseline/client boundary is
  stable. Agent keeps all identity, conversation, knowledge, and memory authority.

Upstream references: [official MCP SDK](https://github.com/modelcontextprotocol/python-sdk)
and [llama.cpp server API](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).
