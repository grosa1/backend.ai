#! /bin/bash

set -e
docker run -v ~/mono-repo/backend.ai/agent.toml:/agent/agent.toml -v /var/run/docker.sock:/var/run/docker.sock -it d5d8d953f17d python -m ai.backend.agent.server

