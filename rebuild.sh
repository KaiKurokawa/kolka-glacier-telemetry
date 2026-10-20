#!/usr/bin/env bash
#
# Пересборка образов проекта без кэша и перезапуск стека.
#
# ВАЖНО: ДАННЫЕ НЕ УДАЛЯЮТСЯ. Тома postgres и объектного хранилища
# остаются на месте. Если нужен полный сброс с чистого листа — смотри reset.sh.
#
# Использование:
#   ./rebuild.sh            # пересобрать и поднять, статус в конце
#   ./rebuild.sh --logs     # то же самое + сразу показать логи (Ctrl+C для выхода)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

readonly RED='\033[0;31m' GREEN='\033[0;32m' YELLOW='\033[1;33m' BLUE='\033[0;34m' NC='\033[0m'
log_step() { printf "\n${BLUE}▶ %s${NC}\n" "$1"; }
log_ok()   { printf "${GREEN}✔ %s${NC}\n" "$1"; }
log_err()  { printf "${RED}✖ %s${NC}\n" "$1" >&2; }

usage() {
    cat <<EOF
Использование: $(basename "$0") [--logs] [-h|--help]

  --logs   после запуска сразу показать логи в follow-режиме (Ctrl+C для выхода)
  -h       эта справка

ДАННЫЕ ПРИ ЭТОМ НЕ УДАЛЯЮТСЯ.
EOF
}

SHOW_LOGS=false
for arg in "$@"; do
    case "$arg" in
        --logs)  SHOW_LOGS=true ;;
        -h|--help) usage; exit 0 ;;
        *) log_err "Неизвестный аргумент: $arg"; usage; exit 1 ;;
    esac
done

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
    log_err "Требуется Docker с плагином compose v2."
    exit 1
fi

log_step "Мягкая остановка контейнеров"
docker compose down --remove-orphans

log_step "Пересборка образов без кэша"
docker compose build --no-cache

log_step "Запуск стека"
docker compose up -d

log_step "Статус"
docker compose ps

if [[ "$SHOW_LOGS" == "true" ]]; then
    log_step "Логи (Ctrl+C для выхода)"
    docker compose logs -f
else
    printf "\n${GREEN}✔ Пересобрано и поднято. Данные целы.${NC}\n"
    printf "  Логи: ${BLUE}docker compose logs -f${NC}\n"
fi
