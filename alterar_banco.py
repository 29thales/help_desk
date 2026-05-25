import sqlite3

# Caminho para o banco de dados (edite conforme necessário)
DB_PATH = 'sistema_chamados.db'

try:
    # Conectar ao banco de dados
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tentar adicionar a coluna quantidade_total
    try:
        cursor.execute('ALTER TABLE chamados ADD COLUMN quantidade_total INTEGER NOT NULL DEFAULT 0;')
        print('Coluna quantidade_total adicionada com sucesso à tabela chamados.')
    except sqlite3.OperationalError as e:
        if 'duplicate column name' in str(e):
            print('A coluna quantidade_total já existe na tabela chamados.')
        else:
            raise e
    
    # Obter e mostrar a estrutura da tabela
    cursor.execute('PRAGMA table_info(chamados);')
    columns = cursor.fetchall()
    
    print('\nEstrutura da tabela chamados:')
    for col in columns:
        cid, name, type_, notnull, dflt_value, pk = col
        print(f'Coluna: {name}, Tipo: {type_}, Não nulo: {bool(notnull)}, Valor padrão: {dflt_value}, Chave primária: {bool(pk)}')
    
    # Fechar a conexão
    conn.close()
    
except Exception as e:
    print(f'Erro: {e}')