# ==============================================================================
# Multi-stage Dockerfile para o Frontend VERA (React + Vite + Nginx)
# ==============================================================================

# Estágio 1: Build da aplicação estática
FROM node:22-alpine AS build

WORKDIR /app

# Copia manifestos de dependência e instala
COPY package*.json ./
RUN npm install

# Copia código-fonte e compila a aplicação com Vite
COPY . .
RUN npm run build

# Estágio 2: Servidor de produção com Nginx Alpine (leve e seguro)
FROM nginx:alpine

# Remove configuração padrão do Nginx
RUN rm -rf /etc/nginx/conf.d/default.conf

# Copia configuração customizada com roteamento SPA e proxy de API
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copia os artefatos compilados do estágio anterior
COPY --from=build /app/dist /usr/share/nginx/html

# Expõe a porta padrão HTTP
EXPOSE 80

# Inicializa o Nginx em primeiro plano
CMD ["nginx", "-g", "daemon off;"]
