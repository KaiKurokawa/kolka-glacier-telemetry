#!/usr/bin/env bash
#
# ПОЛНЫЙ СБРОС ПРОЕКТА.
# Останавливает стек и УДАЛЯЕТ ВСЕ ДАННЫЕ: том postgres, том объектного
# хранилища, сети и контейнеры. ВОССТАНОВЛЕНИЕ НЕВОЗМОЖНО.
#
# Использование:
#   ./reset.sh          # с интерактивным подтверждением
#   ./reset.sh --yes    # без подтверждения (для CI / автоматизации)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

readonly RED='\033[0;31m' GREEN='\033[0;32m' YELLOW='\033[1;33m' NC='\033[0m'
log_step() { printf "\n${BLUE}▶ %s${NC}\n" "$1"; }
log_ok()   { printf "${GREEN}✔ %s${NC}\n" "$1"; }
log_warn() { printf "${YELLOW}⚠ %s${NC}\n" "$1"; }
log_err()  { printf "${RED}✖ %s${NC}\n" "$1" >&2; }

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
    log_err "Требуется Docker с плагином compose v2."
    exit 1
fi

# Подтверждение, если не передан --yes
if [[ "${1:-}" != "--yes" && "${1:-}" != "-y" ]]; then
    log_warn "ЭТА КОМАНДА БЕЗВОЗВРАТНО УДАЛИТ ВСЕ ДАННЫЕ ПРОЕКТА."
    log_warn "(записи телеметрии, фотографии в объектном хранилище, настройки)"
    # || true — чтобы Ctrl+D / EOF не ронял скрипт под set -e
    read -r -p "Введите YES для продолжения: " answer || true
    if [[ "$answer" != "YES" ]]; then
        log_ok "Отменено. Ничего не удалено."
        exit 0
    fi
fi

log_step "Остановка и удаление контейнеров, сетей и ТОМОВ"
docker compose down --remove-orphans --volumes

log_ok "Данные удалены."
printf "\n  Для подъёма с нуля:  ${BLUE}./first_run.sh${NC}  или  ${BLUE}docker compose up -d${NC}\n"
