# schemas/usuario_schema.py
#
# Schemas da Fase 1 - base multi-usuário.
# Mantém também os schemas legados (UsuarioBase, UsuarioCreate, UsuarioLogin, Token)
# para o auth.py e qualquer código antigo continuar funcionando.

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Literal
from datetime import datetime


# ====================================================
# LEGADOS — mantidos pra compatibilidade com auth.py
# ====================================================

class UsuarioBase(BaseModel):
    email: EmailStr
    nome: str
    is_admin: bool = False


class UsuarioCreate(UsuarioBase):
    senha: str


class UsuarioLogin(BaseModel):
    email: EmailStr
    senha: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    email: Optional[str] = None


# ====================================================
# FASE 1 — multi-usuário
# ====================================================

TipoUsuario = Literal["admin", "tecnico", "cliente"]


class UsuarioCriar(BaseModel):
    """Admin cria admin/técnico/cliente."""
    nome: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    senha: str = Field(..., min_length=6, max_length=100)
    tipo_usuario: TipoUsuario

    # Só pra técnicos
    comissao_percentual: Optional[float] = Field(default=0.0, ge=0, le=100)
    pode_ver_fila_aberta: Optional[bool] = True

    # Só pra clientes
    cliente_id: Optional[int] = None

    @validator("comissao_percentual")
    def comissao_valida(cls, v):
        if v is None:
            return 0.0
        return v

    def model_dump_validado(self) -> dict:
        """Aplica regras de tipo: zera campos não-aplicáveis."""
        d = self.dict() if hasattr(self, "dict") else self.model_dump()
        if d["tipo_usuario"] != "tecnico":
            d["comissao_percentual"] = 0.0
            d["pode_ver_fila_aberta"] = False
        if d["tipo_usuario"] != "cliente":
            d["cliente_id"] = None
        return d


class UsuarioAtualizar(BaseModel):
    """Admin edita usuário existente. Não troca tipo nem reseta senha aqui."""
    nome: Optional[str] = Field(None, min_length=2, max_length=150)
    email: Optional[EmailStr] = None
    comissao_percentual: Optional[float] = Field(None, ge=0, le=100)
    pode_ver_fila_aberta: Optional[bool] = None
    cliente_id: Optional[int] = None
    ativo: Optional[bool] = None


class ResetarSenhaInput(BaseModel):
    """Admin define a nova senha (sem precisar da antiga)."""
    nova_senha: str = Field(..., min_length=6, max_length=100)


class UsuarioResposta(BaseModel):
    """Resposta padrão: nunca expõe hash de senha."""
    id: int
    nome: str
    email: str
    tipo_usuario: str
    is_admin: bool
    ativo: bool

    # Técnico
    comissao_percentual: float = 0.0
    pode_ver_fila_aberta: bool = False

    # Cliente
    cliente_id: Optional[int] = None
    nome_cliente_vinculado: Optional[str] = None  # derivado

    valor_hora: float = 0.0
    criado_em: Optional[datetime] = None

    class Config:
        from_attributes = True


# Resposta legada (mantida pra não quebrar quem importa)
class UsuarioResposta_Legada(UsuarioBase):
    id: int
    criado_em: datetime

    class Config:
        from_attributes = True
