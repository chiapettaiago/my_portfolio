#!/usr/bin/env python3
"""
Script para verificar a estrutura do banco MySQL antes da migração
"""

import pymysql
import sys

# Configurações do MySQL
MYSQL_CONFIG = {
    'host': '144.22.178.234',
    'port': 3306,
    'user': 'portfolio',
    'password': '8MEPBTxaaZRaKxs8',
    'database': 'portfolio',
    'charset': 'utf8mb4'
}

def check_mysql_structure():
    """Verifica a estrutura do banco MySQL"""
    try:
        # Conecta ao MySQL
        conn = pymysql.connect(**MYSQL_CONFIG)
        print("✅ Conectado ao MySQL com sucesso!")
        print("=" * 60)
        
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # Lista todas as tabelas
            cursor.execute("SHOW TABLES")
            tables = [row[f'Tables_in_{MYSQL_CONFIG["database"]}'] for row in cursor.fetchall()]
            
            print(f"📋 Tabelas encontradas no banco '{MYSQL_CONFIG['database']}':")
            print("-" * 40)
            
            for table in tables:
                print(f"📄 Tabela: {table}")
                
                # Mostra a estrutura da tabela
                cursor.execute(f"DESCRIBE {table}")
                columns = cursor.fetchall()
                
                print("   Colunas:")
                for col in columns:
                    print(f"     - {col['Field']} ({col['Type']}) {col['Key']} {col['Null']} {col['Default']}")
                
                # Conta os registros
                cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                count = cursor.fetchone()['count']
                print(f"   📊 Total de registros: {count}")
                
                # Mostra alguns exemplos de dados (primeiros 3 registros)
                cursor.execute(f"SELECT * FROM {table} LIMIT 3")
                samples = cursor.fetchall()
                
                if samples:
                    print("   📝 Exemplos de dados:")
                    for i, sample in enumerate(samples, 1):
                        print(f"     Registro {i}: {dict(sample)}")
                
                print("-" * 40)
            
            print(f"\n🔢 Total de tabelas: {len(tables)}")
            
        conn.close()
        print("🔐 Conexão MySQL fechada")
        
    except Exception as e:
        print(f"❌ Erro ao conectar ao MySQL: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    print("🔍 Verificação da Estrutura do Banco MySQL")
    print("=" * 50)
    check_mysql_structure()
