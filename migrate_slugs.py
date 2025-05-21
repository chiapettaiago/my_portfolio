#!/usr/bin/env python
from app import app, db, Post, slugify, get_unique_slug
from sqlalchemy import text

print("Iniciando migração para adicionar slugs aos posts...")

# Usar o contexto da aplicação Flask
with app.app_context():
    # 1. Adicionar a coluna slug à tabela Post (se não existir)
    try:
        # Usar text() para o SQL literal
        db.session.execute(text("ALTER TABLE post ADD COLUMN slug VARCHAR(100)"))
        db.session.commit()
        print("Coluna 'slug' adicionada à tabela Post.")
        
        # Após adicionar a coluna, precisamos atualizar o objeto de metadados do SQLAlchemy
        # para que ele saiba da existência da nova coluna
        db.Model.metadata.reflect(db.engine)
    except Exception as e:
        print(f"Erro ao adicionar coluna: {str(e)}")
        db.session.rollback()
        
        # Se o erro for porque a coluna já existe, podemos continuar
        if "Duplicate column" in str(e) or "column exists" in str(e).lower():
            print("A coluna 'slug' já existe. Continuando com a migração...")
        else:
            print("Erro fatal na migração. Abortando.")
            exit(1)

    # 2. Gerar slugs para todos os posts existentes
    try:
        # Obter todos os posts usando SQL direto para evitar problema com a nova coluna
        result = db.session.execute(text("SELECT id, title FROM post"))
        posts = result.fetchall()
        
        print(f"Encontrados {len(posts)} posts para migração.")
        
        # Para cada post, gerar um slug e atualizá-lo no banco
        for i, post in enumerate(posts):
            post_id = post[0]
            title = post[1]
            
            # Gerar um slug único para o título
            slug = get_unique_slug(title)
            
            # Atualizar o post com o novo slug
            db.session.execute(
                text("UPDATE post SET slug = :slug WHERE id = :id"),
                {"slug": slug, "id": post_id}
            )
            
            print(f"[{i+1}/{len(posts)}] Post ID {post_id}: '{title}' → Slug: '{slug}'")
        
        # Adicionar constraint de unicidade após preencher os slugs
        try:
            db.session.execute(text("ALTER TABLE post ADD UNIQUE (slug)"))
            print("Adicionada constraint UNIQUE para a coluna slug.")
        except Exception as e:
            print(f"Aviso: Não foi possível adicionar constraint UNIQUE: {str(e)}")
        
        db.session.commit()
        print("Migração completa! Todos os posts agora possuem slugs.")
    except Exception as e:
        print(f"Erro ao gerar slugs: {str(e)}")
        db.session.rollback()