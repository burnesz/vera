import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.router import api_router
from app.db.session import SessionLocal, get_db
from app.db.init_db import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("vera.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: inicialização de banco e verificação/criação do admin inicial via .env
    logger.info("Iniciando plataforma VERA...")
    try:
        if get_db in app.dependency_overrides:
            db_gen = app.dependency_overrides[get_db]()
            db = next(db_gen)
            try:
                init_db(db)
            finally:
                try:
                    next(db_gen)
                except StopIteration:
                    pass
        else:
            db = SessionLocal()
            try:
                init_db(db)
            finally:
                db.close()
    except Exception as e:
        logger.warning(f"Aviso ao inicializar dados no startup: {e}")

    yield

    # Shutdown
    logger.info("Encerrando plataforma VERA...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API da Plataforma VERA — RAG para feedback pedagógico e aprendizado de Matemática no ENEM.",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configuração de CORS para permitir integração com Frontend Web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro das rotas da API
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "docs": "/docs",
        "api_v1": settings.API_V1_STR
    }
