# Usando Python 3.9 como base
FROM python:3.9-slim

# Definindo variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Configurações de rede para acessar serviços do host
ENV MYSQL_HOST=191.252.100.132
ENV MYSQL_PORT=3306
ENV MEMCACHED_HOST=191.252.100.132
ENV MEMCACHED_PORT=11211

# Instalando dependências do sistema
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Criando e definindo o diretório de trabalho
WORKDIR /app

# Copiando os arquivos de requisitos primeiro (para melhor uso do cache do Docker)
COPY requirements.txt .

# Instalando dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiando o resto da aplicação
COPY . .

# Criando diretório para uploads
RUN mkdir -p static/uploads

# Expondo a porta que a aplicação usa
EXPOSE 7000

# Comando para executar a aplicação
CMD ["python", "app.py", "--host=0.0.0.0", "--port=7000"] 