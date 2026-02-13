#!/usr/bin/env bash
# Download SHACL2FOL JAR and Vampire theorem prover for local development.
#
# These are NOT vendored in git because they total ~45 MB.
# Run this script once after cloning:
#
#   bash scripts/setup_shacl2fol.sh
#
# Requirements: Java 21+ (openjdk-21-jre-headless), wget or curl.

set -euo pipefail

REPO="https://raw.githubusercontent.com/paolo7/SHACL2FOL/main/runnable"
LIB_DIR="$(cd "$(dirname "$0")/.." && pwd)/lib"

mkdir -p "$LIB_DIR"

echo "==> Downloading SHACL2FOL.jar ..."
if command -v wget &>/dev/null; then
    wget -q -O "$LIB_DIR/SHACL2FOL.jar" "$REPO/SHACL2FOL.jar"
else
    curl -sL -o "$LIB_DIR/SHACL2FOL.jar" "$REPO/SHACL2FOL.jar"
fi

echo "==> Downloading Vampire prover ..."
if command -v wget &>/dev/null; then
    wget -q -O "$LIB_DIR/vampire" "$REPO/vampire"
else
    curl -sL -o "$LIB_DIR/vampire" "$REPO/vampire"
fi
chmod +x "$LIB_DIR/vampire"

echo "==> Verifying Java version ..."
JAVA_VER=$(java -version 2>&1 | head -1)
echo "    $JAVA_VER"

echo "==> Verifying SHACL2FOL ..."
java -jar "$LIB_DIR/SHACL2FOL.jar" 2>&1 | head -3

echo ""
echo "Done. SHACL2FOL is ready at $LIB_DIR/"
echo "  - SHACL2FOL.jar: $(du -sh "$LIB_DIR/SHACL2FOL.jar" | cut -f1)"
echo "  - vampire:       $(du -sh "$LIB_DIR/vampire" | cut -f1)"
