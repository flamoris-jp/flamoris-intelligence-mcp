# AGENTS.md

## Scope

These instructions apply to the entire repository.

This repository is for the FLAMORIS MCP-native intelligence gateway.

**Current status:** Phase 1 implements a Python MCP runtime, configured model/capability discovery, and bounded synchronous llama.cpp inference. See `docs/CONTRACT.md`. Live deployment acceptance is separate from mock/CI validation. Do not describe future providers or downstream integration as implemented.

## Core authority

Intelligence MCP may own:

- provider-neutral intelligence request/result contracts;
- MCP-facing intelligence tools/resources;
- provider adapters;
- provider/model capability metadata;
- routing decisions;
- bounded execution/task metadata needed to fulfill intelligence requests, including limited coordination within a request;
- intelligence-specific health and diagnostics.

Intelligence MCP must not silently become the authority for:

- conversations, persistent memory, Agent prompts, or Agent policy;
- generative-media jobs, workflows, or assets;
- FLAMORIS product documents or editing state;
- generic MCP/logging/security infrastructure that belongs in FLAMORIS Commons.

## Architecture principles

1. **MCP-facing contracts stay provider-neutral where practical**
   - Keep vendor/model/runtime-specific APIs behind adapters.
   - Do not expose raw provider APIs merely because doing so is easier.
   - When a provider-specific capability is intentionally public, name and scope it explicitly.

2. **Do not invent abstractions before providers prove the need**
   - Start from real provider integrations.
   - Prefer a small explicit adapter over a speculative universal framework.
   - Generalize only behavior demonstrated by multiple implementations or clearly required by the public contract.

3. **No Agent-memory ownership**
   - Execution context may be passed into a request.
   - Do not persist conversations, user memory, Agent policy, or knowledge state as hidden side effects.
   - Any caching must be clearly distinguished from durable Agent state.

4. **No media-generation ownership**
   - Image, video, music, and voice generation belongs to `flamoris-generation-mcp`.
   - Do not reproduce Generation MCP's workflow/job/asset authority.

5. **Bounded execution**
   - Bound context/input sizes, outputs, concurrency, timeouts, retries, filesystem access, network access, and resource use.
   - Make cancellation semantics explicit when introduced.
   - Do not automatically retry non-idempotent or side-effecting provider operations after ambiguous failures.

6. **Inspectable routing**
   - Routing should be deterministic where requirements make that possible.
   - Record enough metadata to diagnose provider/model selection without leaking secrets.
   - Avoid hidden fallback chains that make behavior impossible to explain.

7. **Local-first, not local-only**
   - Local models are first-class providers.
   - Remote providers may be supported behind the same explicit boundary.
   - Do not hard-code developer machine names, private hostnames, tunnel IDs, or personal network topology.

8. **Human-authoritative**
   - AI-assisted development is welcome.
   - Humans remain responsible for architecture, security, licensing, compatibility, and release decisions.

## Integration boundaries

### `flamoris-ai-agent`

Owns persistent Agent-facing state such as conversations, memory, knowledge context, prompts, tools, and Agent policy.

Intelligence MCP should accept only the context needed for execution and should not silently retain it as Agent memory.

### `flamoris-generation-mcp`

Owns generative-media and closely related media-analysis execution, workflows, jobs, and assets.

Keep the two MCP surfaces conceptually parallel but domain-separated.

### Product repositories

Products remain authoritative for project/document state and editing behavior.

If Intelligence MCP later exposes coding or product-assistance capabilities, they must interact through explicit product/tool contracts rather than bypass product authority.

### FLAMORIS Commons

Reuse shared MCP/logging/security foundations when an appropriate stable package exists.

Do not duplicate generic infrastructure merely to keep this repository self-contained.

## Provider credentials and privacy

Never commit, log, or return:

- API keys;
- access tokens;
- passwords;
- private keys;
- authentication cookies;
- provider secrets;
- private tunnel/deployment identifiers.

Treat prompts, code, files, repository contents, and tool context as potentially private.

Before sending data to a remote provider, the runtime contract should make that data flow explicit.

Provider responses are untrusted input and must be validated before being used as paths, URLs, commands, tool arguments, or structured control data.

## Development workflow

Before implementing a substantial change:

- read README.md, this file, CONTRIBUTING.md, and SECURITY.md;
- read the relevant Issue/design document;
- inspect `flamoris-ai`, `flamoris-ai-agent`, and `flamoris-generation-mcp` boundaries;
- inspect current code/tests before proposing abstractions;
- identify provider-specific vs provider-neutral responsibilities;
- keep changes scoped to the Issue;
- update public documentation when tools, transports, providers, or behavior change.

For a new provider, document:

- capability mapping;
- credential/configuration requirements;
- request/result normalization;
- cancellation and timeout behavior;
- rate/resource limits;
- privacy/data-flow implications;
- license/terms constraints that affect integration.

## Testing and CI

Normal CI must not require:

- paid provider access;
- live private API keys;
- a live GPU;
- local model weights;
- private source repositories or datasets.

Use fake/mock providers for normal tests.

Add focused tests for validation, routing, provider adapters, error mapping, bounded resources, and rejection paths.

If transport behavior is introduced, test protocol behavior without depending on a personal tunnel or deployment environment.

## Licensing

Unless stated otherwise, code and documentation are licensed under Apache License 2.0.

Do not add third-party code, models, weights, datasets, prompts, media, generated assets, or provider material unless their licenses and redistribution terms are compatible and clearly documented.

## Support

FLAMORIS does not provide guaranteed individual support.

Repository documentation, Issues, tests, logs, and source code are the primary support references. AI-assisted self-support is encouraged.

