# jup-gateway: Bun, no build step. Cloud Build here runs the legacy builder (no BuildKit), so
# nothing below relies on BuildKit-only syntax or $BUILDPLATFORM.
FROM oven/bun:1.3.11-slim

WORKDIR /app
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile --production
COPY tsconfig.json ./
COPY src ./src

ENV NODE_ENV=production PORT=8080
USER bun
EXPOSE 8080
CMD ["bun", "src/server.ts"]
