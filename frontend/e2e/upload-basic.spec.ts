import { test, expect } from '@playwright/test';
import path from 'path';

test('should upload file and show processing status', async ({ page }) => {
  // Navigate to the app
  await page.goto('/');

  // Verify we're on the upload page
  await expect(page.getByText('Upload Audio for Transcription')).toBeVisible();

  // Get the audio file path
  const audioPath = path.resolve(__dirname, '../../test_audio/papo gustavo 1404.m4a');

  // Upload the audio file
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(audioPath);

  // Wait for upload to complete - should show "Uploading..." first
  console.log('Waiting for upload to start...');

  // After upload completes, should start processing
  // Check for either "Transcribing audio..." or the processing state
  const processingText = page.getByText('Transcribing audio...');

  try {
    await expect(processingText).toBeVisible({ timeout: 60000 });
    console.log('Processing started - shows "Transcribing audio..."');

    // Take a screenshot
    await page.screenshot({ path: 'test-results/upload-processing.png' });

    // Now check for progress stages (new feature)
    // Look for stage dots
    const stageDots = page.locator('.rounded-full.w-3.h-3');
    const dotCount = await stageDots.count();
    console.log(`Found ${dotCount} progress stage dots`);

    if (dotCount === 4) {
      console.log('SUCCESS: Progress stage indicator is working (4 dots found)');
    } else if (dotCount > 0) {
      console.log(`PARTIAL: Found ${dotCount} dots instead of expected 4`);
    } else {
      console.log('INFO: No progress stage dots found yet');
    }

    // Check for stage description
    const stageTexts = ['Loading Audio', 'Transcribing', 'Identifying Speakers', 'Saving Results'];
    for (const text of stageTexts) {
      const element = page.getByText(text, { exact: false });
      if (await element.isVisible({ timeout: 1000 }).catch(() => false)) {
        console.log(`Found stage text: "${text}"`);
      }
    }

    // Take another screenshot
    await page.screenshot({ path: 'test-results/upload-with-stages.png' });

  } catch (e) {
    console.log('Error waiting for processing:', e);
    await page.screenshot({ path: 'test-results/upload-error.png' });
    throw e;
  }
});
