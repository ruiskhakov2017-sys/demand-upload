FROM node:24-alpine AS deps
WORKDIR /app
COPY frontend/package.json /app/package.json
COPY frontend/package-lock.json /app/package-lock.json
RUN npm ci

FROM deps AS build
COPY frontend /app
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY infrastructure/docker/frontend.nginx.conf /etc/nginx/conf.d/default.conf
