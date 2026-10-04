# Configured OpenAI Responses

Owning scope: Intelligence MCP external OpenAI provider adapter. FLAMORIS AI #18 supersedes the earlier assumption that Agent or Studio consume this adapter through internal MCP calls.

The existing six MCP tools remain unchanged. `ModelEntry.provider_id` defaults to
`llamacpp` and explicitly supports `openai`. Both providers can coexist; no runtime
switch/fallback is made. Discovery gives configured public IDs, not provider aliases,
URLs, keys or filesystem paths. This MCP owns no conversation/personality state. Internal Agent/Studio remote-provider selection and context-export policy belong to their non-MCP execution boundaries.

The OpenAI adapter uses the fixed `https://api.openai.com/v1/responses` endpoint.
Its stateless text request supplies model, input, instructions, max_output_tokens,
store=false, stream=false, background=false, tools=[] and truncation=disabled.
Temperature is deliberately omitted because model support varies. This initial
adapter does not expose custom tools, media inputs, provider conversations,
previous_response_id, auto truncation or background jobs. Response model must match
the exact configured provider_model snapshot. Use a pinned snapshot rather than an
alias that the provider may resolve to a different model. Refusals/tool results,
malformed usage and noncompleted/error responses never become successful text.
A max_output_tokens incomplete response normalizes to finish_reason=length.

Contract verified against the [official OpenAI Responses reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
on 2026-10-04 JST. It defines the request flags, output items/status and input/output/
total usage, including reasoning within the output-token ceiling. Model availability
and live API behavior still require operator acceptance, not test fixtures.

## Configuration

Configure only on the Intelligence service:

- `FLAMORIS_INTELLIGENCE_MODELS`: 1..16 unique IDs. Local entries are compatible;
  remote entries add provider_id=openai and an exact provider_model snapshot.
- `FLAMORIS_INTELLIGENCE_OPENAI_API_KEY`: required when any OpenAI model is configured.
- `FLAMORIS_INTELLIGENCE_OPENAI_INPUT_USD_PER_MILLION` and
  `FLAMORIS_INTELLIGENCE_OPENAI_OUTPUT_USD_PER_MILLION`: positive operator-supplied
  upper price estimates covering **every** configured OpenAI model. These are not
  baked-in vendor price claims. Update deliberately when pricing changes.
- `FLAMORIS_INTELLIGENCE_OPENAI_MAX_REQUEST_USD`: positive <=100 admission estimate
  ceiling, applied before inference. Conservative UTF-8 bytes plus template allowance
  bound the input estimate; max_output_tokens bounds output. Usage is normalized and
  `estimated_cost_usd` reports the measured token counts at configured rates. This is
  an estimate/per-request admission bound, not a monthly/provider billing guarantee.

Input, JSON response, output text, timeout and concurrency use existing Settings bounds.
Capacity is per provider so a running/offline local provider does not reserve API
capacity. At most two configured provider budgets exist per process. Health reports
providers independently; `models.get` also performs a bounded free authenticated
GET model check for OpenAI. External MCP callers may use exact-model availability rather than assuming all aliases are usable from general provider health. GET probes send
no personality, transcript or Studio draft and perform no inference.

No redirects, environment proxies or retries. Transport close/cancel frees local
work but cannot guarantee cancellation or absence of charges after remote acceptance.
429/authentication/server/time/size failures return fixed sanitized codes. Logs and
public errors do not include provider bodies or credentials. store=false disables
Response storage; it does not promise that all provider-side processing/log retention
is zero. Follow the configured account's provider privacy terms.

Normal tests use httpx mocks and synthetic text only. Deployment, real keys, grants,
paid smoke and local-GPU/image coexistence acceptance remain separate. Docker uses
the same configuration; no new dependency or GPU library is needed.


## Boundary correction

This adapter remains valid for external MCP use of OpenAI Responses API. It is **not** the canonical internal API provider for AI Agent or Studio. Do not route Agent personality/conversation traffic through Intelligence MCP merely to reuse this adapter. The internal execution adapter ownership is handled separately under AI Agent / AI Runtime design. No code removal is implied by this documentation-only change; implementation cleanup is a later reviewed step.
