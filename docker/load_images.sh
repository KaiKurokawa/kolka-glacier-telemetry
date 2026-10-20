#!/usr/bin/env bash
#
# Загружает Docker-образы из каталога с .tar/.tar.gz архивами.
#
# Использование:
#   ./load.sh [images_dir]
#
set -euo pipefail

IN_DIR="${1:-images}"

if [[ ! -d "$IN_DIR" ]]; then
    echo "❌ Каталог не найден: $IN_DIR"
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "❌ Docker не найден в PATH"
    exit 1
fi

# Проверка целостности, если есть checksums.sha256
if [[ -f "$IN_DIR/checksums.sha256" ]] && command -v sha256sum >/dev/null 2>&1; then
    echo "🔐 Проверяю контрольные суммы..."
    if (cd "$IN_DIR" && sha256sum -c checksums.sha256); then
        echo "   ✅ Все архивы целы"
    else
        echo "   ❌ Повреждённые архивы! Продолжать?"
        read -r -p "   Введите yes для продолжения: " answer
        [[ "$answer" != "yes" ]] && exit 1
    fi
fi

loaded=0
failed=0

shopt -s nullglob
archives=( "$IN_DIR"/*.tar "$IN_DIR"/*.tar.gz )

if [[ ${#archives[@]} -eq 0 ]]; then
    echo "❌ В каталоге $IN_DIR нет ни .tar, ни .tar.gz файлов"
    exit 1
fi

echo "Найдено архивов: ${#archives[@]}"
echo

for archive in "${archives[@]}"; do
    echo "→ Загружаю: $archive"
    if docker load -i "$archive"; then
        ((loaded++)) || true
    else
        echo "   ❌ Не удалось загрузить $archive"
        ((failed++)) || true
    fi
done

echo
echo "============================================"
echo " Загружено:        $loaded"
echo " Ошибок:           $failed"
echo "--------------------------------------------"
echo " Локальные образы:"
docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' | head -30
echo "============================================"

exit 0
