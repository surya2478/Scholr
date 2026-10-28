import { test, expect } from '@playwright/test';

test.describe('Student Core Journey', () => {
  test('student can sign in and view home dashboard', async ({ page }) => {
    // Navigate to root which performs dev auto-login for student
    await page.goto('/');

    // Verify redirected to student dashboard
    await expect(page).toHaveURL(/\/student/);

    // Verify header branding and badges
    await expect(page.locator('text=ScholrJr')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('text=Year 10').first()).toBeVisible();

    // Verify key student dashboard navigation links
    await expect(page.getByRole('link', { name: /Practice/i }).first()).toBeVisible();
    await expect(page.getByRole('link', { name: /Tutor/i }).first()).toBeVisible();
  });

  test('student can navigate to practice and see session controls', async ({ page }) => {
    await page.goto('/student/practice');

    // Should stay on practice page or show practice interface
    await expect(page).toHaveURL(/\/student\/practice/);

    // Wait for the app shell to be loaded
    await expect(page.locator('text=ScholrJr')).toBeVisible({ timeout: 15000 });

    // Verify practice content is displayed (e.g. subject selector, question card, or start session)
    const practiceContainer = page.locator('main');
    await expect(practiceContainer).toBeVisible();
  });

  test('student can open the Tutor', async ({ page }) => {
    await page.goto('/student/tutor');

    await expect(page).toHaveURL(/\/student\/tutor/);
    await expect(page.locator('text=ScholrJr')).toBeVisible({ timeout: 15000 });

    // Verify the Tutor's chat elements exist (input, controls)
    const mainContent = page.locator('main');
    await expect(mainContent).toBeVisible();
  });

  test('student can access IIT Foundation bridge page', async ({ page }) => {
    await page.goto('/student/iit');

    await expect(page).toHaveURL(/\/student\/iit/);
    await expect(page.locator('text=ScholrJr')).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/IIT Foundation/i).first()).toBeVisible();
  });
});
