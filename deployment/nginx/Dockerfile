# Multi-stage build: build frontend, then serve with Nginx

# 1) Frontend build stage
FROM node:20-alpine AS frontend_builder
WORKDIR /app

# Install deps
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund

# Copy source and build
COPY frontend/ .
RUN npm run build

# 2) Nginx runtime
FROM nginx:alpine

# Copy nginx configs
COPY deployment/nginx/nginx.conf /etc/nginx/nginx.conf
COPY deployment/nginx/conf.d /etc/nginx/conf.d

# Copy built frontend
COPY --from=frontend_builder /app/dist /usr/share/nginx/html

# Expose standard ports
EXPOSE 80 443 5173

CMD ["nginx", "-g", "daemon off;"]

