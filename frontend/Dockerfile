FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./

RUN npm install

COPY . .

ENV API_BASE=http://192.168.14.15:8004/api/extractos/totalizar
ENV API_REPORTE=http://192.168.14.15:8004/api/extractos/reporte
ENV API_ETIQUETA=http://192.168.14.15:8004/api/etiquetas

RUN npm run build

FROM nginx:1.25-alpine AS runner

COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
