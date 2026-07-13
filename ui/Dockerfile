# syntax=docker/dockerfile:1
FROM node:22-alpine AS base

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"

RUN corepack enable

FROM base AS dependencies

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN --mount=type=cache,id=ape-ui-pnpm,target=/pnpm/store pnpm install --frozen-lockfile

FROM dependencies AS build

WORKDIR /app

ARG BACKEND_API_URL=http://backend:8000
ARG NEXT_PUBLIC_APE_RUNTIME_PROFILE=service
ENV BACKEND_API_URL=$BACKEND_API_URL
ENV NEXT_PUBLIC_APE_RUNTIME_PROFILE=$NEXT_PUBLIC_APE_RUNTIME_PROFILE
ENV NEXT_TELEMETRY_DISABLED=1

COPY . .
RUN pnpm build

FROM node:22-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV NEXT_PUBLIC_APE_RUNTIME_PROFILE=service
ENV HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 ape \
    && adduser --system --uid 1001 --ingroup ape ape

COPY --from=build --chown=ape:ape /app/public ./public
COPY --from=build --chown=ape:ape /app/.next/standalone ./
COPY --from=build --chown=ape:ape /app/.next/static ./.next/static

USER ape

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/').then((r) => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["node", "server.js"]
