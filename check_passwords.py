#!/usr/bin/env python3
import firebase_admin
from firebase_admin import credentials, firestore
import json

# Inicializar Firebase
cred = credentials.Certificate('firebase-credentials.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# Buscar alguns usuários para verificar o formato da senha
users_ref = db.collection('users')
users = users_ref.limit(5).stream()

print("Verificando formato das senhas dos usuários migrados:")
print("=" * 60)

for user in users:
    user_data = user.to_dict()
    password_hash = user_data.get('password', '')
    
    print(f'ID: {user.id}')
    print(f'Username: {user_data.get("username")}')
    print(f'Password hash (primeiros 50 chars): {password_hash[:50]}...')
    print(f'Password hash total length: {len(password_hash)}')
    
    # Verificar se é scrypt
    if password_hash.startswith('scrypt:'):
        print('Formato: scrypt (MySQL)')
        parts = password_hash.split(':')
        print(f'Partes scrypt: {parts[:4]}')  # Só os primeiros 4 elementos
    elif password_hash.startswith('pbkdf2:'):
        print('Formato: pbkdf2 (Werkzeug)')
    else:
        print('Formato: desconhecido')
    
    print("-" * 40)
