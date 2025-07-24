#!/usr/bin/env python3
import firebase_admin
from firebase_admin import credentials, firestore
from werkzeug.security import generate_password_hash

try:
    # Inicializar Firebase
    cred = credentials.Certificate('firebase-credentials.json')
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase conectado com sucesso!")

    # Encontrar um usuário admin
    users_ref = db.collection('users')
    admin_query = users_ref.where('role', '==', 'admin').limit(1)
    admin_users = list(admin_query.stream())
    
    if not admin_users:
        print("Nenhum usuário admin encontrado!")
        exit(1)
    
    admin_user = admin_users[0]
    admin_data = admin_user.to_dict()
    
    print(f"Usuário admin encontrado:")
    print(f"  ID: {admin_user.id}")
    print(f"  Username: {admin_data.get('username')}")
    print(f"  Role: {admin_data.get('role')}")
    
    # Gerar nova senha usando Werkzeug (compatível)
    new_password = "admin123"
    new_hash = generate_password_hash(new_password)
    
    print(f"\nDefinindo nova senha: {new_password}")
    print(f"Novo hash Werkzeug: {new_hash[:50]}...")
    
    # Atualizar a senha no Firebase
    admin_ref = db.collection('users').document(admin_user.id)
    admin_ref.update({
        'password': new_hash
    })
    
    print(f"\n✓ Senha atualizada com sucesso!")
    print(f"Agora você pode fazer login com:")
    print(f"  Username: {admin_data.get('username')}")
    print(f"  Password: {new_password}")
    
except Exception as e:
    print(f"Erro: {str(e)}")
    import traceback
    traceback.print_exc()
