#!/usr/bin/env python3
"""
Script de migração de MySQL para Firebase
Este script conecta ao banco MySQL existente e migra todos os dados para o Firebase Firestore.
"""

import os
import sys
import logging
from datetime import datetime
import pymysql
import firebase_admin
from firebase_admin import credentials, firestore

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configurações do MySQL
MYSQL_CONFIG = {
    'host': '144.22.178.234',
    'port': 3306,
    'user': 'portfolio',
    'password': '8MEPBTxaaZRaKxs8',
    'database': 'portfolio',
    'charset': 'utf8mb4'
}

# Configuração do Firebase
FIREBASE_CREDENTIALS_PATH = 'firebase_credentials.json'

class MySQLToFirebaseMigrator:
    def __init__(self):
        self.mysql_conn = None
        self.firebase_db = None
        self.migration_stats = {
            'users': {'total': 0, 'migrated': 0, 'errors': 0},
            'posts': {'total': 0, 'migrated': 0, 'errors': 0},
            'comments': {'total': 0, 'migrated': 0, 'errors': 0},
            'pageviews': {'total': 0, 'migrated': 0, 'errors': 0},
            'powershell_scripts': {'total': 0, 'migrated': 0, 'errors': 0}
        }

    def connect_mysql(self):
        """Conecta ao banco MySQL"""
        try:
            self.mysql_conn = pymysql.connect(**MYSQL_CONFIG)
            logger.info("✅ Conectado ao MySQL com sucesso!")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao conectar ao MySQL: {str(e)}")
            return False

    def connect_firebase(self):
        """Conecta ao Firebase"""
        try:
            if not os.path.exists(FIREBASE_CREDENTIALS_PATH):
                logger.error(f"❌ Arquivo de credenciais não encontrado: {FIREBASE_CREDENTIALS_PATH}")
                return False
            
            cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred)
            self.firebase_db = firestore.client()
            logger.info("✅ Conectado ao Firebase com sucesso!")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao conectar ao Firebase: {str(e)}")
            return False

    def get_mysql_tables(self):
        """Lista todas as tabelas do MySQL"""
        try:
            with self.mysql_conn.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                tables = [row[0] for row in cursor.fetchall()]
                logger.info(f"📋 Tabelas encontradas no MySQL: {tables}")
                return tables
        except Exception as e:
            logger.error(f"❌ Erro ao listar tabelas: {str(e)}")
            return []    def migrate_users(self):
        """Migra usuários do MySQL para Firebase"""
        logger.info("👥 Iniciando migração de usuários...")
        
        try:
            with self.mysql_conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # Verifica se a tabela user existe (sem 's')
                cursor.execute("SHOW TABLES LIKE 'user'")
                if not cursor.fetchone():
                    logger.warning("⚠️ Tabela 'user' não encontrada no MySQL")
                    return
                
                # Busca todos os usuários
                cursor.execute("SELECT * FROM user")
                users = cursor.fetchall()
                self.migration_stats['users']['total'] = len(users)
                
                logger.info(f"📊 Encontrados {len(users)} usuários para migrar")
                
                # Migra cada usuário
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
                            'mysql_id': user.get('id'),  # Preserva o ID original para referências
                            'created_at': datetime.now(),
                            'updated_at': datetime.now()
                        }
                        
                        # Salva no Firebase
                        doc_ref = self.firebase_db.collection('users').document()
                        doc_ref.set(user_data)
                        
                        self.migration_stats['users']['migrated'] += 1
                        logger.info(f"✅ Usuário migrado: {user.get('username', 'N/A')}")
                        
                    except Exception as e:
                        self.migration_stats['users']['errors'] += 1
                        logger.error(f"❌ Erro ao migrar usuário {user.get('username', 'N/A')}: {str(e)}")
                        
        except Exception as e:
            logger.error(f"❌ Erro na migração de usuários: {str(e)}")    def migrate_posts(self):
        """Migra posts do MySQL para Firebase"""
        logger.info("📝 Iniciando migração de posts...")
        
        try:
            with self.mysql_conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # Verifica se a tabela post existe (sem 's')
                cursor.execute("SHOW TABLES LIKE 'post'")
                if not cursor.fetchone():
                    logger.warning("⚠️ Tabela 'post' não encontrada no MySQL")
                    return
                
                # Busca todos os posts
                cursor.execute("SELECT * FROM post")
                posts = cursor.fetchall()
                self.migration_stats['posts']['total'] = len(posts)
                
                logger.info(f"📊 Encontrados {len(posts)} posts para migrar")
                
                # Migra cada post
                for post in posts:
                    try:
                        # Prepara os dados do post para o Firestore
                        post_data = {
                            'title': post.get('title', ''),
                            'slug': post.get('slug', ''),
                            'content': post.get('content', ''),
                            'created_at': post.get('created_at', datetime.now()),
                            'scheduled_for': post.get('scheduled_for'),
                            'is_published': bool(post.get('is_published', False)),
                            'main_image': post.get('main_image'),
                            'user_id': str(post.get('user_id', '')),
                            'mysql_id': post.get('id'),  # Preserva o ID original
                            'updated_at': datetime.now()
                        }
                        
                        # Salva no Firebase
                        doc_ref = self.firebase_db.collection('posts').document()
                        doc_ref.set(post_data)
                        
                        self.migration_stats['posts']['migrated'] += 1
                        logger.info(f"✅ Post migrado: {post.get('title', 'N/A')}")
                        
                    except Exception as e:
                        self.migration_stats['posts']['errors'] += 1
                        logger.error(f"❌ Erro ao migrar post {post.get('title', 'N/A')}: {str(e)}")
                        
        except Exception as e:
            logger.error(f"❌ Erro na migração de posts: {str(e)}")    def migrate_comments(self):
        """Migra comentários do MySQL para Firebase"""
        logger.info("💬 Iniciando migração de comentários...")
        
        try:
            with self.mysql_conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # Verifica se a tabela comment existe (sem 's')
                cursor.execute("SHOW TABLES LIKE 'comment'")
                if not cursor.fetchone():
                    logger.warning("⚠️ Tabela 'comment' não encontrada no MySQL")
                    return
                
                # Busca todos os comentários
                cursor.execute("SELECT * FROM comment")
                comments = cursor.fetchall()
                self.migration_stats['comments']['total'] = len(comments)
                
                logger.info(f"📊 Encontrados {len(comments)} comentários para migrar")
                
                # Migra cada comentário
                for comment in comments:
                    try:
                        # Prepara os dados do comentário para o Firestore
                        comment_data = {
                            'post_id': str(comment.get('post_id', '')),
                            'user_id': str(comment.get('user_id', '')),
                            'content': comment.get('content', ''),
                            'created_at': comment.get('created_at', datetime.now()),
                            'mysql_id': comment.get('id'),  # Preserva o ID original
                            'updated_at': datetime.now()
                        }
                        
                        # Salva no Firebase
                        doc_ref = self.firebase_db.collection('comments').document()
                        doc_ref.set(comment_data)
                        
                        self.migration_stats['comments']['migrated'] += 1
                        logger.info(f"✅ Comentário migrado: ID {comment.get('id', 'N/A')}")
                        
                    except Exception as e:
                        self.migration_stats['comments']['errors'] += 1
                        logger.error(f"❌ Erro ao migrar comentário {comment.get('id', 'N/A')}: {str(e)}")
                        
        except Exception as e:
            logger.error(f"❌ Erro na migração de comentários: {str(e)}")    def migrate_pageviews(self):
        """Migra visualizações de página do MySQL para Firebase"""
        logger.info("👀 Iniciando migração de page views...")
        
        try:
            with self.mysql_conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # Verifica se a tabela page_view existe
                cursor.execute("SHOW TABLES LIKE 'page_view'")
                if not cursor.fetchone():
                    logger.warning("⚠️ Tabela 'page_view' não encontrada no MySQL")
                    return
                
                # Busca todas as visualizações (limitando para evitar sobrecarga)
                cursor.execute("SELECT * FROM page_view ORDER BY timestamp DESC LIMIT 10000")
                pageviews = cursor.fetchall()
                self.migration_stats['pageviews']['total'] = len(pageviews)
                
                logger.info(f"📊 Encontradas {len(pageviews)} visualizações para migrar")
                
                # Migra cada visualização
                for pageview in pageviews:
                    try:
                        # Prepara os dados da visualização para o Firestore
                        pageview_data = {
                            'path': pageview.get('path', ''),
                            'ip': pageview.get('ip', ''),
                            'user_agent': pageview.get('user_agent', ''),
                            'browser': pageview.get('browser', ''),
                            'device_type': pageview.get('device_type', ''),
                            'referrer': pageview.get('referrer'),
                            'timestamp': pageview.get('timestamp', datetime.now()),
                            'user_id': str(pageview.get('user_id', '')) if pageview.get('user_id') else None,
                            'mysql_id': pageview.get('id')  # Preserva o ID original
                        }
                        
                        # Salva no Firebase
                        doc_ref = self.firebase_db.collection('pageviews').document()
                        doc_ref.set(pageview_data)
                        
                        self.migration_stats['pageviews']['migrated'] += 1
                        
                        # Log a cada 100 registros para não sobrecarregar
                        if self.migration_stats['pageviews']['migrated'] % 100 == 0:
                            logger.info(f"✅ {self.migration_stats['pageviews']['migrated']} visualizações migradas...")
                        
                    except Exception as e:
                        self.migration_stats['pageviews']['errors'] += 1
                        logger.error(f"❌ Erro ao migrar pageview {pageview.get('id', 'N/A')}: {str(e)}")
                        
        except Exception as e:
            logger.error(f"❌ Erro na migração de pageviews: {str(e)}")    def migrate_powershell_scripts(self):
        """Migra scripts PowerShell do MySQL para Firebase"""
        logger.info("⚡ Iniciando migração de scripts PowerShell...")
        
        try:
            with self.mysql_conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # Verifica se a tabela power_shell_script existe
                cursor.execute("SHOW TABLES LIKE 'power_shell_script'")
                if not cursor.fetchone():
                    logger.warning("⚠️ Tabela 'power_shell_script' não encontrada no MySQL")
                    return
                
                # Busca todos os scripts
                cursor.execute("SELECT * FROM power_shell_script")
                scripts = cursor.fetchall()
                self.migration_stats['powershell_scripts']['total'] = len(scripts)
                
                logger.info(f"📊 Encontrados {len(scripts)} scripts PowerShell para migrar")
                
                # Migra cada script
                for script in scripts:
                    try:
                        # Prepara os dados do script para o Firestore
                        script_data = {
                            'token': script.get('token', ''),
                            'script': script.get('script', ''),
                            'description': script.get('description', ''),
                            'created_at': script.get('created_at', datetime.now()),
                            'expires_at': script.get('expires_at'),
                            'created_by': str(script.get('created_by', '')),
                            'access_count': int(script.get('access_count', 0)),
                            'last_accessed': script.get('last_accessed'),
                            'mysql_id': script.get('id'),  # Preserva o ID original
                            'updated_at': datetime.now()
                        }
                        
                        # Salva no Firebase
                        doc_ref = self.firebase_db.collection('powershellscripts').document()
                        doc_ref.set(script_data)
                        
                        self.migration_stats['powershell_scripts']['migrated'] += 1
                        logger.info(f"✅ Script PowerShell migrado: {script.get('description', 'N/A')}")
                        
                    except Exception as e:
                        self.migration_stats['powershell_scripts']['errors'] += 1
                        logger.error(f"❌ Erro ao migrar script {script.get('token', 'N/A')}: {str(e)}")
                        
        except Exception as e:
            logger.error(f"❌ Erro na migração de scripts PowerShell: {str(e)}")

    def print_migration_summary(self):
        """Exibe um resumo da migração"""
        logger.info("\n" + "="*60)
        logger.info("📊 RESUMO DA MIGRAÇÃO")
        logger.info("="*60)
        
        total_records = 0
        total_migrated = 0
        total_errors = 0
        
        for table, stats in self.migration_stats.items():
            logger.info(f"📋 {table.upper()}:")
            logger.info(f"   Total: {stats['total']}")
            logger.info(f"   Migrados: {stats['migrated']}")
            logger.info(f"   Erros: {stats['errors']}")
            logger.info(f"   Taxa de sucesso: {(stats['migrated']/stats['total']*100) if stats['total'] > 0 else 0:.1f}%")
            logger.info("")
            
            total_records += stats['total']
            total_migrated += stats['migrated']
            total_errors += stats['errors']
        
        logger.info(f"🔢 TOTAIS GERAIS:")
        logger.info(f"   Total de registros: {total_records}")
        logger.info(f"   Migrados com sucesso: {total_migrated}")
        logger.info(f"   Erros: {total_errors}")
        logger.info(f"   Taxa de sucesso geral: {(total_migrated/total_records*100) if total_records > 0 else 0:.1f}%")
        logger.info("="*60)

    def run_migration(self):
        """Executa a migração completa"""
        logger.info("🚀 Iniciando migração de MySQL para Firebase...")
        
        # Conecta aos bancos
        if not self.connect_mysql():
            return False
        
        if not self.connect_firebase():
            return False
        
        # Lista as tabelas disponíveis
        tables = self.get_mysql_tables()
        
        # Executa as migrações
        self.migrate_users()
        self.migrate_posts()
        self.migrate_comments()
        self.migrate_pageviews()
        self.migrate_powershell_scripts()
        
        # Exibe o resumo
        self.print_migration_summary()
        
        # Fecha conexões
        if self.mysql_conn:
            self.mysql_conn.close()
            logger.info("🔐 Conexão MySQL fechada")
        
        logger.info("✅ Migração concluída!")
        return True

def main():
    """Função principal"""
    print("🔄 Script de Migração MySQL → Firebase")
    print("=" * 50)
    
    # Verifica se o arquivo de credenciais existe
    if not os.path.exists(FIREBASE_CREDENTIALS_PATH):
        print(f"❌ Arquivo de credenciais não encontrado: {FIREBASE_CREDENTIALS_PATH}")
        print("Por favor, configure suas credenciais do Firebase antes de continuar.")
        return
    
    # Pergunta se o usuário quer continuar
    response = input("⚠️  Esta operação irá migrar dados do MySQL para o Firebase. Continuar? (s/N): ")
    if response.lower() not in ['s', 'sim', 'y', 'yes']:
        print("❌ Migração cancelada pelo usuário.")
        return
    
    # Executa a migração
    migrator = MySQLToFirebaseMigrator()
    success = migrator.run_migration()
    
    if success:
        print("\n🎉 Migração concluída com sucesso!")
        print("📄 Verifique o arquivo 'migration.log' para detalhes completos.")
    else:
        print("\n❌ Migração falhou. Verifique os logs para mais detalhes.")

if __name__ == "__main__":
    main()
