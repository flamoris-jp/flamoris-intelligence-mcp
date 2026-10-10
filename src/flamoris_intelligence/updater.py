"""Intelligence configuration validation without invoking a provider."""

from flamoris_update_core.domain import check_resources, configuration_revision
from flamoris_update_core.owner import ApplicationOwner, DomainState
from flamoris_update_core.owner_cli import serve

from .config import Settings

SCHEMAS = {"configuration": "intelligence-config-1"}


def inspect_domain(config, resources):
    check_resources(resources, ["configuration"])
    Settings.from_env()
    return DomainState(
        schemas=SCHEMAS,
        active_work=False,
        unknown_work=False,
        configuration_digest=configuration_revision(resources),
    )


def factory(config):
    return ApplicationOwner(config, "flamoris-intelligence-mcp", "1.0.1", inspect_domain)


def main():
    serve(factory)
