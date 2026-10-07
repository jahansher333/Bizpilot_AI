# Production image for the BizPilot web app. Build from apps/web:
#   docker build -t bizpilot-web --build-arg NEXT_PUBLIC_API_URL=https://api.example.com .
# NEXT_PUBLIC_API_URL is inlined into the browser bundle at build time, so each environment
# needs its own image. The browser calls the API directly (CORS), which keeps the real client IP
# visible to the API's rate limits.
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci


FROM node:20-alpine AS build
WORKDIR /app
ARG NEXT_PUBLIC_API_URL
RUN test -n "$NEXT_PUBLIC_API_URL" || (echo "NEXT_PUBLIC_API_URL build arg is required" && exit 1)
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build


FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN adduser -D -u 10001 bizpilot
COPY --from=build --chown=bizpilot:bizpilot /app/.next/standalone ./
COPY --from=build --chown=bizpilot:bizpilot /app/.next/static ./.next/static
USER bizpilot
EXPOSE 3000
CMD ["node", "server.js"]
