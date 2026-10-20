#!/usr/bin/env bash
#
# Сохранение Docker-образов проекта в ./docker/data для офлайн-переноса.
#
# ПЕРЕД ЗАПУСКОМ убедись, что кастомные образы собраны, а публичные скачаны:
#   docker compose build interface ingestor
#
# Использование:
#   ./save_docker_images.sh            # сохранить то, что есть локально (+ докачать отсутствующие)
#   ./save_docker_images.sh --force    # форсировать docker pull перед сохранением
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

readonly RED='\033[0;31m' GREEN='\033[0;32m' YELLOW='\033[1;33m' BLUE='\033[0;34m' NC='\033[0m'
log_step() { printf "\n${BLUE}▶ %s${NC}\n" "$1"; }
log_ok()   { printf "${GREEN}✔ %s${NC}\n" "$1"; }
log_warn() { printf "${YELLOW}⚠ %s${NC}\n" "$1"; }
log_err()  { printf "${RED}✖ %s${NC}\n" "$1" >&2; }
log_info() { printf "  %s\n" "$1"; }   # <-- вот эту я забыл в прошлый раз

usage() {
    cat <<EOF
Использование: $(basename "$0") [--force] [-h|--help]

  --force   всегда делать docker pull перед сохранением (обновить теги)
  -h        эта справка

Список образов: docker/docker_images.txt
Куда сохраняем: docker/data/
EOF
}

FORCE_PULL="false"
for arg in "$@"; do
    case "$arg" in
        --force)   FORCE_PULL="true" ;;
        -h|--help) usage; exit 0 ;;
        *) log_err "Неизвестный аргумент: $arg"; usage; exit 1 ;;
    esac
done

readonly SAVE_SCRIPT="$SCRIPT_DIR/docker/save_images.sh"
readonly LIST_FILE="$SCRIPT_DIR/docker/docker_images.txt"
readonly OUT_DIR="$SCRIPT_DIR/docker/data"

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
    log_err "Требуется Docker с плагином compose v2."
    exit 1
fi

[[ -f "$SAVE_SCRIPT" ]] || { log_err "Не найден $SAVE_SCRIPT"; exit 1; }
[[ -f "$LIST_FILE"  ]] || { log_err "Не найден $LIST_FILE";  exit 1; }

log_step "Сохранение образов (FORCE_PULL=$FORCE_PULL)"
log_info "Список:  $LIST_FILE"
log_info "Каталог: $OUT_DIR"

# Передаём FORCE_PULL через окружение, чтобы не править сам save_images.sh
FORCE_PULL="$FORCE_PULL" bash "$SAVE_SCRIPT" "$LIST_FILE" "$OUT_DIR"

log_step "Итог по каталогу"
du -sh "$OUT_DIR" 2>/dev/null || true
ls -lh "$OUT_DIR"

printf "\n${GREEN}✔ Bundle готов.${NC}\n"
printf "  Забери каталог ${BLUE}%s${NC} на целевую машину (scp / rsync / флешка).\n" "$OUT_DIR"
