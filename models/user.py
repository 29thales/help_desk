from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    senha_hash = Column(String)

    # Compatibilidade: mantido para não quebrar código antigo
    is_admin = Column(Boolean, default=False)
    valor_hora = Column(Float, default=0.0)

    # ============ FASE 1 - MULTI-USUÁRIO ============
    # 'admin' | 'tecnico' | 'cliente'
    tipo_usuario = Column(String(20), default="tecnico", nullable=False, index=True)

    # Só preenchido se tipo='cliente' — vínculo com a empresa
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)

    # Só relevante para técnicos
    comissao_percentual = Column(Float, default=0.0, nullable=False)
    pode_ver_fila_aberta = Column(Boolean, default=False, nullable=False)

    # Soft delete (não pode deletar admin único — vide validação na rota)
    ativo = Column(Boolean, default=True, nullable=False)

    # Fase 3: força cliente a trocar a senha no primeiro login
    precisa_trocar_senha = Column(Boolean, default=False, nullable=False)

    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)

    # ============ RELACIONAMENTOS ============
    chamados_solicitados = relationship(
        "Chamado",
        back_populates="usuario_solicitante",
        foreign_keys="Chamado.solicitante_id",
    )
    # Chamados que esse usuário (técnico) está atendendo
    chamados_atendendo = relationship(
        "Chamado",
        back_populates="tecnico",
        foreign_keys="Chamado.tecnico_id",
    )
    # Empresa vinculada (se for cliente)
    cliente_vinculado = relationship("Cliente", foreign_keys=[cliente_id])

    # ============ HELPERS ============
    @property
    def eh_admin(self) -> bool:
        return self.tipo_usuario == "admin" or self.is_admin

    @property
    def eh_tecnico(self) -> bool:
        return self.tipo_usuario == "tecnico"

    @property
    def eh_cliente(self) -> bool:
        return self.tipo_usuario == "cliente"

    def __repr__(self):
        return f"<Usuario(id={self.id}, email='{self.email}', tipo='{self.tipo_usuario}')>"
