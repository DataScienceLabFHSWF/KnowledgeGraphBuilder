#!/bin/sh
# Entrypoint for SHACL2FOL Docker image
# - prints environment info
# - optionally runs a smoke check if argument 'smoke' is given

printf "SHACL2FOL container starting...\n"
printf "Vampire: "
if command -v vampire >/dev/null 2>&1; then
  vampire --version 2>&1 | head -n1 || true
else
  printf "(vampire not found)\n"
fi

printf "SHACL2FOL JAR: "
if [ -f /opt/shacl2fol/SHACL2FOL.jar ]; then
  ls -lh /opt/shacl2fol/SHACL2FOL.jar
else
  printf "(SHACL2FOL.jar not present)\n"
fi

if [ "$1" = "smoke" ]; then
  echo "Smoke prerequisites:"
  printf "  - vampire: %s\n" "$(if command -v vampire >/dev/null 2>&1; then echo ok; else echo missing; fi)"
  printf "  - SHACL2FOL.jar: %s\n" "$(if [ -f /opt/shacl2fol/SHACL2FOL.jar ]; then echo ok; else echo missing; fi)"
  exit 0
fi

exec "$@"
