import { defineConfig } from '@playwright/test'

export default defineConfig({
    testDir: './tests/e2e',
    timeout: 30_000,
    retries: 1,
    use: {
        baseURL: 'http://localhost:8000',
        headless: true,
    },
    // Django dev server must be started manually via `devbox run dev` before
    // running E2E tests. No webServer block — Solr + DB are managed by devbox.
    projects: [
        { name: 'chromium', use: { browserName: 'chromium' } },
    ],
    reporter: [
        ['list'],
        ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ],
})
