# The web app, for running the whole app on a laptop (docs/run-locally.md).
# Render builds from render.yaml instead; this image is never deployed.
FROM node:22-slim AS build
WORKDIR /src
COPY design-system/tokens.json design-system/tokens.json
COPY web/package.json web/package-lock.json web/
RUN cd web && npm ci --no-audit --no-fund
COPY web/ web/
ARG VITE_API_URL=http://localhost:8000
RUN cd web && VITE_API_URL=$VITE_API_URL npm run build

FROM nginx:1.27-alpine
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/web/dist /usr/share/nginx/html
