#!/usr/bin/env python3
import firebase_admin
from firebase_admin import credentials, firestore
import json

# Inicializar Firebase
cred = credentials.Certificate('firebase-credentials.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# Buscar usuário admin
print("Procurando usuário admin...")
users_ref = db.collection('users')

# Buscar por username admin ou role admin
admin_users = []

# Buscar por role admin
admin_role_query = users_ref.where('role', '==', 'admin').stream()
for user in admin_role_query:
    user_data = user.to_dict()
    admin_users.append({
        'id': user.id,
        'username': user_data.get('username'),
        'role': user_data.get('role'),
        'password_hash': user_data.get('password', '')[:50] + '...'
    })

# Buscar por username admin
admin_username_query = users_ref.where('username', '==', 'admin').stream()
for user in admin_username_query:
    user_data = user.to_dict()
    # Evitar duplicatas
    if user.id not in [u['id'] for u in admin_users]:
        admin_users.append({
            'id': user.id,
            'username': user_data.get('username'),
            'role': user_data.get('role'),
            'password_hash': user_data.get('password', '')[:50] + '...'
        })

if admin_users:
    print(f"Encontrados {len(admin_users)} usuários admin:")
    for i, user in enumerate(admin_users):
        print(f"{i+1}. ID: {user['id']}")
        print(f"   Username: {user['username']}")
        print(f"   Role: {user['role']}")
        print(f"   Password hash: {user['password_hash']}")
        print("-" * 40)
else:
    print("Nenhum usuário admin encontrado.")
    print("Vamos verificar alguns usuários para encontrar um padrão...")
    
    # Buscar qualquer usuário para análise
    any_users = users_ref.limit(3).stream()
    for user in any_users:
        user_data = user.to_dict()
        print(f"ID: {user.id}")
        print(f"Username: {user_data.get('username')}")
        print(f"Role: {user_data.get('role')}")
        print(f"Password hash: {user_data.get('password', '')[:50]}...")
        print("-" * 40)
