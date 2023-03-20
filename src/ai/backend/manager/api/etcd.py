from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, Iterable, Mapping, Tuple

import aiohttp_cors
import trafaret as t
from aiohttp import web

from ai.backend.common import redis_helper
from ai.backend.common.docker import get_known_registries
from ai.backend.common.logging import BraceStyleAdapter
from ai.backend.common.types import AcceleratorMetadata

from .auth import superadmin_required
from .exceptions import InvalidAPIParameters
from .types import CORSOptions, WebMiddleware
from .utils import check_api_params

if TYPE_CHECKING:
    from .context import RootContext

log = BraceStyleAdapter(logging.getLogger(__spec__.name))  # type: ignore[name-defined]


KNOWN_SLOT_METADATA: Mapping[str, AcceleratorMetadata] = {
    "cpu": {
        "slot_name": "cpu",
        "description": "CPU",
        "human_readable_name": "CPU",
        "display_unit": "Core",
        "number_format": {"binary": False, "round_length": 0},
        "display_icon": "cpu",
    },
    "mem": {
        "slot_name": "ram",
        "description": "Memory",
        "human_readable_name": "RAM",
        "display_unit": "GiB",
        "number_format": {"binary": True, "round_length": 0},
        "display_icon": "cpu",
    },
    "cuda.device": {
        "slot_name": "cuda.device",
        "human_readable_name": "GPU",
        "description": "CUDA-capable GPU",
        "display_unit": "GPU",
        "number_format": {"binary": False, "round_length": 0},
        "display_icon": "gpu1",
    },
    "cuda.shares": {
        "slot_name": "cuda.shares",
        "human_readable_name": "fGPU",
        "description": "CUDA-capable GPU (fractional)",
        "display_unit": "fGPU",
        "number_format": {"binary": False, "round_length": 2},
        "display_icon": "gpu1",
    },
    "rocm.device": {
        "slot_name": "rocm.device",
        "human_readable_name": "GPU",
        "description": "ROCm-capable GPU",
        "display_unit": "GPU",
        "number_format": {"binary": False, "round_length": 0},
        "display_icon": "gpu2",
    },
    "tpu.device": {
        "slot_name": "tpu.device",
        "human_readable_name": "TPU",
        "description": "TPU device",
        "display_unit": "GPU",
        "number_format": {"binary": False, "round_length": 0},
        "display_icon": "tpu",
    },
}


async def get_resource_slots(request: web.Request) -> web.Response:
    log.info("ETCD.GET_RESOURCE_SLOTS ()")
    root_ctx: RootContext = request.app["_root.context"]
    known_slots = await root_ctx.shared_config.get_resource_slots()
    return web.json_response(known_slots, status=200)


async def get_resource_metadata(request: web.Request) -> web.Response:
    log.info("ETCD.GET_RESOURCE_METADATA ()")
    root_ctx: RootContext = request.app["_root.context"]
    accelerator_metadata_jsons: Dict[str, str] = await redis_helper.execute(
        root_ctx.redis_stat,
        lambda r: r.hgetall("computer.metadata"),
        encoding="utf-8",
    )
    accelerator_metadatas: Dict[str, AcceleratorMetadata] = {}
    for slot_name, metadata_json in accelerator_metadata_jsons.items():
        accelerator_metadatas[slot_name] = json.loads(metadata_json)
    for key, value in KNOWN_SLOT_METADATA.items():
        if key not in accelerator_metadatas:
            accelerator_metadatas[key] = value
    return web.json_response(accelerator_metadatas, status=200)


async def get_vfolder_types(request: web.Request) -> web.Response:
    log.info("ETCD.GET_VFOLDER_TYPES ()")
    root_ctx: RootContext = request.app["_root.context"]
    vfolder_types = await root_ctx.shared_config.get_vfolder_types()
    return web.json_response(vfolder_types, status=200)


@superadmin_required
async def get_docker_registries(request: web.Request) -> web.Response:
    """
    Returns the list of all registered docker registries.
    """
    log.info("ETCD.GET_DOCKER_REGISTRIES ()")
    root_ctx: RootContext = request.app["_root.context"]
    _registries = await get_known_registries(root_ctx.shared_config.etcd)
    # ``yarl.URL`` is not JSON-serializable, so we need to represent it as string.
    known_registries: Mapping[str, str] = {k: v.human_repr() for k, v in _registries.items()}
    return web.json_response(known_registries, status=200)


