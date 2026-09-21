import { test, expect } from '@playwright/test';

test.describe('Parent & Guardian Core Journey', () => {
  test.beforeEach(async ({ page }) => {
    // Obtain a dev session token for guardian role via the API proxy or direct endpoint
    const response = await page.request.post('/api/dev/session', {
      data: { role: 'guardian' },
    });
    const sessionData = await response.json();

    // Set the token in localStorage before each test page load
    await page.addInitScript((token) => {
      window.localStorage.setItem('scholr.dev_token', token);
    }, sessionData.token);
  });

  test('parent can view overview dashboard with guardian status', async ({ page }) => {
    await page.goto('/parent');

    // Wait for the app shell to load with the guardian identity
    await expect(page.locator('text=ScholrFamily')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('text=Guardian').first()).toBeVisible();

    // Verify parent navigation items
    await expect(page.getByRole('link', { name: /Monthly summary|Monthly/i }).first()).toBeVisible();
    await expect(page.getByRole('link', { name: /Review marks/i }).first()).toBeVisible();
    await expect(page.getByRole('link', { name: /Safety alerts|Safety/i }).first()).toBeVisible();
  });

  test('parent can view safety alerts and consent settings', async ({ page }) => {
    await page.goto('/parent/safety');

    await expect(page).toHaveURL(/\/parent\/safety/);
    await expect(page.locator('text=ScholrFamily')).toBeVisible({ timeout: 15000 });

    const mainContent = page.locator('main');
    await expect(mainContent).toBeVisible();
  });

  test('parent can review monthly summary and student progress overview', async ({ page }) => {
    await page.goto('/parent/summary');

    await expect(page).toHaveURL(/\/parent\/summary/);
    await expect(page.locator('text=ScholrFamily')).toBeVisible({ timeout: 15000 });

    const mainContent = page.locator('main');
    await expect(mainContent).toBeVisible();
  });
});
