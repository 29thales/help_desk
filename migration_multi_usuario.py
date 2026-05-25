# ============================================
# MIGRATION FASE 1 - BASE MULTI-USUÁRIO
# ============================================
# Adiciona colunas em `usuarios` e `chamados`, cria tabela
# `chamado_transferencias` e marca admins existentes.
#
# IMPORTANTE: Faz backup automático do banco antes de tudo.
# Se algo der errado, é só restaurar o arquivo .bkp_<timestamp>.db
# ============================================

import sqlite3
import shutil
import os
import sys
from datetime import datetime

DB_PATH = "sistema_chamados.db"


# ---------- helpers ----------

def coluna_existe(cur, tabela, coluna):
    cur.execute(f"PRAGMA table_info({tabela})")
    return any(row[1] == coluna for row in cur.fetchall())


def tabela_existe(cur, nome):
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (nome,),
    )
    return cur.fetchone() is not None


def add_coluna(cur, tabela, definicao_sql):
    """definicao_sql ex: 'tipo_usuario VARCHAR(20) DEFAULT \"tecnico\"'"""
    nome_coluna = definicao_sql.split()[0]
    if coluna_existe(cur, tabela, nome_coluna):
        print(f"  · {tabela}.{nome_coluna} já existe — pulando")
        return False
    cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {definicao_sql}")
    print(f"  ✅ {tabela}.{nome_coluna} adicionada")
    return True


# ---------- backup ----------

def fazer_backup():
    if not os.path.exists(DB_PATH):
        print(f"⚠️  Banco {DB_PATH} não encontrado. Vai ser criado do zero.")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bkp = f"{DB_PATH}.bkp_{timestamp}"
    shutil.copy2(DB_PATH, bkp)
    print(f"💾 Backup criado: {bkp}")
    return bkp


# ---------- migration ----------

def migrar():
    print("=" * 60)
    print("MIGRATION FASE 1 - BASE MULTI-USUÁRIO")
    print("=" * 60)

    backup = fazer_backup()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        # ===== USUARIOS =====
        print("\n📋 Tabela `usuarios`:")
        add_coluna(cur, "usuarios",
                   "tipo_usuario VARCHAR(20) DEFAULT 'tecnico'")
        add_coluna(cur, "usuarios",
                   "cliente_id INTEGER REFERENCES clientes(id)")
        add_coluna(cur, "usuarios",
                   "comissao_percentual FLOAT DEFAULT 0")
        add_coluna(cur, "usuarios",
                   "pode_ver_fila_aberta BOOLEAN DEFAULT 0")
        add_coluna(cur, "usuarios",
                   "ativo BOOLEAN DEFAULT 1")

        # ===== CHAMADOS =====
        print("\n📋 Tabela `chamados`:")
        add_coluna(cur, "chamados",
                   "tecnico_id INTEGER REFERENCES usuarios(id)")
        add_coluna(cur, "chamados",
                   "motivo_devolucao TEXT")

        # ===== CHAMADO_TRANSFERENCIAS =====
        print("\n📋 Tabela `chamado_transferencias`:")
        if tabela_existe(cur, "chamado_transferencias"):
            print("  · chamado_transferencias já existe — pulando")
        else:
            cur.execute("""
                CREATE TABLE chamado_transferencias (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chamado_id INTEGER NOT NULL REFERENCES chamados(id),
                    de_usuario_id INTEGER REFERENCES usuarios(id),
                    para_usuario_id INTEGER REFERENCES usuarios(id),
                    motivo TEXT,
                    criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute(
                "CREATE INDEX ix_transf_chamado ON chamado_transferencias(chamado_id)"
            )
            print("  ✅ chamado_transferencias criada")

        # ===== POPULAR tipo_usuario =====
        # Regra do briefing: is_admin=true → 'admin', resto → 'tecnico'
        # Confirmado pelo usuário: ninguém vira cliente automaticamente.
        print("\n🔄 Populando `tipo_usuario` em registros existentes:")

        cur.execute("""
            UPDATE usuarios
            SET tipo_usuario = 'admin'
            WHERE is_admin = 1
              AND (tipo_usuario IS NULL OR tipo_usuario = 'tecnico')
        """)
        admins_marcados = cur.rowcount
        print(f"  ✅ {admins_marcados} admin(s) marcado(s) como tipo_usuario='admin'")

        cur.execute("""
            UPDATE usuarios
            SET tipo_usuario = 'tecnico'
            WHERE (is_admin = 0 OR is_admin IS NULL)
              AND (tipo_usuario IS NULL OR tipo_usuario = '')
        """)
        tecnicos_marcados = cur.rowcount
        if tecnicos_marcados > 0:
            print(f"  ✅ {tecnicos_marcados} usuário(s) não-admin marcado(s) como 'tecnico'")
        else:
            print("  · Nenhum não-admin para marcar (banco só tem admins)")

        # Garante ativo=1 em todos os existentes
        cur.execute("UPDATE usuarios SET ativo = 1 WHERE ativo IS NULL")

        # ===== STATUS 'atribuido' =====
        # Não precisa alterar enum (status é VARCHAR livre), só registra no log.
        print("\n📌 Status 'atribuido' agora é válido na coluna `status` de chamados")
        print("   (campo é VARCHAR livre, sem CHECK constraint — nada a alterar)")

        conn.commit()

        # ===== VERIFICAÇÃO =====
        print("\n" + "=" * 60)
        print("✅ MIGRATION CONCLUÍDA COM SUCESSO")
        print("=" * 60)

        cur.execute("SELECT COUNT(*) FROM usuarios WHERE tipo_usuario='admin'")
        n_admin = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM usuarios WHERE tipo_usuario='tecnico'")
        n_tec = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM usuarios WHERE tipo_usuario='cliente'")
        n_cli = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM usuarios")
        n_total = cur.fetchone()[0]

        print(f"\n📊 Resumo:")
        print(f"   Admins:   {n_admin}")
        print(f"   Técnicos: {n_tec}")
        print(f"   Clientes: {n_cli}")
        print(f"   TOTAL:    {n_total}")

        if backup:
            print(f"\n💾 Backup salvo em: {backup}")
            print("   (Se algo der errado, restaure com: cp {backup} {DB_PATH})")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERRO: {e}")
        if backup:
            print(f"💾 Backup intacto em {backup} — restaure se necessário")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    migrar()
