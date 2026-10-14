from aiogram import Router

from magic_boot.handlers import start


def build_router() -> Router:
    router = Router()
    router.include_router(start.router)
    return router
