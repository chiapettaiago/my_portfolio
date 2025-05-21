#!/usr/bin/env python
from app import app, db
from sqlalchemy import text, inspect

print("Iniciando migração para adicionar campos ao modelo User...")

# Usar o contexto da aplicação Flask
with app.app_context():
    try:
        # Verificar se as colunas já existem
        inspector = inspect(db.engine)
        existing_columns = [col['name'] for col in inspector.get_columns('user')]
        
        # Adicionar as novas colunas à tabela user (apenas se não existirem)
        if 'fullname' not in existing_columns:
            db.session.execute(text("ALTER TABLE user ADD COLUMN fullname VARCHAR(100)"))
            print("Coluna 'fullname' adicionada à tabela User.")
        else:
            print("Coluna 'fullname' já existe.")
        
        if 'email' not in existing_columns:
            db.session.execute(text("ALTER TABLE user ADD COLUMN email VARCHAR(120)"))
            print("Coluna 'email' adicionada à tabela User.")
            
            # Adicionar índice único à coluna email
            db.session.execute(text("ALTER TABLE user ADD UNIQUE INDEX (email)"))
            print("Índice único adicionado à coluna 'email'.")
        else:
            print("Coluna 'email' já existe.")
        
        if 'phone' not in existing_columns:
            db.session.execute(text("ALTER TABLE user ADD COLUMN phone VARCHAR(20)"))
            print("Coluna 'phone' adicionada à tabela User.")
        else:
            print("Coluna 'phone' já existe.")
        
        db.session.commit()
        print("Migração concluída com sucesso!")
    except Exception as e:
        print(f"Erro ao adicionar colunas: {str(e)}")
        db.session.rollback()