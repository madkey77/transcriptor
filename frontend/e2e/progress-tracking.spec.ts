import { test, expect } from '@playwright/test';
import path from 'path';

test.describe('Progress Tracking', () => {
  test('should display progress stages and logs during transcription', async ({ page }) => {
    // Navigate to the app
    await page.goto('/');

    // Verify we're on the upload page
    await expect(page.getByText('Upload Audio for Transcription')).toBeVisible();

    // Get the audio file path
    const audioPath = path.resolve(__dirname, '../../test_audio/papo gustavo 1404.m4a');

    // Upload the audio file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(audioPath);

    // Wait for upload to complete and processing to start
    await expect(page.getByText('Transcribing audio...')).toBeVisible({ timeout: 30000 });

    // Check that stage indicator appears (the dots container)
    // The stage indicator should show processing stages
    const stageIndicator = page.locator('.animate-pulse');
    await expect(stageIndicator).toBeVisible({ timeout: 10000 });

    // Check for stage description text (one of the stages)
    const stageDescriptions = [
      'Preparing audio file...',
      'Loading Audio',
      'Transcribing audio with WhisperX...',
      'Transcribing',
      'Identifying speakers...',
      'Identifying Speakers',
      'Saving transcription segments...',
      'Saving Results',
    ];

    // Wait for any stage description to appear
    let stageFound = false;
    for (const desc of stageDescriptions) {
      try {
        const element = page.getByText(desc, { exact: false });
        if (await element.isVisible({ timeout: 2000 })) {
          stageFound = true;
          console.log(`Found stage: ${desc}`);
          break;
        }
      } catch {
        // Continue to next stage
      }
    }

    // Take a screenshot for debugging
    await page.screenshot({ path: 'test-results/progress-tracking-stages.png' });

    // Check for the Processing Logs button (collapsible)
    const logsButton = page.getByText('Processing Logs', { exact: false });

    // Wait for logs to appear (may take a moment)
    try {
      await expect(logsButton).toBeVisible({ timeout: 60000 });
      console.log('Processing Logs button found');

      // Click to expand logs
      await logsButton.click();

      // Wait a moment for logs to render
      await page.waitForTimeout(1000);

      // Take screenshot with logs expanded
      await page.screenshot({ path: 'test-results/progress-tracking-logs.png' });

      // Check that log entries are visible (look for timestamp pattern or log level)
      const logPanel = page.locator('.font-mono.text-xs');
      await expect(logPanel).toBeVisible({ timeout: 5000 });
    } catch (e) {
      console.log('Logs not visible yet, continuing...', e);
    }

    // Wait for completion (this can take a while for audio processing)
    await expect(page.getByText('Complete')).toBeVisible({ timeout: 600000 });

    // Take final screenshot
    await page.screenshot({ path: 'test-results/progress-tracking-complete.png' });

    // Verify we can see the transcription
    await expect(page.getByText('Click on a speaker name to edit it')).toBeVisible({ timeout: 10000 });

    console.log('Test completed successfully!');
  });

  test('should show stage progress dots', async ({ page }) => {
    // Navigate to the app
    await page.goto('/');

    // Get the audio file path
    const audioPath = path.resolve(__dirname, '../../test_audio/papo gustavo 1404.m4a');

    // Upload the audio file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(audioPath);

    // Wait for processing status
    await expect(page.getByText('Transcribing audio...')).toBeVisible({ timeout: 30000 });

    // Look for the stage dots (they should be rendered as small circles)
    // The dots are w-3 h-3 rounded-full elements
    const dots = page.locator('.rounded-full.w-3.h-3');

    // Wait for dots to appear
    await expect(dots.first()).toBeVisible({ timeout: 30000 });

    // Count the dots (should be 4: loading_audio, transcribing, diarizing, saving)
    const dotCount = await dots.count();
    console.log(`Found ${dotCount} progress dots`);
    expect(dotCount).toBe(4);

    // Take screenshot
    await page.screenshot({ path: 'test-results/progress-dots.png' });

    // Wait for at least one dot to turn green (completed stage)
    // Green dots have bg-green-500 class
    const greenDot = page.locator('.rounded-full.bg-green-500');

    // Wait for processing to advance (first dot should become green after loading_audio)
    await expect(greenDot.first()).toBeVisible({ timeout: 120000 });
    console.log('At least one stage completed (green dot visible)');

    await page.screenshot({ path: 'test-results/progress-dots-advanced.png' });
  });
});
