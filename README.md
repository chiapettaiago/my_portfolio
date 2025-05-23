# Chiapetta Dev Portfolio & Blog

Um site pessoal e blog desenvolvido em **Flask** para apresentar o portfólio, projetos e artigos técnicos de Iago Filgueiras Chiapetta.

## Índice

- [Descrição](#descrição)
- [Funcionalidades](#funcionalidades)
- [Tecnologias Utilizadas](#tecnologias-utilizadas)
- [Pré-requisitos](#pré-requisitos)
- [Instalação e Configuração](#instalação-e-configuração)
- [Variáveis de Ambiente](#variáveis-de-ambiente)
- [Migrações de Banco de Dados](#migrações-de-banco-de-dados)
- [Execução](#execução)
- [Uso com Docker](#uso-com-docker)
- [Estrutura de Pastas](#estrutura-de-pastas)
- [Contribuição](#contribuição)
- [Licença](#licença)

## Descrição

Este projeto contém:

- Página inicial com apresentação pessoal e destaques de habilidades.
- Seção de projetos com links externos.
- Blog com criação, edição e agendamento de posts (Markdown/HTML).
- Sistema de comentários com autenticação de usuários.
- Dashboard de analytics próprio para monitoramento de visualizações.
- Cache de dados com **Memcached** para otimizar consultas.
- RSS feed para última atualizações.
- PWA com service worker (`sw.js`).

## Funcionalidades

- CRUD de posts (publicação imediata ou agendada).
- Upload de imagem principal para cada post.
- Autenticação de usuário (login, registro, logout).
- Dashboard de analytics (visitas, dispositivos, páginas mais acessadas).
- Cache de "posts recentes" e "postos individuais".
- RSS feed ([`/feed`]).
- Manifest e service worker para suporte PWA.

## Tecnologias Utilizadas

- Python 3.10
- Flask
- Flask-Login
- Flask-SQLAlchemy
- MySQL (MariaDB)
- Memcached
- Bootstrap 5
- Chart.js
- Jinja2
- Docker & Docker Compose

## Pré-requisitos

- Python 3.10+
- pip
- MySQL/MariaDB
- Memcached
- (Opcional) Docker & Docker Compose

## Instalação e Configuração

1. Clone este repositório:

   ```bash
   git clone https://github.com/chiapettaiago/portfolio.git
   cd portfolio
   ```

2. Crie e ative um ambiente virtual:

   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate   # Windows
   source .venv/bin/activate   # Linux/macOS
   ```

3. Instale as dependências:

   ```bash
   pip install -r requirements.txt
   ```

4. Copie o arquivo de exemplo de variáveis de ambiente e ajuste:

   ```bash
   copy .env.example .env       # Windows
   cp .env.example .env        # Linux/macOS
   ```

5. Configure as credenciais de banco de dados e Memcached no `.env`.

## Variáveis de Ambiente

- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_DB`
- `MEMCACHED_HOST`
- `MEMCACHED_PORT`
- `SECRET_KEY`

## Migrações de Banco de Dados

Este projeto inclui scripts para atualização de slugs e campos de usuário. Execute:

```bash
python migrate_slugs.py
python migrate_user_fields.py
```

## Execução

Inicie o servidor Flask:

```bash
flask run --host=0.0.0.0 --port=7000
```

Acesse em `http://localhost:7000`.

## Uso com Docker

1. Construa e suba contêineres:

   ```bash
   docker-compose up --build -d
   ```

2. Logs:

   ```bash
   docker-compose logs -f
   ```

3. Parar e remover:

   ```bash
   docker-compose down
   ```

## Estrutura de Pastas

```
/my_portfolio
├── app.py               # Aplicação Flask
├── requirements.txt     # Dependências Python
├── Dockerfile
├── docker-compose.yml
├── migrate_slugs.py     # Script de migração de slugs
├── migrate_user_fields.py
├── static/              # CSS, JS, imagens, uploads
├── templates/           # Templates Jinja2
└── README.md            # Documentação (este arquivo)
```

## Contribuição

Contribuições são bem-vindas! Abra issues e pull requests para melhorias ou correções.

## Licença

Este projeto está licenciado sob a [MIT License](LICENSE).
