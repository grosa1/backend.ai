import ctypes
import ctypes.util
import logging
import os
import sys
from typing import Iterator

import aiohttp
import aiotools

from ai.backend.common.cgroup import get_cgroup_mount_point
from ai.backend.common.docker import get_docker_connector
from ai.backend.common.logging import BraceStyleAdapter

logger = logging.getLogger(__spec__.name)  # type: ignore[name-defined]
log = BraceStyleAdapter(logger)
_numa_supported = False

if sys.platform == "linux":
    _libnuma_path = ctypes.util.find_library("numa")
    if _libnuma_path:
        _libnuma = ctypes.CDLL(_libnuma_path)
        _numa_supported = True


def get_cpus() -> set[int]:
    cpu_count = os.cpu_count()
    if cpu_count is None:
        return {0}
    return {idx for idx in range(cpu_count)}


def parse_cpuset(value: str) -> Iterator[int]:
    if not value:
        raise ValueError("empty cpuset value")
    ranges = value.split(",")
    for r in ranges:
        begin, _, end = r.partition("-")
        if end:
            begin_value = int(begin)
            end_value = int(end)
            if begin_value > end_value:
                raise ValueError(f"invalid range in cpuset: {begin}-{end}")
            yield from range(int(begin), int(end) + 1)
        else:
            yield int(begin)


class libnuma:
    @staticmethod
    def node_of_cpu(core) -> int:
        if _numa_supported:
            return int(_libnuma.numa_node_of_cpu(core))  # type: ignore
        else:
            return 0

    @staticmethod
    def num_nodes() -> int:
        if _numa_supported:
            return int(_libnuma.numa_num_configured_nodes())  # type: ignore
        else:
            return 1

    @staticmethod
    @aiotools.lru_cache(maxsize=1)
    async def get_available_cores() -> set[int]:
        cpuset_source = "the system cpu count"
        try:
            match sys.platform:
                case "linux":
                    try:
                        docker_host, connector = get_docker_connector()
                        async with aiohttp.ClientSession(connector=connector) as sess:
                            async with sess.get(docker_host / "info") as resp:
                                data = await resp.json()
                    except (RuntimeError, aiohttp.ClientError):
                        pass
                    else:
                        # Assume cgroup v1 if CgroupVersion key is absent
                        if "CgroupVersion" not in data:
                            data["CgroupVersion"] = "1"
                        try:
                            driver = data["CgroupDriver"]
                            version = data["CgroupVersion"]
                            mount_point = get_cgroup_mount_point(version, "cpuset")

                            match driver:
                                case "cgroupfs":
                                    cgroup_parent = "docker"
                                case "systemd":
                                    cgroup_parent = "system.slice"

                            match version:
                                case "1":
                                    cpuset_source_name = "cpuset.effective_cpus"
                                case "2":
                                    cpuset_source_name = "cpuset.cpus.effective"

                            docker_cpuset_path = mount_point / cgroup_parent / cpuset_source_name
                            log.debug(f"docker_cpuset_path: {docker_cpuset_path}")
                            cpuset_source = "the docker cgroup (v{})".format(version)
                        except RuntimeError:
                            pass  # couldn't find the cgroup mount point. try alternatives.
                    try:
                        docker_cpuset = docker_cpuset_path.read_text()
                        cpuset = {*parse_cpuset(docker_cpuset)}
                        return cpuset
                    except (IOError, ValueError):
                        try:
                            cpuset = os.sched_getaffinity(0)  # type: ignore
                            cpuset_source = "the scheduler affinity mask of the agent process"
                            return cpuset
                        except AttributeError:
                            return get_cpus()
                case "darwin" | "win32":
                    try:
                        docker_host, connector = get_docker_connector()
                        async with aiohttp.ClientSession(connector=connector) as sess:
                            async with sess.get(docker_host / "info") as resp:
                                data = await resp.json()
                                return {idx for idx in range(data["NCPU"])}
                    except (RuntimeError, aiohttp.ClientError):
                        return get_cpus()
                case _:
                    return get_cpus()
        finally:
            log.debug("read the available cpuset from {}", cpuset_source)

    @staticmethod
    async def get_core_topology(limit_cpus=None) -> tuple[list[int], ...]:
        topo: tuple[list[int], ...] = tuple([] for _ in range(libnuma.num_nodes()))
        for c in await libnuma.get_available_cores():
            if limit_cpus is not None and c not in limit_cpus:
                continue
            n = libnuma.node_of_cpu(c)
            topo[n].append(c)
        return topo
