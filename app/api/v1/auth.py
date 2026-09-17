from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.security import get_password_hash, verify_password, create_access_token
from app.db.session import get_db
from app.db.models.user import User
from app.schemas.auth import Token, LoginRequest
from app.schemas.user import UserCreate, UserResponse

router = APIRouter(prefix="/auth", tags=["Autenticação"])


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """
    Localiza o usuário por e-mail e valida o hash da senha fornecida.
    """
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra um novo usuário na plataforma"
)
def register(
    user_in: UserCreate,
    db: Session = Depends(get_db)
) -> UserResponse:
    """
    Cria uma nova conta de estudante na plataforma:
    - Valida se o e-mail já não está cadastrado.
    - Aplica hash criptográfico seguro (bcrypt) na senha.
    - Define a role estritamente como 'student' (mitigação de Privilege Escalation).
    - Retorna os dados públicos do usuário recém-criado.
    """
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Já existe um usuário cadastrado com este e-mail."
        )

    hashed_password = get_password_hash(user_in.password)
    user = User(
        nome=user_in.nome,
        email=user_in.email,
        hashed_password=hashed_password,
        role="student",
        is_ativo=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/login",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Login via formulário OAuth2 (compatível com Swagger UI)"
)
def login_oauth2(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
) -> Token:
    """
    Autentica o usuário usando formato padrão OAuth2 (username = email, password):
    - Compatível nativamente com o botão Authorize do Swagger UI (/docs).
    - Emite token JWT de acesso com validade configurada.
    """
    user = authenticate_user(db, email=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_ativo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário inativo na plataforma."
        )

    access_token = create_access_token(subject=str(user.id), role=user.role)
    return Token(access_token=access_token, token_type="bearer")


@router.post(
    "/login/json",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Login via corpo JSON (para consumo em frontends Web)"
)
def login_json(
    credentials: LoginRequest,
    db: Session = Depends(get_db)
) -> Token:
    """
    Autentica o usuário a partir de um payload JSON tradicional ({email, password}).
    """
    user = authenticate_user(db, email=credentials.email, password=credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_ativo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário inativo na plataforma."
        )

    access_token = create_access_token(subject=str(user.id), role=user.role)
    return Token(access_token=access_token, token_type="bearer")


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Retorna os dados do usuário autenticado"
)
def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
) -> UserResponse:
    """
    Retorna o perfil e papel do usuário logado via Bearer token JWT.
    """
    return current_user
