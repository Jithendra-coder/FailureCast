import { expect, test, type Page } from '@playwright/test'

async function openWorkspace(page: Page) {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'See what the engine data is telling you.' })).toBeVisible()
  await expect(page.getByText('RESEARCH DEMO · SIMULATED DATA')).toBeVisible()
  await page.getByRole('button', { name: /Get started/ }).click()
  await page.getByLabel('Administrator password').fill(process.env.FAILURECAST_E2E_PASSWORD || '')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: 'See the signal. Plan the review.' })).toBeVisible()
  await expect(page.getByText('API connected')).toBeVisible()
}

test('demo introduction leads into engine inspection and historical replay', async ({ page }) => {
  await openWorkspace(page)

  await page.getByRole('button', { name: 'Inspect engine' }).click()
  await expect(page.getByRole('heading', { name: 'Engine health' })).toBeVisible()
  await expect(page.getByText('Historical simulation', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Replay studio' }).click()
  await expect(page.getByRole('heading', { name: 'Trajectory replay' })).toBeVisible()
  const restartReplay = page.getByRole('button', { name: 'Restart replay' })
  const resetReplay = page.getByRole('button', { name: 'Reset replay' })
  if (await restartReplay.isVisible()) await restartReplay.click()
  else if (await resetReplay.isVisible()) await resetReplay.click()
  else await page.getByRole('button', { name: /^(Start replay|Resume)$/ }).click()
  await expect(page.getByRole('button', { name: 'Pause' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Current replay estimate' })).toBeVisible()
  await expect(page.getByText('Historical simulation. No live equipment connection or control.')).toBeVisible()
  await page.getByRole('button', { name: 'Pause' }).click()
  await expect(page.getByRole('button', { name: 'Resume' })).toBeVisible()
})

test('candidate training, approval, evaluation and rollback complete in the UI', async ({ page }) => {
  await openWorkspace(page)
  await page.getByRole('button', { name: 'Experiments' }).click()
  const completedJobs = page.getByText('completed', { exact: true })
  const completedBefore = await completedJobs.count()
  await page.getByRole('button', { name: 'Queue training job' }).click()
  await expect(completedJobs).toHaveCount(completedBefore + 1, { timeout: 120_000 })

  await page.getByRole('button', { name: 'Model registry' }).click()
  const previousActiveRow = page.getByRole('row').filter({ has: page.getByText('active', { exact: true }) })
  const previousActiveModelId = await previousActiveRow.getByRole('cell').first().innerText()
  await page.getByRole('button', { name: 'Review & promote' }).waitFor({ state: 'visible', timeout: 120_000 })
  await page.getByRole('button', { name: 'Review & promote' }).click()
  await expect(page.getByRole('heading', { name: 'Activate this model version?' })).toBeVisible()
  await page.getByRole('button', { name: 'Approve & activate' }).click()
  await expect(page.getByRole('button', { name: 'Evaluate simulated demo' })).toBeVisible({ timeout: 30_000 })

  const simulatedEvaluations = page.getByText('Simulated evaluation', { exact: true })
  const evaluationCount = await simulatedEvaluations.count()
  await page.getByRole('button', { name: 'Evaluate simulated demo' }).click()
  await expect(simulatedEvaluations).toHaveCount(evaluationCount + 1, { timeout: 30_000 })
  await page.getByRole('button', { name: 'Roll back' }).click()
  await expect(page.getByRole('row').filter({ hasText: previousActiveModelId }).getByText('active', { exact: true })).toBeVisible({ timeout: 30_000 })
})
