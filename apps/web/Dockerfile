# The web image. Next.js in standalone output, so the runtime stage carries no node_modules tree.
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
# Next bakes the /api proxy target into the build (next.config.ts), so the API's address is a build argument.
ARG SCHOLR_API_ORIGIN=http://api:8000
ENV SCHOLR_API_ORIGIN=$SCHOLR_API_ORIGIN     NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000
RUN addgroup -S scholr && adduser -S scholr -G scholr
COPY --from=build /app/public ./public
COPY --from=build --chown=scholr:scholr /app/.next/standalone ./
COPY --from=build --chown=scholr:scholr /app/.next/static ./.next/static
USER scholr
EXPOSE 3000
# The browser only ever talks to this origin; /api/* is proxied to SCHOLR_API_ORIGIN (see next.config.ts).
CMD ["node", "server.js"]
