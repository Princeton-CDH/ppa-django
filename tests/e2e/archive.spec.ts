import { test, expect } from '@playwright/test'

/**
 * Archive search page E2E tests.
 * Most tests require Solr + DB (devbox run dev).
 * Tests are tagged with comments indicating Solr dependency.
 */
test.describe('Archive search — form interaction', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/archive/')
    })

    // ── Clear button ──────────────────────────────────────────────────────────

    test('clear button is hidden when query input is empty', async ({ page }) => {
        const clearBtn = page.locator('[data-clearable-target="button"]').first()
        await expect(clearBtn).toHaveCSS('display', 'none')
    })

    test('clear button appears after typing in query field', async ({ page }) => {
        const input = page.locator('input[name=query]')
        const clearBtn = page.locator('[data-clearable-target="button"]').first()

        await input.fill('poetry')
        await expect(clearBtn).not.toHaveCSS('display', 'none')
    })

    test('clicking clear button empties the query field', async ({ page }) => {
        const input = page.locator('input[name=query]')
        const clearBtn = page.locator('[data-clearable-target="button"]').first()

        await input.fill('poetry')
        await clearBtn.click()
        await expect(input).toHaveValue('')
    })

    // ── Advanced search toggle ────────────────────────────────────────────────

    test('advanced search fields are hidden by default', async ({ page }) => {
        const advanced = page.locator('.advanced.segment').first()
        await expect(advanced).toHaveCSS('display', 'none')
    })

    test('clicking advanced toggle shows the advanced search fields', async ({ page }) => {
        await page.locator('[data-action*="toggleAdvancedSearch"]').click()
        const advanced = page.locator('.advanced.segment').first()
        await expect(advanced).not.toHaveCSS('display', 'none')
    })

    test('clicking advanced toggle twice hides the advanced search fields again', async ({ page }) => {
        const toggle = page.locator('[data-action*="toggleAdvancedSearch"]')
        await toggle.click()
        await toggle.click()
        const advanced = page.locator('.advanced.segment').first()
        await expect(advanced).toHaveCSS('display', 'none')
    })

    test('advanced search open state persists across page reload (sessionStorage)', async ({ page }) => {
        await page.locator('[data-action*="toggleAdvancedSearch"]').click()
        await page.reload()
        const advanced = page.locator('.advanced.segment').first()
        await expect(advanced).not.toHaveCSS('display', 'none')
    })

    // ── Date validation ───────────────────────────────────────────────────────

    test('date validation message is hidden initially', async ({ page }) => {
        const validation = page.locator('[data-search-target="validation"]')
        await expect(validation).toHaveCSS('visibility', 'hidden')
    })

    test('date validation shows when min date is greater than max date', async ({ page }) => {
        // Open advanced search to access date fields
        await page.locator('[data-action*="toggleAdvancedSearch"]').click()

        await page.locator('#id_pub_date_0').fill('1900')
        await page.locator('#id_pub_date_1').fill('1800')
        // Trigger validation by dispatching input event on either date field
        await page.locator('#id_pub_date_0').dispatchEvent('input')

        const validation = page.locator('[data-search-target="validation"]')
        await expect(validation).toHaveCSS('visibility', 'visible')
    })

    // ── Sort dropdown ─────────────────────────────────────────────────────────

    test('sort dropdown is present on the page', async ({ page }) => {
        await expect(page.locator('[data-controller="select"]')).toBeVisible()
    })

    // ── Prevent Enter submit ──────────────────────────────────────────────────

    test('pressing Enter in query field does not navigate away', async ({ page }) => {
        const input = page.locator('input[name=query]')
        await input.click()
        await page.keyboard.press('Enter')
        // Page should still be /archive/
        expect(page.url()).toContain('/archive/')
    })
})

test.describe('Archive search — AJAX results (requires Solr)', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/archive/')
    })

    test('typing a query updates the results area', async ({ page }) => {
        const results = page.locator('[data-search-target="results"]')
        const initialContent = await results.innerHTML()

        await page.locator('input[name=query]').fill('poetry')
        // Wait for debounce (750ms) + network response
        await page.waitForTimeout(1200)

        const updatedContent = await results.innerHTML()
        expect(updatedContent).not.toBe(initialContent)
    })

    test('works count shows loading state during AJAX', async ({ page }) => {
        const workscount = page.locator('[data-search-target="workscount"]')
        await page.locator('input[name=query]').fill('poetry')
        // The loading class should appear briefly
        await expect(workscount).toHaveClass(/loading/, { timeout: 1000 })
    })

    test('URL is updated with query parameter after search', async ({ page }) => {
        await page.locator('input[name=query]').fill('poetry')
        await page.waitForTimeout(1200)
        expect(page.url()).toContain('query=poetry')
    })

    test('sort change triggers results update', async ({ page }) => {
        const results = page.locator('[data-search-target="results"]')
        // Wait for initial load
        await page.waitForLoadState('networkidle')
        const initialContent = await results.innerHTML()

        const sortSelect = page.locator('[data-select-target="input"]')
        await sortSelect.selectOption('pub_date_asc')

        await page.waitForTimeout(800)
        const updatedContent = await results.innerHTML()
        expect(updatedContent).not.toBe(initialContent)
    })

    test('pagination link updates URL with page parameter', async ({ page }) => {
        // Only run if pagination exists
        const nextBtn = page.locator('.page-controls a').first()
        const count = await nextBtn.count()
        if (!count) test.skip()

        await nextBtn.click()
        await page.waitForURL(/page=/)
        expect(page.url()).toContain('page=')
    })
})
