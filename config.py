# config.py
# ============================================
# ARQUIVO DE CONFIGURAÇÃO DO SISTEMA
# ============================================
# Este arquivo centraliza todas as configurações
# do sistema em um único lugar para facilitar
# manutenção e segurança

import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

# ============================================
# CONFIGURAÇÕES DE SEGURANÇA
# ============================================

# Chave secreta para gerar tokens JWT
# ⚠️ IMPORTANTE: Mude isto para uma chave aleatória forte!
SECRET_KEY = os.getenv("SECRET_KEY", "sua-chave-super-secreta-mude-isto-em-producao")

# Algoritmo de criptografia do JWT
ALGORITHM = "HS256"

# Tempo de expiração do token em minutos
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 horas

# ============================================
# CONFIGURAÇÕES DO BANCO DE DADOS
# ============================================

# Caminho do banco de dados SQLite
# Ele será criado automaticamente na pasta raiz
DATABASE_URL = "sqlite:///./sistema_chamados.db"

# ============================================
# CONFIGURAÇÕES DE EMAIL
# ============================================

# Configurações para envio de emails (opcional, para futuro)
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "seu-email@gmail.com")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "sua-senha-aqui")

# ============================================
# CONFIGURAÇÕES DE APLICAÇÃO
# ============================================

# Nome da aplicação
APP_NAME = "Sistema de Chamados - Help Desk"
APP_VERSION = "1.0.0"

# Modo debug (True em desenvolvimento, False em produção)
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# ============================================
# CONFIGURAÇÕES DE FATURAMENTO
# ============================================

# Valor padrão da hora de serviço (em reais)
VALOR_HORA_PADRAO = 130.00

# Tempo mínimo de faturamento em minutos
# Qualquer atendimento com menos tempo será cobrado como este valor
TEMPO_MINIMO_FATURAMENTO = 30  # minutos

# Valor mínimo cobrado por hora (para 1-30 minutos)
VALOR_MINIMO_30MIN = 65.00

print("✅ Configurações carregadas com sucesso!")