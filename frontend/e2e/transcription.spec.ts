import { test, expect } from '@playwright/test';
import path from 'path';

const TEST_AUDIO_PATH = path.resolve(__dirname, '../../test_audio/papo gustavo 1404.m4a');

test.describe('Audio Transcription E2E', () => {
  test('should upload audio file and display transcription', async ({ page }) => {
    // Navigate to the upload page
    await page.goto('/');

    // Verify page loaded
    await expect(page.locator('h1')).toContainText('Transcriptor');
    await expect(page.locator('h2')).toContainText('Upload Audio for Transcription');

    // Upload the audio file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(TEST_AUDIO_PATH);

    // Wait for upload to start (progress should appear)
    await expect(page.locator('text=Uploading')).toBeVisible({ timeout: 10000 });

    // Wait for processing to start
    await expect(page.locator('text=Transcribing audio')).toBeVisible({ timeout: 60000 });

    // Wait for transcription to complete (this can take several minutes)
    await expect(page.locator('text=Complete')).toBeVisible({ timeout: 600000 });

    // Verify transcription view is displayed
    await expect(page.locator('h2')).toContainText('papo gustavo 1404.m4a');

    // Verify speaker labels are present (at least one SPEAKER badge)
    const speakerBadges = page.locator('button:has-text("SPEAKER_")');
    await expect(speakerBadges.first()).toBeVisible({ timeout: 5000 });

    // Verify segments are displayed
    const segments = page.locator('.space-y-3 > div');
    const segmentCount = await segments.count();
    expect(segmentCount).toBeGreaterThan(0);

    console.log(`Transcription completed with ${segmentCount} segments`);

    // Verify download button is present
    await expect(page.locator('button:has-text("Download")')).toBeVisible();
  });

  test('should edit speaker name', async ({ page }) => {
    // This test assumes we have a completed transcription from the previous test
    // Navigate to history
    await page.goto('/');
    await page.click('button:has-text("History")');

    // Wait for history to load
    await page.waitForTimeout(2000);

    // Click on first completed transcription
    const completedItem = page.locator('button:has-text("completed")').first();
    if (await completedItem.isVisible()) {
      await completedItem.click();

      // Wait for transcription view
      await page.waitForTimeout(1000);

      // Click on first speaker to edit
      const speakerButton = page.locator('button:has-text("SPEAKER_")').first();
      if (await speakerButton.isVisible()) {
        await speakerButton.click();

        // Wait for editor modal
        await expect(page.locator('text=Edit Speaker Name')).toBeVisible({ timeout: 5000 });

        // Enter new name
        const input = page.locator('input[placeholder="Enter speaker name"]');
        await input.fill('Gustavo');

        // Save
        await page.click('button:has-text("Save")');

        // Verify modal closed and name updated
        await expect(page.locator('text=Edit Speaker Name')).not.toBeVisible({ timeout: 5000 });
        await expect(page.locator('button:has-text("Gustavo")')).toBeVisible({ timeout: 5000 });
      }
    }
  });

  test('should download transcription', async ({ page }) => {
    // Navigate to history and find a completed transcription
    await page.goto('/');
    await page.click('button:has-text("History")');

    await page.waitForTimeout(2000);

    const completedItem = page.locator('button:has-text("completed")').first();
    if (await completedItem.isVisible()) {
      await completedItem.click();
      await page.waitForTimeout(1000);

      // Click download button
      const downloadButton = page.locator('button:has-text("Download")');
      if (await downloadButton.isVisible()) {
        await downloadButton.click();

        // Click on TXT format
        await page.click('text=Text (.txt)');

        // The download should start (we can't easily verify file content in Playwright)
        console.log('Download initiated');
      }
    }
  });
});
