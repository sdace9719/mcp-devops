FROM docker.io/library/node:20-alpine AS build
WORKDIR /app
COPY package*.json /app/
RUN sh -c "if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi"
COPY index.html /app/index.html
COPY postcss.config.cjs tailwind.config.cjs /app/
COPY public /app/public
COPY src /app/src
ARG VITE_API_BASE
ENV VITE_API_BASE=${VITE_API_BASE}
RUN npm run build

FROM docker.io/library/nginx:1.27-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]


