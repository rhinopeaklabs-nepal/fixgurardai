# The marketing site: stamp the layout onto each page, then serve with nginx.

FROM node:22-alpine AS build
WORKDIR /site
COPY build.mjs ./
COPY src ./src
RUN node build.mjs


FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /site/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1/healthz || exit 1
