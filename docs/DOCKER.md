# Docker deployment

This image runs **Intelligence MCP only**. It contains no llama.cpp, weights, GPU
libraries, Agent state, media assets, or runtime activation logic. LIME Manager
remains the authority for the independently managed LLM runtime.

## Networking decision

The supported Compose example targets **Linux Docker Engine with host networking**.
The existing CLI/Settings restriction to `127.0.0.1` or `::1` is unchanged. Bridge
networking with published ports cannot reach a process listening only on the
container's loopback. Broadening the application bind is unnecessary for this
deployment, so `0.0.0.0`, `::`, and arbitrary hostnames remain rejected.

With `network_mode: host`, the MCP listener and configured provider loopback URL
use the host network namespace. There are deliberately no `ports`, `extra_hosts`,
model mounts, Docker socket mounts, or privileged mode. `host.docker.internal` is
not required. Docker Desktop/Windows/macOS and bridge-mode deployment are not
covered by this example; do not assume `-p` makes them equivalent.

Host networking sacrifices container network isolation: this process can reach
host services. Keep the host trusted. Every local OS user/process that can reach
the listener can invoke inference; loopback and SDK Host/Origin checks are **not
client authentication**. An external Hub must connect through a separately managed
authenticated proxy/tunnel on the host. A trusted local client or host-networked
container can use loopback directly; an ordinary bridge container cannot. The
proxy must supply a permitted upstream loopback Host and enforce caller access
before forwarding; do not disable SDK checks to pass arbitrary external Host or
Origin headers. This Issue does not install/configure that proxy or Hub.

## Build and start

From the checked-out repository root on the Linux deployment host:

```sh
cp .env.example .env
chmod 600 .env
# Edit .env for your provider URL, served model alias, limits, and free local port.
docker compose config --quiet
docker compose build
docker compose up -d --wait --wait-timeout 90
docker compose ps
```

Use an account authorized to operate Docker. Preserve an existing `.env` when
updating. Compose reads the file via `env_file`; the package itself does not load
dotenv files. Do not paste resolved Compose configuration or container environment
inspection into public reports: they may contain the optional provider credential.

All application settings use the existing `FLAMORIS_INTELLIGENCE_*` names:

| Settings | Deployment use |
| --- | --- |
| `TRANSPORT` | Image CMD explicitly selects `streamable-http`; outside Docker the package defaults to stdio |
| `HTTP_HOST`, `HTTP_PORT`, `MCP_PATH` | Loopback listener; defaults `127.0.0.1`, `8767`, `/mcp` |
| `PROVIDER_URL` | Operator-controlled llama.cpp base URL, no `/v1` suffix; host loopback works in this network mode |
| `PROVIDER_API_KEY` | Optional provider bearer credential; does not authenticate MCP clients |
| `MODELS` | JSON array of public IDs, served aliases, context/output budgets |
| `TIMEOUT_SECONDS`, `HEALTH_TIMEOUT_SECONDS` | Inference/provider-health deadlines; defaults 120/5 seconds |
| `MAX_INPUT_BYTES`, `MAX_RESPONSE_BYTES`, `MAX_OUTPUT_BYTES` | Defaults 65536/1048576/262144 bytes |
| `MAX_CONCURRENCY` | Default 1 in-flight inference per process; overflow returns `busy` |

The full bounds and model example are in [README](../README.md#configuration).
CLI flags still override environment values. Use environment settings for container
host/port/path changes so the server and healthcheck read the same configuration;
overriding only the server command's port/path would leave healthcheck on the old
address. The optional provider credential is forwarded exactly as in package use.
Provider redirects, environment proxies, and automatic inference retries remain
disabled; callers cannot supply endpoints.

The multi-stage build creates wheels, then installs from the wheel directory
offline into Python 3.12 slim. `docker-requirements.txt` pins the runtime dependency
resolution independently of the package's compatible ranges. To intentionally
refresh it, run the `uv pip compile` command in its header and rerun CI. The Python
base tag and build tooling are not digest-locked; retain the reviewed built image
digest for exact deployment rollback. No development extras or editable install
are used in the final image. The allowlisted build context excludes `.env`, Git
metadata, models, and local state.

The image runs as UID/GID 10001. Compose makes its filesystem read-only, drops
capabilities, prevents privilege escalation, and bounds memory/CPU/process count.
No writable volumes are needed. The service uses one process; multiple containers
or workers do **not** share admission state. Do not scale replicas as a way to
manage GPU capacity. Host networking also prevents two instances using one port.

## Health and diagnostics

```sh
docker compose exec -T intelligence-mcp python -m flamoris_intelligence_mcp.healthcheck
docker compose logs --tail 100 intelligence-mcp
```

The healthcheck negotiates MCP over the configured local HTTP path and reads the
tool catalog, checking for Intelligence tools. It has a two-second operation
deadline and a five-second Docker process timeout. It uses neither proxy
environment variables nor redirects. Success is exit 0; failure is exit 1 with a
fixed message. It never calls provider health, inference, or runtime activation.
Thus stopped, sleeping, unhealthy, or authentication-failing providers do not
make a responsive MCP container unhealthy. It does not consume inference capacity.

Use `system.health` for the separate bounded provider status, and an explicit
inference smoke for real model acceptance. Docker's `healthy` is not proof of model
readiness. A wrong MCP path, stopped listener, stalled transport, or unrelated MCP
catalog fails the healthcheck. Docker health status alone does not restart an
unhealthy process; the restart policy covers process exits.

## Live LIME acceptance after merge/deployment

Do not infer live readiness from CI or an old setup document. The operator should
use LIME Manager to activate `llm` and confirm the current llama.cpp runtime is
READY. This container never calls systemd or performs activation.

After starting the container, install this repository's package in a separate
smoke-client virtual environment (no GPU needed), then from the repository root:

```sh
python examples/smoke.py --url http://127.0.0.1:8767/mcp --model gpt-oss-20b
docker compose restart intelligence-mcp
docker compose up -d --wait --wait-timeout 90
python examples/smoke.py --url http://127.0.0.1:8767/mcp --model gpt-oss-20b
```

Substitute the configured local port/path and public model ID. The script calls
`system.health`, `models.list`, `capabilities.list`, then `inference.execute` with a
harmless fixed greeting prompt and 256-token maximum. Confirm an actual GPT-OSS
answer both before and after restart. A `length` response can be empty when the
reasoning budget is exhausted; a transport success alone is not that acceptance.
If needed, inspect the runtime configuration with its owner rather than expanding
this MCP's authority. `--discovery-only` skips inference for offline diagnostics
and CI; it cannot satisfy real GPT-OSS acceptance.

Record only commit/image identifier, public model ID, process/provider health,
success, finish reason, elapsed time, and token usage in Issue #3. Exclude private
addresses, credentials, model paths, and prompt/response contents. Confirm runtime
ownership remains with LIME Manager. Close #3 only after this live acceptance;
Docker/mock CI does not perform it.

For an update, review the new source, rebuild, and use `docker compose up -d --wait`.
For rollback, retain/tag the prior image and use `docker compose up -d --no-build`
with that image configured. `docker compose down` stops/removes this gateway; it
does not stop the managed provider or delete any model/Agent/media data.
