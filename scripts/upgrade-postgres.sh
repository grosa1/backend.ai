#! /bin/bash
set -euo pipefail
shopt -s xpg_echo

# NOTE: this script should be executed from the repository root.

# Color constants
GREEN="\033[0;92m"
CYAN="\033[0;96m"
WHITE="\033[0;97m"
NC="\033[0m"

function join_by { local IFS="$1"; shift; echo "$*"; }

HALFSTACK_VOLUME_PATH="$(pwd)/volumes"
DOCKER_COMPOSE_CURRENT="docker-compose.halfstack.current.yml"
DOCKER_COMPOSE_MAIN="docker-compose.halfstack-main.yml"

echo "${CYAN}▪ [halfstack]${WHITE} Environment${NC}"
echo " - HALFSTACK_VOLUME_PATH = ${HALFSTACK_VOLUME_PATH}"
echo " - DOCKER_COMPOSE_CURRENT = ${DOCKER_COMPOSE_CURRENT} (will be used as the source of configurations)"
echo " - DOCKER_COMPOSE_MAIN = ${DOCKER_COMPOSE_MAIN} (will be used as the template for the new halfstack)"
echo
echo -n "${WHITE}Do you want to proceed? [Y/n]${NC} "; read -n 1 -r
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  exit 1
fi
echo

# NOTE: etcd and redis does not require explicit migration procedures.

POSTGRES_CONTAINER=$(docker compose -f ${DOCKER_COMPOSE_CURRENT} ps -q "backendai-half-db")
POSTGRES_OLD_VERSION=$(cat "${DOCKER_COMPOSE_CURRENT}" | yq '.services."backendai-half-db".image')
POSTGRES_NEW_VERSION=$(cat "${DOCKER_COMPOSE_MAIN}" | yq '.services."backendai-half-db".image')
if [ "$POSTGRES_OLD_VERSION" == "$POSTGRES_NEW_VERSION" ]; then
  echo "${GREEN}✓ [postgres]${WHITE} The postgres container version has not been changed. Skipping upgrade.${NC}"
else
  echo "${CYAN}▪ [postgres]${WHITE} Upgrading postgres from ${POSTGRES_OLD_VERSION} ($(echo ${POSTGRES_CONTAINER} | cut -b -12)) to ${POSTGRES_NEW_VERSION}"

  echo "${CYAN}▪ [postgres]${WHITE} Making the database dump at ${HALFSTACK_VOLUME_PATH}/postgres-data.old/upgrade-dump.sql ...${NC}"
  docker exec -it ${POSTGRES_CONTAINER} sh -c 'pg_dumpall --tablespaces-only -U postgres > /var/lib/postgresql/data/upgrade-dump.sql'

  echo "${CYAN}▪ [halfstack]${WHITE} Stopping the current halfstack ...${NC}"
  docker compose -f "${DOCKER_COMPOSE_CURRENT}" down
  echo "${CYAN}▪ [postgres]${WHITE} Migrating the database to the new version of postgres ...${NC}"
  sudo mv "${HALFSTACK_VOLUME_PATH}/postgres-data" "${HALFSTACK_VOLUME_PATH}/postgres-data.old"
  sudo mkdir -p "${HALFSTACK_VOLUME_PATH}/postgres-data"
  sudo docker pull "${POSTGRES_NEW_VERSION}"
  current_db_envs=($(cat ${DOCKER_COMPOSE_CURRENT} | yq '.services."backendai-half-db".environment.[]'))
  TEMP_CID=$(sudo docker run -d \
    -v ${HALFSTACK_VOLUME_PATH}/postgres-data.old:/data.old \
    -v ${HALFSTACK_VOLUME_PATH}/postgres-data:/var/lib/postgresql/data \
    $(join_by ' ' ${current_db_envs[@]/#/-e }) \
    "${POSTGRES_NEW_VERSION}")
  while :
  do
    { sudo docker exec -it ${TEMP_CID} sh -c 'pg_isready -U postgres >/dev/null 2>&1'; rc=$?; } || :
    if [ $rc -eq 0 ]; then break; fi
    sleep 0.5
  done
  sudo docker exec -it ${TEMP_CID} sh -c 'psql -U postgres -f /data.old/upgrade-dump.sql >/dev/null'
  sudo docker stop ${TEMP_CID} && sudo docker rm ${TEMP_CID}
fi

echo "${CYAN}▪ [halfstack]${WHITE} Recreating the docker compose stack ...${NC}"
cp "${DOCKER_COMPOSE_CURRENT}" "${DOCKER_COMPOSE_CURRENT}.backup"
# assuming that each port config has only one line...
postgres_ports=$(cat "${DOCKER_COMPOSE_CURRENT}" | yq '.services."backendai-half-db".ports.[]')
redis_ports=$(cat "${DOCKER_COMPOSE_CURRENT}" | yq '.services."backendai-half-redis".ports.[]')
etcd_ports=$(cat "${DOCKER_COMPOSE_CURRENT}" | yq '.services."backendai-half-etcd".ports.[]')
cp "${DOCKER_COMPOSE_MAIN}" "${DOCKER_COMPOSE_CURRENT}"
yq -i '.services."backendai-half-db".ports = [''"'"$postgres_ports"'"]' ${DOCKER_COMPOSE_CURRENT}
yq -i '.services."backendai-half-redis".ports = [''"'"$redis_ports"'"]' ${DOCKER_COMPOSE_CURRENT}
yq -i '.services."backendai-half-etcd".ports = [''"'"$etcd_ports"'"]' ${DOCKER_COMPOSE_CURRENT}
docker compose -f "${DOCKER_COMPOSE_CURRENT}" up -d

echo "${GREEN}✓ [halfstack]${WHITE} Completed upgrade.${NC}"
