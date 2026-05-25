# models/atendimento.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from database import Base

# 1. Definição do Enum para o Status do Atendimento
class StatusAtendimento(enum.Enum):
    """Enum para representar os possíveis status de um atendimento."""
    em_progresso = "Em Progresso"
    pausado = "Pausado"
    finalizado = "Finalizado"

# 2. Definição do Modelo Atendimento
class Atendimento(Base):
    """
    Representa um registro de atendimento a um chamado no sistema.
    Cada atendimento está associado a um chamado específico e a um usuário.
    """
    __tablename__ = "atendimentos"

    id = Column(Integer, primary_key=True, index=True)
    
    # Chave estrangeira para o chamado
    chamado_id = Column(Integer, ForeignKey("chamados.id"), nullable=False)
    
    # Chave estrangeira para o usuário
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    
    data_inicio = Column(DateTime, default=datetime.utcnow, nullable=False)
    data_fim = Column(DateTime, nullable=True)
    duracao_minutos = Column(Integer, nullable=True)
    descricao = Column(String, nullable=False)
    
    # Status do atendimento usando o Enum
    status = Column(Enum(StatusAtendimento), default=StatusAtendimento.em_progresso, nullable=False)
    
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 3. Relacionamentos
    chamado = relationship("Chamado", back_populates="atendimentos")
    usuario = relationship("Usuario", back_populates="atendimentos")

    # 4. Método __repr__ para debug
    def __repr__(self):
        return (
            f"<Atendimento(id={self.id}, chamado_id={self.chamado_id}, "
            f"usuario_id={self.usuario_id}, status='{self.status.value}')>"
        )