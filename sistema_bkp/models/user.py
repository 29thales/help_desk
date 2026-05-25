from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime
from datetime import datetime
from database import Base

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    senha_hash = Column(String)
    is_admin = Column(Boolean, default=False)
    valor_hora = Column(Float, default=0.0)

    # 🔥 ADICIONE ISSO
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)