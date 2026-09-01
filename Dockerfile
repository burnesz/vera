# Usa uma imagem oficial segura e atualizada do Python (Debian Bookworm)
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Atualiza pacotes do sistema para corrigir vulnerabilidades conhecidas
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copia os requisitos e instala as dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código do projeto para o contêiner
COPY . .

# Expõe a porta padrão do FastAPI
EXPOSE 8000

# Comando para iniciar o servidor uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]