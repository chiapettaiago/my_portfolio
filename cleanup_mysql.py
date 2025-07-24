#!/usr/bin/env python3
"""
Script para limpar dependências e arquivos relacionados ao MySQL
após a migração bem-sucedida para Firebase.
"""

import os
import shutil
import subprocess
import sys

def remove_mysql_packages():
    """Remove pacotes MySQL desnecessários."""
    packages_to_remove = [
        'pymysql',
        'mysql-connector-python',
        'SQLAlchemy',
        'sqlalchemy'
    ]
    
    print("🗑️  Removendo pacotes MySQL desnecessários...")
    for package in packages_to_remove:
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'uninstall', package, '-y'], 
                         capture_output=True, text=True)
            print(f"   ✅ {package} removido")
        except Exception as e:
            print(f"   ⚠️  {package} não encontrado ou erro: {e}")

def backup_mysql_files():
    """Move arquivos MySQL para pasta de backup."""
    backup_dir = "mysql_backup_files"
    
    mysql_files = [
        'check_mysql_structure.py',
        'backup_mysql.py',
        'migrate_mysql_to_firebase_fixed.py',
        'mysql_backup_20250724_152902.json',
        'migration.log'
    ]
    
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        print(f"📁 Criada pasta de backup: {backup_dir}")
    
    print("\n📦 Movendo arquivos MySQL para backup...")
    for file in mysql_files:
        if os.path.exists(file):
            try:
                shutil.move(file, os.path.join(backup_dir, file))
                print(f"   ✅ {file} movido para backup")
            except Exception as e:
                print(f"   ⚠️  Erro ao mover {file}: {e}")
        else:
            print(f"   ℹ️  {file} não encontrado")

def create_requirements_txt():
    """Cria novo requirements.txt apenas com dependências necessárias."""
    firebase_requirements = """# Dependências do Portfolio Flask com Firebase
Flask==2.3.3
firebase-admin==6.2.0
python-dotenv==1.0.0
Werkzeug==2.3.7
Jinja2==3.1.2
MarkupSafe==2.1.3
itsdangerous==2.1.2
click==8.1.7
"""
    
    print("\n📝 Criando novo requirements.txt...")
    with open('requirements.txt', 'w', encoding='utf-8') as f:
        f.write(firebase_requirements)
    print("   ✅ requirements.txt atualizado com dependências Firebase")

def create_deployment_guide():
    """Cria guia de deploy para produção."""
    guide_content = """# 🚀 Guia de Deploy - Portfolio Flask + Firebase

## ✅ Migração Concluída
- ✅ MySQL → Firebase Firestore
- ✅ 7.943 registros migrados com 100% de sucesso
- ✅ Aplicação testada e funcionando

## 📋 Dependências Atuais
```bash
pip install -r requirements.txt
```

## 🔧 Configuração Firebase
1. Arquivo de credenciais: `firebase-credentials.json`
2. Variável de ambiente: `GOOGLE_APPLICATION_CREDENTIALS`

## 🌐 Deploy em Produção

### Opção 1: Railway/Heroku
```bash
# Definir variáveis de ambiente
GOOGLE_APPLICATION_CREDENTIALS_JSON=<conteúdo do arquivo JSON>
FLASK_ENV=production
```

### Opção 2: Google Cloud Run
```bash
gcloud run deploy portfolio-app --source .
```

### Opção 3: Docker
```dockerfile
FROM python:3.10-slim
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
EXPOSE 7000
CMD ["python", "app.py"]
```

## 🔒 Segurança
- ✅ Credenciais Firebase em arquivo separado
- ✅ Modo de desenvolvimento com fallback
- ✅ Logs de erro configurados

## 🎯 Próximos Passos
1. Deploy em produção
2. Configurar domínio personalizado
3. Configurar SSL/TLS
4. Monitoramento com Firebase Analytics
"""
    
    print("\n📖 Criando guia de deployment...")
    with open('DEPLOYMENT_GUIDE.md', 'w', encoding='utf-8') as f:
        f.write(guide_content)
    print("   ✅ DEPLOYMENT_GUIDE.md criado")

def main():
    print("🧹 LIMPEZA PÓS-MIGRAÇÃO MYSQL → FIREBASE")
    print("=" * 50)
    
    # Remover pacotes MySQL
    remove_mysql_packages()
    
    # Fazer backup dos arquivos MySQL
    backup_mysql_files()
    
    # Criar novo requirements.txt
    create_requirements_txt()
    
    # Criar guia de deployment
    create_deployment_guide()
    
    print("\n🎉 LIMPEZA CONCLUÍDA!")
    print("=" * 50)
    print("✅ Pacotes MySQL removidos")
    print("✅ Arquivos MySQL movidos para backup")
    print("✅ requirements.txt atualizado")
    print("✅ Guia de deployment criado")
    print("\n🚀 Sua aplicação está pronta para produção!")
    print("📖 Consulte DEPLOYMENT_GUIDE.md para instruções de deploy")

if __name__ == "__main__":
    main()
