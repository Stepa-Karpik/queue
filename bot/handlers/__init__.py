from bot.handlers.start import router as start_router
from bot.handlers.profile import router as profile_router
from bot.handlers.subjects import router as subjects_router
from bot.handlers.list_import import router as list_router
from bot.handlers.starosta import router as starosta_router
from bot.handlers.starosta_panel import router as starosta_panel_router

__all__ = [
    "start_router",
    "profile_router",
    "subjects_router",
    "list_router",
    "starosta_router",
    "starosta_panel_router",
]
