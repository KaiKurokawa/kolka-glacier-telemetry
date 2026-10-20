#!/usr/bin/env bash
#
# Первый запуск проекта на машине БЕЗ доступа к Docker Hub.
# Загружает заранее сохранённые образы из ./docker/data и поднимает стек.
# Идемпотентен: можно запускать повторно, образы просто перезапишутся.
#
# Использование:
#   ./first_run.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---------------------------------------------------------------------------
# Оформление вывода
# ---------------------------------------------------------------------------
readonly RED='\033[0;31m' GREEN='\033[0;32m' YELLOW='\033[1;33m' BLUE='\033[0;34m' NC='\033[0m'
log_step() { printf "\n${BLUE}▶ %s${NC}\n" "$1"; }
log_ok()   { printf "${GREEN}✔ %s${NC}\n" "$1"; }
log_warn() { printf "${YELLOW}⚠ %s${NC}\n" "$1"; }
log_err()  { printf "${RED}✖ %s${NC}\n" "$1" >&2; }
log_info() { printf "  %s\n" "$1"; }

require_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        log_err "Docker не найден в PATH."
        exit 1
    fi
    if ! docker compose version >/dev/null 2>&1; then
        log_err "Нет команды 'docker compose' (v2). Установлен только старый docker-compose (v1)."
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Пути
# ---------------------------------------------------------------------------
readonly LOAD_SCRIPT="$SCRIPT_DIR/docker/load_images.sh"
readonly IMAGES_DIR="$SCRIPT_DIR/docker/data"

# ---------------------------------------------------------------------------
# Валидация
# ---------------------------------------------------------------------------
log_step "Проверка окружения"
require_docker
log_ok "Docker и docker compose доступны"

if [[ ! -f "$LOAD_SCRIPT" ]]; then
    log_err "Скрипт загрузки образов не найден: $LOAD_SCRIPT"
    exit 1
fi

if [[ ! -d "$IMAGES_DIR" ]]; then
    log_err "Каталог с образами не найден: $IMAGES_DIR"
    log_info "Скопируй сюда bundle с машины, где запускался save_docker_images.sh."
    exit 1
fi

if ! compgen -G "$IMAGES_DIR/*.tar*" >/dev/null 2>&1; then
    log_err "В $IMAGES_DIR нет ни одного .tar / .tar.gz файла."
    exit 1
fi

log_ok "Файлы образов на месте: $(find "$IMAGES_DIR" -maxdepth 1 -name '*.tar*' | wc -l) шт."

# ---------------------------------------------------------------------------
# Загрузка образов
# ---------------------------------------------------------------------------
log_step "Загрузка Docker-образов из $IMAGES_DIR"
# Вызываем через bash явно — права на исполнение вложенному скрипту не обязательны.
bash "$LOAD_SCRIPT" "$IMAGES_DIR"

# ---------------------------------------------------------------------------
# Подъём стека
# ---------------------------------------------------------------------------
log_step "Запуск docker compose"
docker compose up -d

log_step "Текущий статус контейнеров"
docker compose ps

log_step "Создание общей сети"
docker network create  proxy

printf "\n${GREEN}✔ Проект поднят.${NC}\n"
printf "  Логи в реальном времени:  ${BLUE}docker compose logs -f${NC}\n"
printf "  Логи конкретного сервиса: ${BLUE}docker compose logs -f interface${NC}\n"
