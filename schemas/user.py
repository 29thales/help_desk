# schemas/user.py
# Shim de compatibilidade. Tudo agora vive em schemas/usuario_schema.py.
# Mantido para não quebrar imports antigos (ex: `from schemas.user import ...`).

from schemas.usuario_schema import (  # noqa: F401
    UsuarioBase,
    UsuarioCreate,
    UsuarioLogin,
    Token,
    TokenData,
    UsuarioResposta_Legada as UsuarioResposta,
)
