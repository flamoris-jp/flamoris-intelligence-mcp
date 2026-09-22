# Security Policy

## Reporting a vulnerability

Do not post suspected vulnerabilities, credentials, API keys, tokens, private prompts, source code, personal data, or other sensitive information in a public Issue.

Use GitHub private vulnerability reporting when available. Otherwise contact the FLAMORIS maintainers through an appropriate private channel before sharing sensitive details.

Non-sensitive security hardening and design discussion may use normal GitHub Issues.

## Intelligence-gateway security scope

Intelligence MCP may cross trust boundaries between clients, local runtimes, remote providers, code, repositories, tools, and network services.

Treat the following as security-sensitive:

- provider credentials and API keys;
- prompts, source code, files, and context sent to remote providers;
- provider/model routing rules;
- model-generated URLs, commands, paths, patches, and structured outputs;
- MCP transport exposure and authentication;
- tunnel/reverse-proxy configuration;
- filesystem and network access;
- coding-agent tool permissions;
- resource exhaustion from inference, long contexts, or concurrency;
- retry/cancellation behavior for side-effecting operations;
- logs containing prompts, code, provider responses, or secrets.

Provider and model output is untrusted input. Validate it before using it as control data or passing it to privileged tools.

Do not commit live credentials, private deployment details, model weights, private datasets, or private source material.

## Supported versions

FLAMORIS is developed as an open-source project without a guaranteed support window or security-response SLA.

Security fixes are generally applied to the current maintained codebase.

## Scope

This policy applies to code and documentation maintained by FLAMORIS.

Third-party model providers, models, weights, datasets, SDKs, and hosted services may have separate security, privacy, licensing, and support terms.

---

# セキュリティポリシー

公開Issueへ、脆弱性情報、credential、API key、token、private prompt、非公開source code、個人情報などを投稿しないでください。

Intelligence MCPはclient、local runtime、remote provider、code、repository、tool、network serviceの間をまたぐ可能性があるため、特に以下をsecurity-sensitiveとして扱います。

- provider credential / API key
- remote providerへ送信するprompt / source / file / context
- model/provider routing
- AIが生成したURL / command / path / patch / structured output
- MCP transport exposure / authentication
- tunnel / reverse proxy設定
- filesystem / network access
- coding-agent tool permission
- inference / long context / concurrencyによるresource exhaustion
- side effectを持つ操作のretry / cancellation
- prompt / source / provider response / secretを含むlog

Providerやmodelのoutputは信頼済み入力として扱わず、control dataやprivileged toolへ渡す前に検証してください。
