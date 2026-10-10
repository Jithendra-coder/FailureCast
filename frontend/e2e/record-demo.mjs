import { chromium } from '@playwright/test'
import { copyFile, mkdir, mkdtemp, rm } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const videoPath = path.resolve(process.env.FAILURECAST_DEMO_VIDEO || path.join(projectRoot, 'docs/demo-video/failurecast-demo.webm'))
const baseUrl = process.env.FAILURECAST_E2E_URL || 'http://127.0.0.1:8000'
const password = process.env.FAILURECAST_E2E_PASSWORD
if (!password) throw new Error('Set FAILURECAST_E2E_PASSWORD for the isolated demo workspace.')

const temporaryVideoDirectory = await mkdtemp(path.join(os.tmpdir(), 'failurecast-demo-'))
await mkdir(path.dirname(videoPath), { recursive: true })
const browser = await chromium.launch()
const context = await browser.newContext({
  acceptDownloads: true,
  viewport: { width: 1920, height: 1080 },
  recordVideo: { dir: temporaryVideoDirectory, size: { width: 1920, height: 1080 } },
})
const page = await context.newPage()
const video = page.video()

const caption = async (message, duration = 2600) => {
  await page.evaluate((text) => {
    const target = document.querySelector('#failurecast-demo-caption span')
    if (target) target.textContent = text
  }, message)
  await page.waitForTimeout(duration)
}

let recordingComplete = false
const countCompletedJobs = async (locator, before) => {
  const deadline = Date.now() + 180_000
  while (Date.now() < deadline) {
    if (await locator.count() > before) return
    await page.waitForTimeout(750)
  }
  throw new Error('The demo training job did not complete within three minutes.')
}

try {
  await page.goto(baseUrl)
  await page.getByRole('heading', { name: 'See what the engine data is telling you.' }).waitFor()
  await page.evaluate(() => {
    const style = document.createElement('style')
    style.textContent = '#failurecast-demo-caption{position:fixed;z-index:2147483647;left:50%;bottom:28px;transform:translateX(-50%);max-width:84vw;padding:16px 26px;border:1px solid #ffffff26;border-radius:14px;background:#10243af2;box-shadow:0 12px 40px #08132255;color:#fff;font:600 22px/1.4 Inter,system-ui,sans-serif;letter-spacing:.01em;text-align:center;pointer-events:none;backdrop-filter:blur(14px)}#failurecast-demo-caption b{display:block;margin-bottom:4px;color:#72dfc4;font-size:12px;letter-spacing:.14em}'
    document.head.append(style)
    const frame = document.createElement('div')
    frame.id = 'failurecast-demo-caption'
    const brand = document.createElement('b')
    brand.textContent = 'FAILURECAST · RESEARCH DEMO'
    const text = document.createElement('span')
    text.textContent = 'A reviewable remaining-useful-life forecasting workflow.'
    frame.append(brand, text)
    document.body.append(frame)
  })
  await caption('Forecasting and model review from simulated engine history.', 4200)
  await page.screenshot({ path: path.join(projectRoot, 'docs/demo-video/failurecast-demo-poster.png') })
  await page.getByRole('button', { name: /Get started/ }).click()
  await page.getByLabel('Administrator password').fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.getByRole('heading', { name: 'See the signal. Plan the review.' }).waitFor()
  await caption('One workspace for fleet context, active model evidence, and review priorities.', 4200)

  await page.getByRole('button', { name: 'Inspect engine' }).click()
  await page.getByRole('heading', { name: 'Engine health' }).waitFor()
  await caption('Inspect observed sensor history alongside the model estimate.', 4200)

  await page.getByRole('button', { name: 'Replay studio' }).click()
  await page.getByRole('heading', { name: 'Trajectory replay' }).waitFor()
  const restartReplay = page.getByRole('button', { name: 'Restart replay' })
  const resetReplay = page.getByRole('button', { name: 'Reset replay' })
  if (await restartReplay.isVisible()) await restartReplay.click()
  else if (await resetReplay.isVisible()) await resetReplay.click()
  else await page.getByRole('button', { name: /^(Start replay|Resume)$/ }).click()
  await page.getByRole('button', { name: 'Pause' }).waitFor()
  await caption('Replay simulated observations through the active model and alert thresholds.', 4800)
  await page.getByRole('button', { name: 'Pause' }).click()

  await page.getByRole('button', { name: 'Experiments' }).click()
  const completedJobs = page.getByText('completed', { exact: true })
  const completedBefore = await completedJobs.count()
  await page.getByRole('button', { name: 'Queue training job' }).click()
  await caption('Train a candidate against the selected dataset version.', 3200)
  await countCompletedJobs(completedJobs, completedBefore)

  await page.getByRole('button', { name: 'Model registry' }).click()
  const previousActiveRow = page.getByRole('row').filter({ has: page.getByText('active', { exact: true }) })
  const previousActiveModelId = await previousActiveRow.getByRole('cell').first().innerText()
  await page.getByRole('button', { name: 'Review & promote' }).waitFor({ timeout: 30_000 })
  await caption('Review validation evidence before explicit model activation.', 3600)
  await page.getByRole('button', { name: 'Review & promote' }).click()
  await page.getByRole('heading', { name: 'Activate this model version?' }).waitFor()
  await page.getByRole('button', { name: 'Approve & activate' }).click()
  const evaluate = page.getByRole('button', { name: 'Evaluate simulated demo' })
  await evaluate.waitFor({ timeout: 30_000 })
  await caption('Promotion is explicit, and the prior active version remains available.', 3600)

  const simulatedEvaluations = page.getByText('Simulated evaluation', { exact: true })
  const evaluationCount = await simulatedEvaluations.count()
  const [download] = await Promise.all([page.waitForEvent('download'), evaluate.click()])
  await download.delete()
  const evaluationDeadline = Date.now() + 30_000
  while (Date.now() < evaluationDeadline && await simulatedEvaluations.count() <= evaluationCount) {
    await page.waitForTimeout(250)
  }
  if (await simulatedEvaluations.count() <= evaluationCount) throw new Error('The simulated evaluation was not recorded in the audit history.')
  await caption('This evaluation uses generated demo data; it is not live equipment evidence.', 4200)

  await page.getByRole('button', { name: 'Roll back' }).click()
  await previousActiveRow.getByText('active', { exact: true }).waitFor({ timeout: 30_000 })
  await caption('Rollback restores the previous approved model and keeps the action recorded.', 3600)
  await page.getByRole('button', { name: 'Overview' }).click()
  await page.getByRole('heading', { name: 'See the signal. Plan the review.' }).waitFor()
  await caption('Research estimates only · no live equipment connection or control.', 5200)
  recordingComplete = true
} finally {
  await context.close()
  await browser.close()
  if (!recordingComplete) await rm(temporaryVideoDirectory, { recursive: true, force: true })
}

try {
  await copyFile(await video.path(), videoPath)
  console.log(`Captioned demo video saved to ${videoPath}`)
} finally {
  await rm(temporaryVideoDirectory, { recursive: true, force: true })
}
