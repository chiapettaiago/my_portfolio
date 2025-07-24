#!/usr/bin/env python3
import sys
import os

# Adicionar o diretório atual ao path para importar app
sys.path.insert(0, os.path.abspath('.'))

from app import check_scrypt_password, db_firestore

print("Testando sistema de login com senhas scrypt migradas...")
print("=" * 60)

# Usar a conexão Firebase já existente do app
if db_firestore is None:
    print("❌ Firebase não está configurado no app")
    exit(1)

print("✅ Firebase conectado com sucesso!")

# Buscar alguns usuários para testar
users_ref = db_firestore.collection('users')
users = users_ref.limit(3).stream()

print("\nTestando verificação de senha scrypt:")
print("-" * 40)

for user in users:
    user_data = user.to_dict()
    username = user_data.get('username')
    stored_hash = user_data.get('password')
    
    print(f"\nTeste para usuário: {username}")
    print(f"Hash armazenado: {stored_hash[:50]}...")
    
    # Testar com senha vazia (deve falhar)
    result_empty = check_scrypt_password(stored_hash, "")
    print(f"Senha vazia: {'❌ FALHOU' if not result_empty else '⚠️ PASSOU (inesperado)'}")
    
    # Testar com senha incorreta (deve falhar)
    result_wrong = check_scrypt_password(stored_hash, "senha_incorreta")
    print(f"Senha incorreta: {'❌ FALHOU' if not result_wrong else '⚠️ PASSOU (inesperado)'}")
    
    # Como não sabemos as senhas reais, vamos apenas verificar se a função não dá erro
    try:
        # Testar se a função executa sem erro
        test_result = check_scrypt_password(stored_hash, "teste123")
        print(f"Função executa sem erro: ✅ SIM (resultado: {test_result})")
    except Exception as e:
        print(f"Função executa sem erro: ❌ NÃO - Erro: {e}")
    
    break  # Testar apenas o primeiro usuário

print("\n" + "=" * 60)
print("Teste de sistema de login concluído!")
print("\nNOTA: Para testar login real, você precisará:")
print("1. Conhecer uma senha de usuário existente, OU")
print("2. Criar um novo usuário com senha conhecida, OU") 
print("3. Implementar reset de senha para usuários existentes")
