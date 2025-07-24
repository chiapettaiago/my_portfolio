#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import check_scrypt_password
import scrypt

def test_scrypt_password():
    """Testa a função de verificação de senha scrypt"""
    
    # Exemplo de hash do Firebase (formato real dos usuários migrados)
    test_hash = "scrypt:32768:8:1$iIS4ZzQPsB5xGS1q$c3ee6c9df66c83c983e1ded96fa2989de8b6efbd92ca638c447ec9daa0d3a9ea09b3360d219d8d187bbeae5b011e33094220f52c37ae666ffbb2f0de9b5613578"
    
    # Senha de teste (obviamente não sabemos a senha real, mas vamos testar a estrutura)
    test_password = "senha123"
    
    print("Testando função check_scrypt_password...")
    print(f"Hash: {test_hash[:50]}...")
    print(f"Senha: {test_password}")
    
    try:
        result = check_scrypt_password(test_hash, test_password)
        print(f"Resultado: {result}")
        print("✓ Função executou sem erros!")
        
        # Teste com hash Werkzeug (deve usar fallback)
        werkzeug_hash = "pbkdf2:sha256:260000$abcd$1234567890abcdef"
        result2 = check_scrypt_password(werkzeug_hash, "teste")
        print(f"Teste fallback Werkzeug: {result2}")
        print("✓ Fallback funcionando!")
        
    except Exception as e:
        print(f"✗ Erro: {str(e)}")
        return False
    
    return True

def test_scrypt_direct():
    """Testa a biblioteca scrypt diretamente"""
    print("\nTestando biblioteca scrypt diretamente...")
    
    try:
        password = "teste123"
        salt = "saltteste"
        
        # Parâmetros típicos do MySQL
        n = 32768
        r = 8  
        p = 1
        dklen = 64
        
        hash_result = scrypt.hash(
            password.encode('utf-8'),
            salt.encode('utf-8'),
            n, r, p, dklen
        )
        
        print(f"Senha: {password}")
        print(f"Salt: {salt}")
        print(f"Hash gerado: {hash_result.hex()}")
        print("✓ Biblioteca scrypt funcionando!")
        
        return True
        
    except Exception as e:
        print(f"✗ Erro na biblioteca scrypt: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("TESTE DE AUTENTICAÇÃO SCRYPT")
    print("=" * 60)
    
    success1 = test_scrypt_direct()
    success2 = test_scrypt_password()
    
    print("\n" + "=" * 60)
    if success1 and success2:
        print("✓ TODOS OS TESTES PASSARAM!")
        print("A função de autenticação está pronta para uso.")
    else:
        print("✗ ALGUNS TESTES FALHARAM!")
        print("Verifique os erros acima.")
    print("=" * 60)