@superadmin_required
@check_api_params(
    t.Dict(
        {
            t.Key("key"): t.String,
            t.Key("prefix", default=False): t.Bool,
        }
    )
)
async def get_config(request: web.Request, params: Any) -> web.Response:
    root_ctx: RootContext = request.app["_root.context"]
    log.info(
        "ETCD.GET_CONFIG (ak:{}, key:{}, prefix:{})",
        request["keypair"]["access_key"],
        params["key"],
        params["prefix"],
    )
    if params["prefix"]:
        # Flatten the returned ChainMap object for JSON serialization
        tree_value = dict(await root_ctx.shared_config.etcd.get_prefix_dict(params["key"]))
        return web.json_response({"result": tree_value})
    else:
        scalar_value = await root_ctx.shared_config.etcd.get(params["key"])
        return web.json_response({"result": scalar_value})


@superadmin_required
@check_api_params(
    t.Dict(
        {
            t.Key("key"): t.String,
            t.Key("value"): (
                t.String(allow_blank=True) | t.Mapping(t.String(allow_blank=True), t.Any)
            ),
        }
    )
)
async def set_config(request: web.Request, params: Any) -> web.Response:
    root_ctx: RootContext = request.app["_root.context"]
    log.info(
        "ETCD.SET_CONFIG (ak:{}, key:{}, val:{})",
        request["keypair"]["access_key"],
        params["key"],
        params["value"],
    )
    if isinstance(params["value"], Mapping):
        updates = {}

        def flatten(prefix, o):
            for k, v in o.items():
                inner_prefix = prefix if k == "" else f"{prefix}/{k}"
                if isinstance(v, Mapping):
                    flatten(inner_prefix, v)
                else:
                    updates[inner_prefix] = v

        flatten(params["key"], params["value"])
        # TODO: chunk support if there are too many keys
        if len(updates) > 16:
            raise InvalidAPIParameters("Too large update! Split into smaller key-value pair sets.")
        await root_ctx.shared_config.etcd.put_dict(updates)
    else:
        await root_ctx.shared_config.etcd.put(params["key"], params["value"])
    return web.json_response({"result": "ok"})


@superadmin_required
@check_api_params(
    t.Dict(
        {
            t.Key("key"): t.String,
            t.Key("prefix", default=False): t.Bool,
        }
    )
)
async def delete_config(request: web.Request, params: Any) -> web.Response:
    root_ctx: RootContext = request.app["_root.context"]
    log.info(
        "ETCD.DELETE_CONFIG (ak:{}, key:{}, prefix:{})",
        request["keypair"]["access_key"],
        params["key"],
        params["prefix"],
    )
    if params["prefix"]:
        await root_ctx.shared_config.etcd.delete_prefix(params["key"])
    else:
        await root_ctx.shared_config.etcd.delete(params["key"])
    return web.json_response({"result": "ok"})


async def app_ctx(app: web.Application) -> AsyncGenerator[None, None]:
    root_ctx: RootContext = app["_root.context"]
    if root_ctx.pidx == 0:
        await root_ctx.shared_config.register_myself()
    yield
    if root_ctx.pidx == 0:
        await root_ctx.shared_config.deregister_myself()


def create_app(
    default_cors_options: CORSOptions,
) -> Tuple[web.Application, Iterable[WebMiddleware]]:
    app = web.Application()
    app.cleanup_ctx.append(app_ctx)
    app["prefix"] = "config"
    app["api_versions"] = (3, 4)
    cors = aiohttp_cors.setup(app, defaults=default_cors_options)
    cors.add(app.router.add_route("GET", r"/resource-slots", get_resource_slots))
    cors.add(app.router.add_route("GET", r"/resource-slots/details", get_resource_metadata))
    cors.add(app.router.add_route("GET", r"/vfolder-types", get_vfolder_types))
    cors.add(app.router.add_route("GET", r"/docker-registries", get_docker_registries))
    cors.add(app.router.add_route("POST", r"/get", get_config))
    cors.add(app.router.add_route("POST", r"/set", set_config))
    cors.add(app.router.add_route("POST", r"/delete", delete_config))
    return app, []
