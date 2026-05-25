# ============================================
# MAIN - SISTEMA HELP DESK
# ============================================

from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import uvicorn
import os

# Banco e models
from database import engine, Base, get_db
from models.user import Usuario

# Auth
from auth import (
    get_password_hash,
    router as auth_router,
    obter_usuario_atual
)

# ============================================
# CONFIGURAÇÕES
# ============================================

APP_TITLE = "Help Desk - Sistema Completo"
DEFAULT_ADMIN_EMAIL = "admin@helpdesk.com"
DEFAULT_ADMIN_PASSWORD = "admin123456"

# ============================================
# CRIAR APP
# ============================================

app = FastAPI(title=APP_TITLE, version="1.0.0")

# ============================================
# CRIAR BANCO
# ============================================

Base.metadata.create_all(bind=engine)

# ============================================
# STATIC FILES
# ============================================

if not os.path.exists("static"):
    os.makedirs("static")

app.mount("/static", StaticFiles(directory="static"), name="static")

# ============================================
# ROTAS DE AUTENTICAÇÃO (API)
# ============================================

app.include_router(auth_router, prefix="/api/auth", tags=["Autenticação"])

# ============================================
# ROTAS HTML (FRONTEND)
# ============================================

# 🔐 LOGIN
@app.get("/")
def login_page():
    return FileResponse("templates/login.html")

# 📊 DASHBOARD
@app.get("/dashboard")
def dashboard_page():
    return FileResponse("templates/dashboard.html")

# 👥 CLIENTES (HTML)
@app.get("/clientes/pagina")
def clientes_page():
    return FileResponse("templates/clientes.html")

# ============================================
# ROTAS API (BACKEND)
# ============================================

@app.get("/api/status")
def status():
    return {"status": "OK", "mensagem": "Sistema Help Desk rodando!"}

# Exemplo de rota protegida
@app.get("/api/usuario-logado")
def usuario_logado(usuario: Usuario = Depends(obter_usuario_atual)):
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "is_admin": usuario.is_admin
    }

# ============================================
# STARTUP
# ============================================

@app.on_event("startup")
def startup_event():
    db: Session = next(get_db())

    try:
        print("🚀 Iniciando sistema...")
        print("✅ Banco conectado")

        admin = db.query(Usuario).filter(Usuario.email == DEFAULT_ADMIN_EMAIL).first()

        if not admin:
            admin = Usuario(
                nome="Administrador",
                email=DEFAULT_ADMIN_EMAIL,
                senha_hash=get_password_hash(DEFAULT_ADMIN_PASSWORD),
                is_admin=True,
                valor_hora=0.0
            )
            db.add(admin)
            db.commit()
            print(f"✅ Admin criado: {DEFAULT_ADMIN_EMAIL}")
        else:
            print(f"✅ Admin já existe")

        print("🔥 Sistema pronto!")

    except Exception as e:
        print(f"❌ Erro ao iniciar: {e}")

    finally:
        db.close()

# ============================================
# RUN
# ============================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )