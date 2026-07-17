import { test, expect } from '@playwright/test'

/**
 * Collection checkbox regression tests.
 * These are the regression tests for the bug where clicking a collection
 * label did not toggle the .active class.
 *
 * Does NOT require Solr — tests only the visual/DOM behavior of the
 * SearchController._setupCollectionInputs() delegated listener.
 *
 * The page initialises with all collections pre-selected (all checked/active).
 * Tests use label.click() because the checkbox is visually hidden inside the
 * label; Playwright cannot click through to the hidden input directly.
 */
test.describe('Collection checkboxes', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/archive/')
    })

    test('all collections start as active on page load', async ({ page }) => {
        const label = page.locator('#collections label.ui.button').first()
        await expect(label).toHaveClass(/active/)
        await expect(label.locator('input[type=checkbox]')).toBeChecked()
    })

    test('clicking an active collection label removes active class', async ({ page }) => {
        const label = page.locator('#collections label.ui.button').first()
        await expect(label).toHaveClass(/active/)

        await label.click()

        await expect(label).not.toHaveClass(/active/)
        await expect(label.locator('input[type=checkbox]')).not.toBeChecked()
    })

    test('clicking an inactive collection label adds active class', async ({ page }) => {
        const label = page.locator('#collections label.ui.button').first()
        // Deselect first
        await label.click()
        await expect(label).not.toHaveClass(/active/)

        // Re-select
        await label.click()
        await expect(label).toHaveClass(/active/)
        await expect(label.locator('input[type=checkbox]')).toBeChecked()
    })

    test('toggling one collection does not affect others', async ({ page }) => {
        const labels = page.locator('#collections label.ui.button')
        const count = await labels.count()
        if (count < 2) test.skip()

        const first = labels.nth(0)
        const second = labels.nth(1)

        // Both start active
        await expect(first).toHaveClass(/active/)
        await expect(second).toHaveClass(/active/)

        // Deselect only the first
        await first.click()
        await expect(first).not.toHaveClass(/active/)
        await expect(second).toHaveClass(/active/)

        // Re-select the first
        await first.click()
        await expect(first).toHaveClass(/active/)
        await expect(second).toHaveClass(/active/)
    })

    test('keyboard Enter on collection checkbox toggles it', async ({ page }) => {
        const label = page.locator('#collections label.ui.button').first()
        const checkbox = label.locator('input[type=checkbox]')

        // Start active; focus the hidden checkbox and press Enter
        await expect(label).toHaveClass(/active/)
        await checkbox.focus()
        await page.keyboard.press('Enter')
        await expect(label).not.toHaveClass(/active/)
    })
})
