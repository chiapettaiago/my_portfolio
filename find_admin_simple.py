#!/usr/bin/env python3
import firebase_admin
from firebase_admin import credentials, firestore
import json

try:
    # Inicializar Firebase
    cred = credentials.Certificate('firebase-credentials.json')
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase conectado com sucesso!")

    # Buscar todos os usuários
    users_ref = db.collection('users')
    users = list(users_ref.stream())
    print(f"Total de usuários encontrados: {len(users)}")
    
    admin_count = 0
    for user in users:
        user_data = user.to_dict()
        username = user_data.get('username', 'N/A')
        role = user_data.get('role', 'user')
        
        if role == 'admin':
            admin_count += 1
            print(f"ADMIN ENCONTRADO:")
            print(f"  ID: {user.id}")
            print(f"  Username: {username}")
            print(f"  Role: {role}")
            print(f"  Password hash: {user_data.get('password', 'N/A')[:50]}...")
            print("-" * 50)
    
    print(f"Total de administradores: {admin_count}")
    
    if admin_count == 0:
        print("Nenhum admin encontrado. Mostrando primeiros 5 usuários:")
        for i, user in enumerate(users[:5]):
            user_data = user.to_dict()
            print(f"{i+1}. Username: {user_data.get('username', 'N/A')} - Role: {user_data.get('role', 'user')}")

except Exception as e:
    print(f"Erro: {str(e)}")
    import traceback
    traceback.print_exc()
