from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import click
import graphene

from ai.backend.common.logging import BraceStyleAdapter, graylog_handler

from ..models.gql import Mutations, Queries

if TYPE_CHECKING:
    from .context import CLIContext

logger = logging.getLogger(__spec__.name)  # type: ignore[name-defined]
logger.addHandler(graylog_handler)
log = BraceStyleAdapter(logger)


@click.group()
def cli(args) -> None:
    pass


@cli.command()
@click.pass_obj
def show(cli_ctx: CLIContext) -> None:
    with cli_ctx.logger:
        schema = graphene.Schema(query=Queries, mutation=Mutations, auto_camelcase=False)
        log.info("======== GraphQL API Schema ========")
        print(str(schema))
