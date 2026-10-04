# AGENTS.md

## Scope and current stage

This repository provides FLAMORIS's external intelligence MCP facade. Read README.md, docs/CONTRACT.md, docs/OPENAI_RESPONSES.md, CONTRIBUTING.md, SECURITY.md, [AI #18](https://github.com/flamoris-jp/flamoris-ai/issues/18) and [local #10](https://github.com/flamoris-jp/flamoris-intelligence-mcp/issues/10).

The user has authorized architecture implementation. The reusable non-MCP provider namespace and external facade may be changed within that scope. Do not perform live provider calls, deployment or credential changes without operational authorization. Generation Controller implementation remains deferred.

## Authority

External path: ChatGPT -> MCP Hub -> Intelligence MCP -> the approved internal capability. Internal Studio, Agent and AI Runtime calls do not use MCP as their service dependency in the target design. Existing implementation/callers are not already migrated merely because these docs changed.

Keep external tool schemas, transport validation, provider-neutral request/result mapping, model/capability projections and bounded diagnostics here. Provider adapters and bounds live in `flamoris_intelligence`; the optional facade owns MCP mapping only. Read docs/INTERNAL_EXECUTION.md for the shared direct contract. Do not delete valid external provider behavior solely to remove internal clients, or copy it into every caller by default.

Do not own durable Agent conversations/personality/memory/policy, generation jobs/inputs/assets, product documents, host runtime switching or generic shared infrastructure. Agent is optional personality, not an obligatory raw-inference layer. Generation MCP and Intelligence MCP are parallel external facades, not an internal bus.

## Terminology and truthful documentation

Use ExecuteFlow for Runtime inference flow, preserve ExecutionPlan for its compiled representation, and use ComfyWorkFlow only for ComfyUI graphs/JSON. Avoid bare Workflow as a new FLAMORIS architecture term. Preserve real code/API/configuration/path spelling in current-implementation references. Do not introduce unimplemented environment variables or claim old clients were removed by a documentation PR.

## Provider design and privacy

Keep vendor/model details behind narrow adapters and expose provider-specific capabilities explicitly when a common contract cannot represent them. Do not add speculative frameworks, automatic provider selection, hidden fallback or task loops outside the reviewed tool contract.

Bound input/context/output, concurrent requests, time, retries, filesystem/network access and resources. Preserve fixed safe errors and metadata. Cancellation/disconnect does not prove remote work stopped or was not billed. Do not replay uncertain inference.

Credentials remain operator configuration. Never commit/log/return keys, tokens, passwords, cookies, private keys or deployment identifiers. Prompts, code and context may be private; remote data flow must be explicit. Responses are untrusted and grant no paths, commands or execution permissions. No hidden durable conversation storage or silent export of local-only history.

## Integration

Agent retains identity, principal/session, conversation and export authorization. Any future external Agent capability must use an explicit internal contract without absorbing Agent state. Products retain editing/document authority. Host lifecycle stays in GPU Node Manager. Reuse appropriate Commons foundations without creating reverse dependencies or duplicating domain authority.

## Change and test discipline

Read actual current source/tests and owning Issues before any later cleanup. Inventory internal-only coupling, retained external tools, model identity checks and operational compatibility. Removing unnecessary translation must not remove authorization/provenance checks still needed by the retained contract. A working non-MCP replacement and explicit unavailable behavior must be specified before deleting a currently used path.

Use focused commits, inspect rendered text and diffs, preserve source history and acceptance evidence, and merge only with user authorization. Normal CI uses fake providers without paid APIs, private credentials, GPUs or weights. Test validation, routing, normalization, transport, limits and rejection behavior. Report actual CI separately from live acceptance.

New provider work requires separately scoped verification of its real request/result contract, configuration, limits, cancellation, data flow and licenses. None is started here.

## Licensing and support

Code and documentation are Apache-2.0 unless stated otherwise. Do not add third-party code/models/weights/data/media without compatible documented terms. FLAMORIS offers no guaranteed individual support; documentation, Issues, tests, logs and source are primary references.
