#!/usr/bin/env python3
"""
Script para criar backup dos dados do MySQL em formato JSON
Este script pode ser usado para fazer backup antes da migração
"""

import os
import sys
import json
from datetime import datetime
import pymysql

# Configurações do MySQL
MYSQL_CONFIG = {
    'host': '144.22.178.234',
    'port': 3306,
    'user': 'portfolio',
    'password': '8MEPBTxaaZRaKxs8',
    'database': 'portfolio',
    'charset': 'utf8mb4'
}

def datetime_handler(obj):
    """Converte datetime para string JSON"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Objeto do tipo {type(obj)} não é serializável JSON")

def backup_mysql_data():
    """Faz backup de todos os dados do MySQL em formato JSON"""
    print("🔄 Criando backup dos dados do MySQL...")
    
    try:
        # Conecta ao MySQL
        conn = pymysql.connect(**MYSQL_CONFIG)
        print("✅ Conectado ao MySQL com sucesso!")
        
        backup_data = {
            'backup_date': datetime.now().isoformat(),
            'database': MYSQL_CONFIG['database'],
            'tables': {}
        }
        
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # Lista todas as tabelas
            cursor.execute("SHOW TABLES")
            tables = [row[f'Tables_in_{MYSQL_CONFIG["database"]}'] for row in cursor.fetchall()]
            
            print(f"📋 Encontradas {len(tables)} tabelas para backup:")
            
            for table in tables:
                print(f"   📄 Fazendo backup da tabela: {table}")
                
                # Busca todos os dados da tabela
                cursor.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()
                
                backup_data['tables'][table] = {
                    'count': len(rows),
                    'data': rows
                }
                
                print(f"      ✅ {len(rows)} registros salvos")
        
        # Salva o backup em arquivo JSON
        backup_filename = f"mysql_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(backup_filename, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2, default=datetime_handler)
        
        print(f"\n🎉 Backup criado com sucesso!")
        print(f"📁 Arquivo: {backup_filename}")
        
        # Mostra estatísticas
        print("\n📊 Estatísticas do backup:")
        total_records = 0
        for table, info in backup_data['tables'].items():
            print(f"   {table}: {info['count']} registros")
            total_records += info['count']
        
        print(f"\n🔢 Total de registros: {total_records}")
        
        conn.close()
        print("🔐 Conexão MySQL fechada")
        
        return backup_filename
        
    except Exception as e:
        print(f"❌ Erro durante o backup: {str(e)}")
        return None

def main():
    """Função principal"""
    print("💾 Script de Backup MySQL")
    print("=" * 40)
    
    backup_file = backup_mysql_data()
    
    if backup_file:
        print(f"\n✅ Backup concluído com sucesso!")
        print(f"📄 O arquivo '{backup_file}' contém todos os seus dados do MySQL.")
        print("\nVocê pode usar este arquivo para:")
        print("  1. Fazer a migração manual para Firebase")
        print("  2. Restaurar dados se necessário")
        print("  3. Verificar os dados antes da migração")
    else:
        print("\n❌ Falha no backup.")

if __name__ == "__main__":
    main()
