# ============================================
# MIGRATION FASE 3 - TROCA DE SENHA INICIAL
# ============================================
# Adiciona coluna `precisa_trocar_senha` em usuarios.
# Idempotente + backup automático.
# ============================================

import sqlite3
import shutil
import os
import sys
from datetime import datetime

DB_PATH = "sistema_chamados.db"


def coluna_existe(cur, tabela, coluna):
    cur.execute(f"PRAGMA table_info({tabela})")
    return any(row[1] == coluna for row in cur.fetchall())


def fazer_backup():
    if not os.path.exists(DB_PATH):
        print(f"⚠️  Banco {DB_PATH} não encontrado.")
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bkp = f"{DB_PATH}.bkp_{timestamp}"
    shutil.copy2(DB_PATH, bkp)
    print(f"💾 Backup criado: {bkp}")
    return bkp


def migrar():
    print("=" * 60)
    print("MIGRATION FASE 3 - TROCA DE SENHA INICIAL")
    print("=" * 60)

    backup = fazer_backup()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        print("\n📋 Tabela `usuarios`:")
        if coluna_existe(cur, "usuarios", "precisa_trocar_senha"):
            print("  · precisa_trocar_senha já existe — pulando")
        else:
            cur.execute(
                "ALTER TABLE usuarios ADD COLUMN precisa_trocar_senha BOOLEAN DEFAULT 0"
            )
            print("  ✅ precisa_trocar_senha adicionada (default=0)")

        # Admin e técnicos já existentes NÃO precisam trocar senha (só é marcado
        # quando ADMIN cria cliente novo). Garante null→0.
        cur.execute("UPDATE usuarios SET precisa_trocar_senha = 0 WHERE precisa_trocar_senha IS NULL")

        conn.commit()
        print("\n✅ MIGRATION CONCLUÍDA")
        if backup:
            print(f"💾 Backup em: {backup}")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERRO: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    migrar()
