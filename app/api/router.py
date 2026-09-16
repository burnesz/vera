from fastapi import APIRouter
from app.api.v1 import health, chat, auth, simulado

api_router = APIRouter()

# Rotas da API v1
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(simulado.router, prefix="/simulados", tags=["Simulados"])

