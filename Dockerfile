FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build && npm test

FROM node:22-bookworm-slim
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY --from=build /app/src ./src
COPY --from=build /app/engine ./engine
COPY --from=build /app/scripts ./scripts
COPY --from=build /app/server.mjs ./server.mjs
COPY --from=build /app/package.json ./package.json
USER node
EXPOSE 3100
CMD ["node","server.mjs"]
