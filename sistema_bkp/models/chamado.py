# models/chamado.py

from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base

class Chamado(Base):
    """
    Modelo de Chamado/Ticket para o sistema Help Desk.
    Representa um registro de um problema ou solicitação,
    vinculado a um cliente e podendo ter múltiplos atendimentos.
    """
    
    __tablename__ = "chamados"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(255), nullable=False)
    descricao = Column(Text, nullable=False)
    categoria = Column(String(50), nullable=False)
    prioridade = Column(String(20), default="media", nullable=False)
    status = Column(String(20), default="aberto", nullable=False)
    
    # Dados de Tempo de Atendimento
    data_inicio = Column(DateTime, nullable=True)
    data_termino = Column(DateTime, nullable=True)
    tempo_gasto_minutos = Column(Integer, default=0, nullable=False)
    
    # Vinculo com Cliente
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    cliente = relationship("Cliente", back_populates="chamados")
    
    # Vinculo com Usuário Solicitante
    solicitante_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    usuario_solicitante = relationship(
        "Usuario", 
        back_populates="chamados_solicitados", 
        foreign_keys=[solicitante_id]
    )

    criado_em = Column(DateTime, default=datetime.now, nullable=False)
    atualizado_em = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    
    # Relacionamento com Atendimentos (Histórico)
    atendimentos = relationship("Atendimento", back_populates="chamado")

    def __repr__(self):
        return (
            f"<Chamado(id={self.id}, titulo='{self.titulo}', "
            f"status='{self.status}', cliente_id={self.cliente_id})>"
        )