import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict, Field


class UserCreate(BaseModel):
    """
    Dados necessários para cadastro de um novo usuário na plataforma.
    """
    nome: str = Field(..., min_length=2, max_length=255, description="Nome completo do usuário")
    email: EmailStr = Field(..., description="Email válido do usuário")
    password: str = Field(..., min_length=6, max_length=128, description="Senha de acesso")
    role: str = Field(default="student", description="Papel: 'student' ou 'admin'")


class UserResponse(BaseModel):
    """
    Dados do usuário retornados pela API (sem expor credenciais sensíveis).
    """
    id: uuid.UUID
    nome: str
    email: str
    role: str
    is_ativo: bool
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
