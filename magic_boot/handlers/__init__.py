from aiogram import Router

from magic_boot.handlers import fallback, menu, settings, tasks, topics


def build_router() -> Router:
    router = Router()
    # Меню первым: его кнопки работают из любого состояния. Fallback — последним.
    for module in (menu, tasks, topics, settings, fallback):
        router.include_router(module.router)
    return router
