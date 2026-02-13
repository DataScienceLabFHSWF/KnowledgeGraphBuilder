#!/bin/sh
# Helper to build & run SHACL2FOL container locally.
# Usage:
#  ./scripts/docker/run_shacl2fol_container.sh --vampire-url <VAMPIRE_TAR_GZ_URL> --shacl2fol-jar <JAR_URL>

set -euo pipefail
VAMPIRE_URL="${1:-}"
SHACL2FOL_JAR_URL="${2:-}"

docker build \
  --file docker/Dockerfile.shacl2fol \
  --build-arg VAMPIRE_RELEASE_URL="$VAMPIRE_URL" \
  --build-arg SHACL2FOL_JAR_URL="$SHACL2FOL_JAR_URL" \
  -t kgbuilder/shacl2fol:local .

# mount project so validator can import kgbuilder
docker run --rm -it \
  -v "$PWD":/opt/project \
  -w /opt/project \
  kgbuilder/shacl2fol:local smoke /bin/sh -c "echo container ready"
