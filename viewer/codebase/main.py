from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .routes import general, media


# ---------------------------------------------------------------------------
# Пути к ассетам.
# Ищем директории относительно этого файла, чтобы не зависеть от WORKDIR.
# Поддерживаются два варианта структуры:
#   /app/codebase/static
#   /app/static
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent


def _find_asset_directory(name: str) -> Path:
    """
    Ищет директорию ассетов в двух возможных местах:
    рядом с main.py и на уровень выше.
    """

    candidates = (
        BASE_DIR / name,
        BASE_DIR.parent / name,
    )

    for candidate in candidates:
        if candidate.is_dir():
            return candidate

    checked_paths = "\n  ".join(str(candidate) for candidate in candidates)

    raise RuntimeError(
        f"Не найдена директория '{name}'.\n"
        f"Искал в следующих местах:\n  {checked_paths}\n\n"
        f"Проверь структуру проекта, Dockerfile и .dockerignore."
    )


TEMPLATES_DIR = _find_asset_directory("templates")
STATIC_DIR = _find_asset_directory("static")


app = FastAPI()

app.state.templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(general.router)
app.include_router(media.router)
