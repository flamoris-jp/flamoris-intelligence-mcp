# Non-MCP intelligence execution

The distribution retains its existing `flamoris-intelligence-mcp` identity. It now
contains two Python boundaries: `flamoris_intelligence` is the reusable stateless
provider implementation, and `flamoris_intelligence_mcp` is the optional external
MCP facade. Installing the distribution without extras requires only HTTP and
validation dependencies. The `mcp` extra installs the MCP SDK for external tools;
internal calls neither import it nor negotiate a connection.

This is an importable interface, not a new HTTP gateway, host runtime controller,
Agent owner or generic ExecuteFlow engine. Agent and Studio reuse provider I/O,
validation, normalization and bounded execution instead of copying vendor code.
Legacy provider/service import paths under `flamoris_intelligence_mcp` remain
compatibility imports. Their existence does not authorize internal MCP routing.

## Direct contract

```python
from flamoris_intelligence import ModelEntry, Settings, create_service

service = create_service(
    Settings(
        provider_url="http://127.0.0.1:8081",
        models=(ModelEntry(id="approved-local", provider_model="served-alias"),),
    )
)
try:
    descriptor = await service.model_available("approved-local")
    result = await service.execute_messages(
        {
            "model_id": "approved-local",
            "messages": [
                {"role": "system", "content": "caller-authorized policy"},
                {"role": "user", "content": "caller-authorized input"},
            ],
            "max_output_tokens": 1024,
        }
    )
finally:
    await service.close()
```

`Settings` contains provider configuration and bounds only; the facade's derived
`Settings` adds MCP transport configuration. Construct direct settings from trusted
operator configuration. Callers cannot supply provider URLs, credentials, aliases,
limits or export permissions in inference input. OpenAI requires an explicitly
configured credential, pricing and a request cost ceiling, and uses the fixed
OpenAI HTTPS endpoint. There is no provider selection, fallback or retry.

| Method | Contract |
| --- | --- |
| `model(model_id)` | Configured public descriptor; no network or activation |
| `model_available(model_id)` | Bounded exact served-alias check; returns descriptor plus `available: true`, or raises a fixed `IntelligenceError` |
| `validate(raw)` / `execute(raw)` | Existing raw `model_id`, `input`, optional `instruction` and sampling/budget fields |
| `validate_messages(raw)` / `execute_messages(raw)` | `model_id`, ordered `messages`, optional `capability_id`, `max_output_tokens`, `temperature`, `timeout_seconds` |
| `close()` | Closes local provider clients; does not prove remote inference stopped |

Messages have exactly `role` (`system`, `user`, `assistant`) and string `content`.
One to 128 messages are permitted. Full ordered role context is sent unchanged;
there is no transcript-to-user flattening, hidden history or provider conversation
ID. Validation allows a system-only request for startup/context checks. The caller
owns which valid conversation turns it may actually execute.

Validation rejects unknown fields, invalid UTF-8, empty context, excessive input,
output/context budget and deadlines before dispatch. Message context accounting
includes a conservative per-message template allowance. Provider response I/O,
output bytes, in-flight inference, health/model probes and whole request time remain
bounded. Cancellation propagates, frees local capacity and closes awaited I/O;
remote completion or billing remains uncertain and work is never replayed.

Successful execution returns the same bounded normalized object as the external
raw contract: `ok`, request-scoped `execution_id`, public `provider_id`, public
`model_id`, `capability_id`, `text`, `finish_reason`, optional `usage` and configured
OpenAI cost estimate. Failures use fixed `ok: false`, `execution_id`, `error.code`
and `error.message`; no upstream body, URL, credential or context is exposed.
Returned provider model identity is checked when available. Exact model probes
check the configured served alias separately from public discovery.

Agent and Studio retain authentication, principal isolation, model grants,
conversation ownership, complete-context remote consent, provenance and request
fences before dispatch. This library has no database or durable user policy and
cannot grant those permissions. An explicitly configured remote model does not
itself authorize sending a particular user's context.

## Installation and migration

Internal consumers install an exact approved Git commit of the base distribution;
external entrypoints install the same commit with `[mcp]`. A mutable branch is not
a deployment pin. Consumer rollout, credentials, model registry changes and live
cutover remain separate operational work. Existing deployed MCP clients do not
migrate merely because this shared library is available.

Tests exercise direct ordered context, exact model identity, neutral imports
without the SDK, bounds, privacy, no-replay and the unchanged six external tools.
Offline tests and wheel installation do not establish real provider readiness.
