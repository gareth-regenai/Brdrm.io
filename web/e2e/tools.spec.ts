// Connecting a tool instead of exporting a file. Only the demo connector is built; real
// tools show as coming soon until each one is.

import { expect, test } from "@playwright/test";

import { signUp, skipSetup } from "./helpers";

test("7. connect a tool and its data arrives with no export", async ({ page }) => {
  const company = await signUp(page);
  await skipSetup(page);
  await page.goto(`/c/${company.tenant}/files`);

  const tools = page.getByRole("region", { name: "Your tools" });
  await expect(tools.locator(".tool", { hasText: "Xero" })).toContainText("Coming soon");
  await expect(tools.getByRole("button", { name: "Connect Xero" })).toHaveCount(0);

  const demo = tools.locator(".tool", { hasText: "Demo company" });
  await demo.getByRole("button", { name: "Connect Demo company" }).click();
  await expect(demo).toContainText("Connected by Ellie Marsh");
  await expect(demo.locator(".pill")).toHaveText("Connected");

  // What it sent takes a file's path: understood, calculated, and an update drafted.
  for (const name of ["Demo company: profit and loss.csv", "Demo company: deals.csv"]) {
    await expect(page.locator(".upload-body", { hasText: name }).locator(".pill.ok")).toBeVisible({ timeout: 60_000 });
  }
  await expect(page.locator(".tile", { hasText: "Revenue" }).first().locator(".figure")).toContainText("£");
  await page.goto(`/c/${company.tenant}/pack/updates`);
  await expect(page.locator(".update")).toHaveCount(2);

  // Nothing new since the last pull adds nothing; disconnecting keeps what arrived.
  await page.goto(`/c/${company.tenant}/files`);
  await demo.getByRole("button", { name: "Pull now" }).click();
  await expect(demo).toContainText("Last pulled");
  await expect(page.locator(".upload-body")).toHaveCount(2);
  await demo.getByRole("button", { name: "Disconnect" }).click();
  await expect(demo.locator(".pill")).toHaveText("Not connected");
  await expect(page.locator(".upload-body")).toHaveCount(2);
});
