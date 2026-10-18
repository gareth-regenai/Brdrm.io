import { defineConfig, devices } from "@playwright/test";

// The six critical journeys (FR-13.4). Locally and in CI they run against
// scripts/e2e-stack.sh; on a Render preview, set E2E_WEB_URL and E2E_API_URL to it.
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 30_000 },
  retries: 0,
  workers: 2,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_WEB_URL ?? "http://localhost:4173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // Where Chromium is already installed (as in Claude's cloud sessions), use it.
        launchOptions: process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {},
      },
    },
  ],
});
