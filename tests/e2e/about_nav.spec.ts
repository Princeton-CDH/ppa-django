import { test, expect } from '@playwright/test'

/**
 * About nav keyboard navigation E2E tests.
 * Does NOT require Solr — tests only the AboutNavController keyboard behavior.
 */
test.describe('About nav keyboard navigation', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/')
    })

    test('focusing the About trigger shows the dropdown', async ({ page }) => {
        const trigger = page.locator('[data-about-nav-target="text"]')
        await trigger.focus()
        const nav = page.locator('[data-controller="about-nav"]')
        await expect(nav).toHaveClass(/hovered/)
    })

    test('blurring the About trigger hides the dropdown', async ({ page }) => {
        const trigger = page.locator('[data-about-nav-target="text"]')
        await trigger.focus()
        await trigger.blur()
        const nav = page.locator('[data-controller="about-nav"]')
        await expect(nav).not.toHaveClass(/hovered/)
    })

    test('ArrowDown from trigger focuses the first menu link', async ({ page }) => {
        const trigger = page.locator('[data-about-nav-target="text"]')
        await trigger.focus()
        await page.keyboard.press('ArrowDown')

        const firstLink = page.locator('[data-controller="about-nav"] .menu .item a').first()
        await expect(firstLink).toBeFocused()
    })

    test('ArrowDown from first menu link focuses the second link', async ({ page }) => {
        const trigger = page.locator('[data-about-nav-target="text"]')
        await trigger.focus()
        await page.keyboard.press('ArrowDown') // to first link

        const links = page.locator('[data-controller="about-nav"] .menu .item a')
        const linkCount = await links.count()
        if (linkCount < 2) test.skip()

        await page.keyboard.press('ArrowDown') // to second link
        await expect(links.nth(1)).toBeFocused()
    })

    test('ArrowUp from first menu link returns focus to trigger', async ({ page }) => {
        const trigger = page.locator('[data-about-nav-target="text"]')
        await trigger.focus()
        await page.keyboard.press('ArrowDown') // to first link
        await page.keyboard.press('ArrowUp')   // back to trigger
        await expect(trigger).toBeFocused()
    })
})
