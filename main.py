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
from models.cliente import Cliente
from models.chamado import Chamado, HistoricoChamado
from models.servico_tecnico import ServicoTecnico

# Auth
from auth import (
    get_password_hash,
    router as auth_router,
    obter_usuario_atual
)

# Rotas
from routes.clientes import router as clientes_router
from routes.chamados import router as chamados_router
from routes.faturamento import router as faturamento_router
from routes.dashboard import router as dashboard_router
from routes.servicos import router as servicos_router
from routes.usuarios import router as usuarios_router
from routes.tecnico import router as tecnico_router
from routes.cliente import router as cliente_router
from routes.comissao import router as comissao_router

# ============================================
# CONFIGURAÇÕES
# ============================================

APP_TITLE = "Help Desk - Sistema Completo"
DEFAULT_ADMIN_EMAIL = "admin@helpdesk.com"
DEFAULT_ADMIN_PASSWORD = "admin123456"

# ============================================
# CRIAR APP
# ============================================

app = FastAPI(title=APP_TITLE, version="2.0.0")

# ============================================
# DEBUG - LOG DE ERROS 500 (temporário, remover depois)
# ============================================
import traceback
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def debug_exception_handler(request: Request, exc: Exception):
    # Imprime traceback completo no console
    print("=" * 80)
    print(f"❌ ERRO 500 em {request.method} {request.url}")
    print("=" * 80)
    traceback.print_exc()
    print("=" * 80)
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {str(exc)}"},
    )

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
# ROTAS API
# ============================================

app.include_router(auth_router, prefix="/api/auth", tags=["Autenticação"])
app.include_router(clientes_router, prefix="/api/clientes", tags=["Clientes"])
app.include_router(chamados_router, prefix="/api/chamados", tags=["Chamados"])
app.include_router(faturamento_router, prefix="/api/faturamento", tags=["Faturamento"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(servicos_router, prefix="/api/servicos", tags=["Serviços Técnicos"])
app.include_router(usuarios_router, prefix="/api/usuarios", tags=["Usuários"])
app.include_router(tecnico_router, prefix="/api/tecnico", tags=["Técnico"])
app.include_router(cliente_router, prefix="/api/cliente", tags=["Cliente"])
app.include_router(comissao_router, prefix="/api/comissao", tags=["Comissão"])

# ============================================
# ROTAS HTML (FRONTEND)
# ============================================

@app.get("/")
def login_page():
    return FileResponse("templates/login.html")

@app.get("/dashboard")
def dashboard_page():
    return FileResponse("templates/dashboard.html")

@app.get("/clientes/pagina")
def clientes_page():
    return FileResponse("templates/clientes.html")

@app.get("/chamados/pagina")
def chamados_page():
    return FileResponse("templates/chamados.html")

@app.get("/faturamento/pagina")
def faturamento_page():
    return FileResponse("templates/faturamento.html")

@app.get("/servicos/pagina")
def servicos_page():
    return FileResponse("templates/servicos.html")

@app.get("/usuarios/pagina")
def usuarios_page():
    return FileResponse("templates/usuarios.html")

@app.get("/tecnico/painel")
def tecnico_painel_page():
    return FileResponse("templates/tecnico_painel.html")

# Alias de compatibilidade (caso algo referencie /tecnico/dashboard)
@app.get("/tecnico/dashboard")
def tecnico_dashboard_alias():
    return FileResponse("templates/tecnico_painel.html")

@app.get("/cliente/painel")
def cliente_painel_page():
    return FileResponse("templates/cliente_painel.html")

@app.get("/trocar-senha")
def trocar_senha_page():
    return FileResponse("templates/trocar_senha.html")

@app.get("/comissao/pagina")
def comissao_page():
    return FileResponse("templates/comissao.html")

# ============================================
# STATUS
# ============================================

@app.get("/api/status")
def status():
    return {"status": "OK", "mensagem": "Sistema Help Desk rodando!"}

@app.get("/api/usuario-logado")
def usuario_logado(usuario: Usuario = Depends(obter_usuario_atual)):
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "is_admin": usuario.is_admin,
        "tipo_usuario": getattr(usuario, "tipo_usuario", "admin" if usuario.is_admin else "tecnico"),
        "pode_ver_fila_aberta": bool(getattr(usuario, "pode_ver_fila_aberta", False)),
        "precisa_trocar_senha": bool(getattr(usuario, "precisa_trocar_senha", False)),
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
            print("✅ Admin já existe")

        print("🔥 Sistema pronto!")
        print("📌 Acesse: http://localhost:8080")

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
