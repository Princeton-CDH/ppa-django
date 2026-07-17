import { test, expect } from '@playwright/test'

/**
 * Work detail page E2E tests.
 * Requires Solr + DB (devbox run dev) — needs real works in the index.
 *
 * These tests navigate to the first available work detail page dynamically,
 * so they don't depend on a hardcoded source_id.
 */
test.describe('Work detail page (requires Solr)', () => {
    let detailUrl: string

    test.beforeAll(async ({ browser }) => {
        // Find a detail page URL from the archive listing
        const page = await browser.newPage()
        await page.goto('/archive/')
        const firstResult = page.locator('.results-list .item .detail').first()
        const count = await firstResult.count()
        if (count) {
            detailUrl = await firstResult.getAttribute('href') ?? '/archive/'
        } else {
            detailUrl = '/archive/'
        }
        await page.close()
    })

    test('detail page loads without errors', async ({ page }) => {
        await page.goto(detailUrl)
        await expect(page).not.toHaveURL(/error/)
        await expect(page.locator('h1')).toBeVisible()
    })

    test('lazy-loaded images gain src after page load', async ({ page }) => {
        await page.goto(detailUrl)
        // Wait for IntersectionObserver to fire on visible images
        await page.waitForLoadState('networkidle')

        const lazyImages = page.locator('img[data-src]')
        const count = await lazyImages.count()
        if (!count) test.skip()

        // At least the first lazy image should have been loaded (it's in viewport)
        const firstImg = lazyImages.first()
        // Once loaded, data-src is removed and src is set
        await expect(firstImg).not.toHaveAttribute('data-src', /.+/, { timeout: 5000 })
    })

    test('tooltip appears on question mark hover', async ({ page }) => {
        await page.goto(detailUrl)

        const tooltipTrigger = page.locator('[data-controller="tooltip"]').first()
        const count = await tooltipTrigger.count()
        if (!count) test.skip()

        await tooltipTrigger.hover()
        await expect(page.locator('.ppa-tooltip')).toBeVisible()
    })

    test('tooltip disappears on mouse leave', async ({ page }) => {
        await page.goto(detailUrl)

        const tooltipTrigger = page.locator('[data-controller="tooltip"]').first()
        const count = await tooltipTrigger.count()
        if (!count) test.skip()

        await tooltipTrigger.hover()
        await expect(page.locator('.ppa-tooltip')).toBeVisible()

        // Move mouse away
        await page.mouse.move(0, 0)
        await expect(page.locator('.ppa-tooltip')).not.toBeVisible()
    })
})

test.describe('Search within work (requires Solr)', () => {
    let detailUrl: string

    test.beforeAll(async ({ browser }) => {
        const page = await browser.newPage()
        await page.goto('/archive/')
        const firstResult = page.locator('.results-list .item .detail').first()
        const count = await firstResult.count()
        detailUrl = count ? (await firstResult.getAttribute('href') ?? '/archive/') : '/archive/'
        await page.close()
    })

    test('search-within form is present on detail page', async ({ page }) => {
        await page.goto(detailUrl)
        await expect(page.locator('#search-within')).toBeVisible()
    })

    test('typing in search-within field updates results output', async ({ page }) => {
        await page.goto(detailUrl)

        const searchWithin = page.locator('#search-within')
        const count = await searchWithin.count()
        if (!count) test.skip()

        const output = page.locator('output[form=search-within]')
        const initialContent = await output.innerHTML()

        await page.locator('input[name=query][form=search-within], #search-within input[name=query]').fill('the')
        await page.waitForTimeout(1200) // debounce + network

        const updatedContent = await output.innerHTML()
        expect(updatedContent).not.toBe(initialContent)
    })
})
