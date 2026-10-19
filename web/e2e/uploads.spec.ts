// A new file stays in the list even when the page's first load of the list is slow and
// lands after the upload's own reload.
import { expect, test } from "@playwright/test";
import { addFile, signUp, skipSetup } from "./helpers";

test("a slow first load does not hide a new upload", async ({ page }) => {
  const company = await signUp(page);
  await skipSetup(page);
  let delayed = false;
  await page.route("**/company/uploads", async (route) => {
    if (route.request().method() !== "GET" || delayed) return route.continue();
    delayed = true;
    const response = await route.fetch();
    await new Promise((resolve) => setTimeout(resolve, 3000));
    return route.fulfill({ response });
  });
  await addFile(page, company, "xero_pnl.csv");
  // Past the delayed load, the file must still be there.
  await page.waitForTimeout(4000);
  expect(delayed).toBe(true);
  await expect(page.locator(".upload-body", { hasText: "xero_pnl.csv" })).toBeVisible();
});
