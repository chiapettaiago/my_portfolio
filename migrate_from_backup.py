#!/usr/bin/env python3
"""
Script para migrar dados do backup JSON para Firebase
Este script lê o backup MySQL e migra para Firebase
"""

import os
import sys
import json
import logging
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# Configuração de logging simplificada (sem emojis para evitar problemas de encoding)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration_from_backup.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuração do Firebase
FIREBASE_CREDENTIALS_PATH = 'firebase_credentials.json'

class BackupToFirebaseMigrator:
    def __init__(self, backup_file):
        self.backup_file = backup_file
        self.firebase_db = None
        self.backup_data = None
        self.migration_stats = {
            'users': {'total': 0, 'migrated': 0, 'errors': 0},
            'posts': {'total': 0, 'migrated': 0, 'errors': 0},
            'comments': {'total': 0, 'migrated': 0, 'errors': 0},
            'pageviews': {'total': 0, 'migrated': 0, 'errors': 0},
            'powershell_scripts': {'total': 0, 'migrated': 0, 'errors': 0}
        }

    def load_backup(self):
        """Carrega o arquivo de backup"""
        try:
            with open(self.backup_file, 'r', encoding='utf-8') as f:
                self.backup_data = json.load(f)
            logger.info(f"Backup carregado com sucesso: {self.backup_file}")
            
            # Mostra informações do backup
            logger.info(f"Data do backup: {self.backup_data['backup_date']}")
            logger.info(f"Database: {self.backup_data['database']}")
            
            total_records = sum(table['count'] for table in self.backup_data['tables'].values())
            logger.info(f"Total de registros no backup: {total_records}")
            
            return True
        except Exception as e:
            logger.error(f"Erro ao carregar backup: {str(e)}")
            return False

    def connect_firebase(self):
        """Conecta ao Firebase"""
        try:
            if not os.path.exists(FIREBASE_CREDENTIALS_PATH):
                logger.error(f"Arquivo de credenciais nao encontrado: {FIREBASE_CREDENTIALS_PATH}")
                return False
            
            cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred)
            self.firebase_db = firestore.client()
            logger.info("Conectado ao Firebase com sucesso!")
            return True
        except Exception as e:
            logger.error(f"Erro ao conectar ao Firebase: {str(e)}")
            return False

    def parse_datetime(self, date_str):
        """Converte string ISO para datetime"""
        if not date_str:
            return datetime.now()
        try:
            # Remove timezone info se presente para simplificar
            if 'T' in date_str:
                return datetime.fromisoformat(date_str.replace('Z', ''))
            return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        except:
            return datetime.now()

    def migrate_users(self):
        """Migra usuários do backup para Firebase"""
        logger.info("Iniciando migracao de usuarios...")
        
        if 'user' not in self.backup_data['tables']:
            logger.warning("Tabela 'user' nao encontrada no backup")
            return
        
        users = self.backup_data['tables']['user']['data']
        self.migration_stats['users']['total'] = len(users)
        
        logger.info(f"Encontrados {len(users)} usuarios para migrar")
        
        for user in users:
            try:
                # Prepara os dados do usuário para o Firestore
                user_data = {
                    'username': user.get('username', ''),
                    'password': user.get('password', ''),
                    'fullname': user.get('fullname', ''),
                    'email': user.get('email', ''),
                    'phone': user.get('phone', ''),
                    'role': user.get('role', 'user'),
                    'mysql_id': user.get('id'),
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                
                # Salva no Firebase
                doc_ref = self.firebase_db.collection('users').document()
                doc_ref.set(user_data)
                
                self.migration_stats['users']['migrated'] += 1
                logger.info(f"Usuario migrado: {user.get('username', 'N/A')}")
                
            except Exception as e:
                self.migration_stats['users']['errors'] += 1
                logger.error(f"Erro ao migrar usuario {user.get('username', 'N/A')}: {str(e)}")

    def migrate_posts(self):
        """Migra posts do backup para Firebase"""
        logger.info("Iniciando migracao de posts...")
        
        if 'post' not in self.backup_data['tables']:
            logger.warning("Tabela 'post' nao encontrada no backup")
            return
        
        posts = self.backup_data['tables']['post']['data']
        self.migration_stats['posts']['total'] = len(posts)
        
        logger.info(f"Encontrados {len(posts)} posts para migrar")
        
        for post in posts:
            try:
                # Prepara os dados do post para o Firestore
                post_data = {
                    'title': post.get('title', ''),
                    'slug': post.get('slug', ''),
                    'content': post.get('content', ''),
                    'created_at': self.parse_datetime(post.get('created_at')),
                    'scheduled_for': self.parse_datetime(post.get('scheduled_for')) if post.get('scheduled_for') else None,
                    'is_published': bool(post.get('is_published', False)),
                    'main_image': post.get('main_image'),
                    'user_id': str(post.get('user_id', '')),
                    'mysql_id': post.get('id'),
                    'updated_at': datetime.now()
                }
                
                # Salva no Firebase
                doc_ref = self.firebase_db.collection('posts').document()
                doc_ref.set(post_data)
                
                self.migration_stats['posts']['migrated'] += 1
                logger.info(f"Post migrado: {post.get('title', 'N/A')[:50]}")
                
            except Exception as e:
                self.migration_stats['posts']['errors'] += 1
                logger.error(f"Erro ao migrar post {post.get('title', 'N/A')}: {str(e)}")

    def migrate_pageviews(self):
        """Migra page views do backup para Firebase"""
        logger.info("Iniciando migracao de page views...")
        
        if 'page_view' not in self.backup_data['tables']:
            logger.warning("Tabela 'page_view' nao encontrada no backup")
            return
        
        pageviews = self.backup_data['tables']['page_view']['data']
        self.migration_stats['pageviews']['total'] = len(pageviews)
        
        logger.info(f"Encontradas {len(pageviews)} visualizacoes para migrar")
        
        # Limita a 5000 registros mais recentes para não sobrecarregar
        pageviews_limited = pageviews[:5000] if len(pageviews) > 5000 else pageviews
        logger.info(f"Migrando {len(pageviews_limited)} visualizacoes (limitado)")
        
        for i, pageview in enumerate(pageviews_limited):
            try:
                # Prepara os dados da visualização para o Firestore
                pageview_data = {
                    'path': pageview.get('path', ''),
                    'ip': pageview.get('ip', ''),
                    'user_agent': pageview.get('user_agent', ''),
                    'browser': pageview.get('browser', ''),
                    'device_type': pageview.get('device_type', ''),
                    'referrer': pageview.get('referrer'),
                    'timestamp': self.parse_datetime(pageview.get('timestamp')),
                    'user_id': str(pageview.get('user_id', '')) if pageview.get('user_id') else None,
                    'mysql_id': pageview.get('id')
                }
                
                # Salva no Firebase
                doc_ref = self.firebase_db.collection('pageviews').document()
                doc_ref.set(pageview_data)
                
                self.migration_stats['pageviews']['migrated'] += 1
                
                # Log a cada 100 registros
                if (i + 1) % 100 == 0:
                    logger.info(f"{i + 1} visualizacoes migradas...")
                
            except Exception as e:
                self.migration_stats['pageviews']['errors'] += 1
                logger.error(f"Erro ao migrar pageview {pageview.get('id', 'N/A')}: {str(e)}")

    def migrate_comments(self):
        """Migra comentários do backup para Firebase"""
        logger.info("Iniciando migracao de comentarios...")
        
        if 'comment' not in self.backup_data['tables']:
            logger.warning("Tabela 'comment' nao encontrada no backup")
            return
        
        comments = self.backup_data['tables']['comment']['data']
        self.migration_stats['comments']['total'] = len(comments)
        
        logger.info(f"Encontrados {len(comments)} comentarios para migrar")
        
        for comment in comments:
            try:
                # Prepara os dados do comentário para o Firestore
                comment_data = {
                    'post_id': str(comment.get('post_id', '')),
                    'user_id': str(comment.get('user_id', '')),
                    'content': comment.get('content', ''),
                    'created_at': self.parse_datetime(comment.get('created_at')),
                    'mysql_id': comment.get('id'),
                    'updated_at': datetime.now()
                }
                
                # Salva no Firebase
                doc_ref = self.firebase_db.collection('comments').document()
                doc_ref.set(comment_data)
                
                self.migration_stats['comments']['migrated'] += 1
                logger.info(f"Comentario migrado: ID {comment.get('id', 'N/A')}")
                
            except Exception as e:
                self.migration_stats['comments']['errors'] += 1
                logger.error(f"Erro ao migrar comentario {comment.get('id', 'N/A')}: {str(e)}")

    def print_migration_summary(self):
        """Exibe um resumo da migração"""
        logger.info("\n" + "="*60)
        logger.info("RESUMO DA MIGRACAO")
        logger.info("="*60)
        
        total_records = 0
        total_migrated = 0
        total_errors = 0
        
        for table, stats in self.migration_stats.items():
            if stats['total'] > 0:  # Só mostra tabelas com dados
                logger.info(f"{table.upper()}:")
                logger.info(f"   Total: {stats['total']}")
                logger.info(f"   Migrados: {stats['migrated']}")
                logger.info(f"   Erros: {stats['errors']}")
                logger.info(f"   Taxa de sucesso: {(stats['migrated']/stats['total']*100) if stats['total'] > 0 else 0:.1f}%")
                logger.info("")
                
                total_records += stats['total']
                total_migrated += stats['migrated']
                total_errors += stats['errors']
        
        logger.info(f"TOTAIS GERAIS:")
        logger.info(f"   Total de registros: {total_records}")
        logger.info(f"   Migrados com sucesso: {total_migrated}")
        logger.info(f"   Erros: {total_errors}")
        logger.info(f"   Taxa de sucesso geral: {(total_migrated/total_records*100) if total_records > 0 else 0:.1f}%")
        logger.info("="*60)

    def run_migration(self):
        """Executa a migração completa"""
        logger.info("Iniciando migracao do backup para Firebase...")
        
        # Carrega o backup
        if not self.load_backup():
            return False
        
        # Conecta ao Firebase
        if not self.connect_firebase():
            return False
        
        # Executa as migrações
        self.migrate_users()
        self.migrate_posts()
        self.migrate_comments()
        self.migrate_pageviews()
        
        # Exibe o resumo
        self.print_migration_summary()
        
        logger.info("Migracao concluida!")
        return True

def main():
    """Função principal"""
    print("Migracao MySQL Backup -> Firebase")
    print("=" * 40)
    
    # Procura arquivo de backup mais recente
    backup_files = [f for f in os.listdir('.') if f.startswith('mysql_backup_') and f.endswith('.json')]
    
    if not backup_files:
        print("Nenhum arquivo de backup encontrado!")
        print("Execute primeiro: python backup_mysql.py")
        return
    
    # Usa o backup mais recente
    backup_file = sorted(backup_files, reverse=True)[0]
    print(f"Usando arquivo de backup: {backup_file}")
    
    # Verifica se o arquivo de credenciais existe
    if not os.path.exists(FIREBASE_CREDENTIALS_PATH):
        print(f"Arquivo de credenciais nao encontrado: {FIREBASE_CREDENTIALS_PATH}")
        print("Por favor, configure suas credenciais do Firebase antes de continuar.")
        print("\nPara obter as credenciais:")
        print("1. Acesse https://console.firebase.google.com/")
        print("2. Selecione o projeto 'portfolio-204dd'")
        print("3. Va em Configuracoes -> Contas de servico")
        print("4. Clique em 'Gerar nova chave privada'")
        print("5. Substitua o conteudo do arquivo firebase_credentials.json")
        return
    
    # Pergunta se o usuário quer continuar
    response = input("\nEsta operacao ira migrar dados do backup para o Firebase. Continuar? (s/N): ")
    if response.lower() not in ['s', 'sim', 'y', 'yes']:
        print("Migracao cancelada pelo usuario.")
        return
    
    # Executa a migração
    migrator = BackupToFirebaseMigrator(backup_file)
    success = migrator.run_migration()
    
    if success:
        print("\nMigracao concluida com sucesso!")
        print("Verifique o arquivo 'migration_from_backup.log' para detalhes completos.")
    else:
        print("\nMigracao falhou. Verifique os logs para mais detalhes.")

if __name__ == "__main__":
    main()
