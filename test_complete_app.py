#!/usr/bin/env python3
import requests
import sys

# Configurações do teste
BASE_URL = "http://localhost:7000"
USERNAME = "Iago"
PASSWORD = "admin123"

def test_login():
    """Testa o login via POST request"""
    
    print("=" * 60)
    print("TESTE DE LOGIN AUTOMATIZADO")
    print("=" * 60)
    
    session = requests.Session()
    
    try:
        # 1. Acessar a página de login para obter o formulário
        print("1. Acessando página de login...")
        login_page = session.get(f"{BASE_URL}/login")
        
        if login_page.status_code != 200:
            print(f"✗ Erro ao acessar página de login: {login_page.status_code}")
            return False
        
        print(f"✓ Página de login acessível (Status: {login_page.status_code})")
        
        # 2. Tentar fazer login
        print(f"2. Tentando login com usuário: {USERNAME}")
        login_data = {
            'username': USERNAME,
            'password': PASSWORD
        }
        
        login_response = session.post(f"{BASE_URL}/login", data=login_data, allow_redirects=False)
        
        print(f"Response status: {login_response.status_code}")
        print(f"Response headers: {dict(login_response.headers)}")
        
        # 3. Verificar se o login foi bem-sucedido
        if login_response.status_code == 302:  # Redirect após login bem-sucedido
            redirect_location = login_response.headers.get('Location', '')
            print(f"✓ Login bem-sucedido! Redirecionando para: {redirect_location}")
            
            # 4. Verificar se consegue acessar área administrativa
            print("3. Testando acesso à área administrativa...")
            admin_response = session.get(f"{BASE_URL}/posts")
            
            if admin_response.status_code == 200:
                print("✓ Acesso à área administrativa bem-sucedido!")
                return True
            else:
                print(f"✗ Erro ao acessar área administrativa: {admin_response.status_code}")
                return False
                
        elif login_response.status_code == 200:
            # Se retornou 200, pode ser que o login falhou e voltou para a página de login
            if "Usuário/senha inválidos" in login_response.text:
                print("✗ Login falhou: Usuário/senha inválidos")
            else:
                print("✗ Login falhou: Retornou para página de login")
            return False
        else:
            print(f"✗ Erro inesperado no login: {login_response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("✗ Erro: Não foi possível conectar ao servidor Flask")
        print("Certifique-se de que o servidor está rodando em http://localhost:7000")
        return False
    except Exception as e:
        print(f"✗ Erro inesperado: {str(e)}")
        return False

def test_home_page():
    """Testa se a página inicial está funcionando"""
    print("4. Testando página inicial...")
    
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print("✓ Página inicial funcionando!")
            return True
        else:
            print(f"✗ Erro na página inicial: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Erro ao testar página inicial: {str(e)}")
        return False

if __name__ == "__main__":
    home_ok = test_home_page()
    login_ok = test_login()
    
    print("\n" + "=" * 60)
    print("RESUMO DOS TESTES:")
    print(f"Página inicial: {'✓ OK' if home_ok else '✗ FALHOU'}")
    print(f"Sistema de login: {'✓ OK' if login_ok else '✗ FALHOU'}")
    
    if home_ok and login_ok:
        print("\n🎉 TODOS OS TESTES PASSARAM!")
        print("A migração para Firebase foi concluída com sucesso!")
    else:
        print("\n⚠️  ALGUNS TESTES FALHARAM!")
        print("Verifique os logs acima para mais detalhes.")
    
    print("=" * 60)
