from bot.handlers.admin import router as admin_router
from bot.handlers.group_list import router as group_list_router
from bot.handlers.list_import import router as list_router
from bot.handlers.management import router as management_router
from bot.handlers.profile import router as profile_router
from bot.handlers.schedule import router as schedule_router
from bot.handlers.start import router as start_router
from bot.handlers.starosta import router as starosta_router
from bot.handlers.subjects import router as subjects_router

__all__ = [
    "admin_router",
    "group_list_router",
    "list_router",
    "management_router",
    "profile_router",
    "schedule_router",
    "start_router",
    "starosta_router",
    "subjects_router",
]
