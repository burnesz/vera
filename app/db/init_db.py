import logging
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.models.user import User

logger = logging.getLogger("vera.init_db")


def init_db(db: Session) -> None:
    """
    Inicializa dados essenciais no banco de dados na inicialização do sistema.
    Verifica se o usuário administrador definido no .env já existe; caso não exista, cria-o automaticamente.
    """
    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        logger.info("ADMIN_EMAIL ou ADMIN_PASSWORD não configurados. Inicialização de admin automático ignorada.")
        return

    admin_email = settings.ADMIN_EMAIL.strip().lower()
    user = db.query(User).filter(User.email == admin_email).first()

    if not user:
        logger.info(f"Usuário admin '{admin_email}' não encontrado no banco. Criando automaticamente via .env...")
        new_admin = User(
            nome=settings.ADMIN_NAME,
            email=admin_email,
            hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
            role="admin",
            is_ativo=True
        )
        db.add(new_admin)
        db.commit()
        db.refresh(new_admin)
        logger.info(f"Usuário administrador padrão criado com sucesso! [Email: {new_admin.email}, ID: {new_admin.id}]")
    else:
        # Garante privilégio de admin caso o usuário exista com outro perfil
        if user.role != "admin":
            logger.info(f"Usuário '{admin_email}' já existe com perfil '{user.role}'. Promovendo para 'admin'...")
            user.role = "admin"
            db.commit()
            db.refresh(user)
        logger.info(f"Usuário administrador '{admin_email}' verificado e pronto.")
