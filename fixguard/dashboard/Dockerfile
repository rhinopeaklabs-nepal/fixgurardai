# Build the dashboard, then serve it from nginx alongside an /api proxy.

FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite inlines these at build time - they cannot be supplied at run time.
# An empty base URL means "same origin", which is what the nginx stage below
# provides by proxying /api to the api container.
ARG VITE_API_BASE_URL=""
ARG VITE_API_KEY=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_API_KEY=$VITE_API_KEY

RUN npm run build


FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
