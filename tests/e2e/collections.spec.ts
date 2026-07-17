import { test, expect } from '@playwright/test'

/**
 * Collection checkbox regression tests.
 * These are the regression tests for the bug where clicking a collection
 * checkbox's "x" did not toggle the .active class on the parent label.
 *
 * Does NOT require Solr — tests only the visual/DOM behavior of the
 * SearchController._setupCollectionInputs() delegated listener.
 */
test.describe('Collection checkboxes', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/archive/')
    })

    test('checking a collection checkbox adds active class to its label', async ({ page }) => {
        const label = page.locator('#collections label.ui.button').first()
        const checkbox = label.locator('input[type=checkbox]')

        // Start unchecked
        await checkbox.check()
        await expect(label).toHaveClass(/active/)
    })

    test('unchecking a collection checkbox removes active class from its label', async ({ page }) => {
        const label = page.locator('#collections label.ui.button').first()
        const checkbox = label.locator('input[type=checkbox]')

        await checkbox.check()
        await expect(label).toHaveClass(/active/)

        await checkbox.uncheck()
        await expect(label).not.toHaveClass(/active/)
    })

    test('multiple collections can be toggled independently', async ({ page }) => {
        const labels = page.locator('#collections label.ui.button')
        const count = await labels.count()
        if (count < 2) test.skip()

        const first = labels.nth(0)
        const second = labels.nth(1)

        await first.locator('input[type=checkbox]').check()
        await expect(first).toHaveClass(/active/)
        await expect(second).not.toHaveClass(/active/)

        await second.locator('input[type=checkbox]').check()
        await expect(first).toHaveClass(/active/)
        await expect(second).toHaveClass(/active/)
    })

    test('keyboard Enter on collection checkbox toggles it', async ({ page }) => {
        const label = page.locator('#collections label.ui.button').first()
        const checkbox = label.locator('input[type=checkbox]')

        await checkbox.focus()
        await page.keyboard.press('Enter')
        await expect(label).toHaveClass(/active/)
    })
})
