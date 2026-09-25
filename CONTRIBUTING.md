# Contributing to FLAMORIS Intelligence MCP

Thank you for your interest in FLAMORIS.

This repository is intended to provide the MCP-native, provider-neutral intelligence boundary for FLAMORIS.

## Before contributing

Issues are welcome from everyone. Pull requests are accepted only from repository collaborators. Please open an Issue to propose documentation fixes or implementation changes.

Please open an Issue first for substantial changes involving:

- new providers;
- new public MCP tools or resources;
- routing or orchestration behavior;
- transport or authentication;
- persistence;
- cross-repository authority changes;
- externally visible compatibility changes.

Before adding a feature, confirm that it belongs in Intelligence MCP rather than `flamoris-ai-agent`, `flamoris-generation-mcp`, a product repository, or FLAMORIS Commons.

## Pull requests

Please:

- keep changes focused;
- keep provider-specific behavior behind adapters;
- identify privacy/data-flow impact;
- include tests where practical;
- preserve public behavior unless intentionally changed;
- avoid unnecessary dependencies;
- distinguish implemented behavior from future plans.

AI-assisted contributions are welcome. Contributors remain responsible for reviewing, testing, licensing, and understanding submitted changes.

## Licensing

Unless explicitly stated otherwise, code and documentation contributions are submitted under Apache License 2.0.

Do not add third-party models, weights, datasets, prompts, provider assets, media, or generated outputs without documenting applicable licenses and redistribution terms.

## Support

FLAMORIS does not provide guaranteed individual support.

Use repository documentation, Issues, tests, logs, and source code as primary references. AI-assisted self-support is encouraged.

---

# FLAMORIS Intelligence MCP へのコントリビューション

FLAMORISに興味を持っていただきありがとうございます。

Issueはどなたでも歓迎します。Pull Requestはリポジトリのcollaboratorのみ受け付けています。修正、機能、ドキュメント変更などの提案はIssueからお願いします。

このリポジトリは、FLAMORISのLLM、推論、Coding AIなどをMCPから扱うprovider-neutralな境界を担当する予定です。

新provider、公開MCP tool/resource、routing、transport、authentication、永続化、複数リポジトリのauthorityに影響する変更は、実装前にIssueで整理してください。

機能を追加する前に、`flamoris-ai-agent`、`flamoris-generation-mcp`、各制作アプリ、FLAMORIS Commonsのどこへ置くべきか確認してください。

コードとドキュメントは、明記がない限りApache License 2.0です。第三者model、weights、dataset、prompt、provider asset、生成outputなどには別の条件が適用される場合があるため、必ず確認・明記してください。
