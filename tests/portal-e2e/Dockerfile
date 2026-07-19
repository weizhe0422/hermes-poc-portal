ARG PLAYWRIGHT_IMAGE=mcr.microsoft.com/playwright:v1.61.0-noble
FROM ${PLAYWRIGHT_IMAGE}

ARG PLAYWRIGHT_VERSION=1.61.0
ARG NPM_REGISTRY=https://registry.npmjs.org

ENV CI=1 \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    RESULTS_DIR=/test-results/portal-e2e

WORKDIR /opt/hermes/portal-e2e

COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund --registry "$NPM_REGISTRY" \
    && test "$(node -p "require('./node_modules/@playwright/test/package.json').version")" = "${PLAYWRIGHT_VERSION}"

COPY playwright.config.ts tsconfig.json ./
COPY reporters ./reporters
COPY probes ./probes
COPY support ./support
COPY tests ./tests

RUN npm run typecheck

RUN mkdir -p /test-results/portal-e2e \
    && chown -R pwuser:pwuser /test-results

USER pwuser

ENTRYPOINT ["npm", "test", "--"]
