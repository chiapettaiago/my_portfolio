import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate('firebase-credentials.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

users = db.collection('users').where('username', '==', 'chiapettaiago').stream()
updated = False
for doc in users:
    db.collection('users').document(doc.id).update({'role': 'admin'})
    print(f'Usuário {doc.id} atualizado para admin')
    updated = True

print('Status:', 'OK' if updated else 'Usuário não encontrado')
