#!/usr/bin/env bash
#
# Сохраняет список Docker-образов в архивы для офлайн-переноса.
# Отсутствующие образы скачиваются автоматически (PULL_MISSING=true по умолчанию).
#
# Использование:
#   ./save_docker_images.sh [images.txt] [output_dir]
#
# Переменные окружения:
#   PULL_MISSING=true|false   если образа нет локально — скачать (по умолчанию true)
#   FORCE_PULL=true|false     всегда скачивать свежую версию, даже если образ есть (по умолчанию false)
#   COMPRESS=gzip|none        сжимать ли tar (по умолчанию gzip)
#
set -euo pipefail

LIST_FILE="${1:-images.txt}"
OUT_DIR="${2:-data}"
PULL_MISSING="${PULL_MISSING:-true}"
FORCE_PULL="${FORCE_PULL:-false}"
COMPRESS="${COMPRESS:-gzip}"

if [[ ! -f "$LIST_FILE" ]]; then
    echo "❌ Файл списка не найден: $LIST_FILE"
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "❌ Docker не найден в PATH"
    exit 1
fi

mkdir -p "$OUT_DIR"

saved=0
skipped=0
failed=0
pulled=0

# Безопасный trim пробелов по краям строки (без внешних процессов)
trim() {
    local s="$1"
    s="${s#"${s%%[![:space:]]*}"}"
    s="${s%"${s##*[![:space:]]}"}"
    printf '%s' "$s"
}

while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
    # Отрезаем комментарий и пробелы
    line="${raw_line%%#*}"
    line="$(trim "$line")"
    [[ -z "$line" ]] && continue

    image="$line"
    echo "→ Обрабатываю: $image"

    need_pull=false

    if [[ "$FORCE_PULL" == "true" ]]; then
        need_pull=true
        echo "   🔄 FORCE_PULL=true — скачиваю свежую версию..."
    elif ! docker image inspect "$image" >/dev/null 2>&1; then
        if [[ "$PULL_MISSING" == "true" ]]; then
            need_pull=true
            echo "   ⬇️  Образа нет локально — скачиваю из реестра..."
        else
            echo "   ⚠️  Образа нет локально. Пропускаю."
            echo "      (запусти с PULL_MISSING=true, чтобы скачать)"
            skipped=$((skipped + 1))
            continue
        fi
    fi

    if [[ "$need_pull" == "true" ]]; then
        if ! docker pull "$image"; then
            echo "   ❌ Не удалось скачать $image"
            failed=$((failed + 1))
            continue
        fi
        pulled=$((pulled + 1))
        echo "   ✅ Скачан: $image"
    fi

    # FS-safe имя файла: / и : -> _
    fname="$(printf '%s' "$image" | sed 's|[/:]|_|g')"
    out_path="$OUT_DIR/${fname}.tar"

    echo "   💾 Сохраняю: $out_path"
    docker save -o "$out_path" "$image"

    if [[ "$COMPRESS" == "gzip" ]]; then
        echo "   🗜️  Сжимаю..."
        gzip -f "$out_path"
        out_path="${out_path}.gz"
    fi

    saved=$((saved + 1))
done < "$LIST_FILE"

echo
echo "============================================"
echo " Скачано:          $pulled"
echo " Сохранено:        $saved"
echo " Пропущено:        $skipped"
echo " Ошибок:           $failed"
echo " Каталог:          $OUT_DIR"
echo "--------------------------------------------"
du -sh "$OUT_DIR" 2>/dev/null || true
echo "============================================"

# Чек-суммы для проверки целостности на целевой машине
if command -v sha256sum >/dev/null 2>&1; then
    echo
    echo " Считаю SHA256..."
    (cd "$OUT_DIR" && sha256sum ./*.tar* > checksums.sha256 2>/dev/null || true)
    echo "   Файл: $OUT_DIR/checksums.sha256"
fi

[[ "$failed" -gt 0 ]] && exit 1
exit 0
