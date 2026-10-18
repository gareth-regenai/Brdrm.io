// The six critical journeys (FR-13.4), each driven through the page as a customer would.
// AI steps replay recorded answers, so no journey calls the live API (FR-13.2).

import { expect, test, type Page } from "@playwright/test";

import { addFile, email, invitationLink, PASSWORD, signUp, skipSetup, waitUntilReady, type Company } from "./helpers";

async function openUpdates(page: Page, company: Company): Promise<void> {
  await page.goto(`/c/${company.tenant}/pack/updates`);
  await expect(page.locator(".update").first()).toBeVisible();
}

test("1. set up through the chat", async ({ page }) => {
  const company = await signUp(page);
  await page.getByRole("button", { name: "Start setup" }).click();
  const chat = page.locator(".chat");
  await expect(chat.locator(".bubble.assistant").first()).toContainText("What are you aiming for in revenue");

  const answer = page.getByLabel("Your answer");
  await answer.fill("About £900k this year");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(chat.locator(".bubble.assistant").last()).toContainText("Which investors should see your updates");

  const investor = email("investor");
  await answer.fill(investor);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  // The chat never invites anyone without the CEO's say-so.
  await page.getByRole("button", { name: "Send invitations" }).click();
  await expect(chat).toContainText("That's everything");

  const setUp = page.getByLabel("Set up for you");
  await expect(setUp).toContainText("£75k a month");
  expect(await invitationLink(investor)).toContain("/invite?token=");
  // Next time, the dashboard is clear, and the conversation lives on in Settings.
  await page.goto(`/c/${company.tenant}`);
  await expect(page.getByText("Needs attention")).toBeVisible();
  await expect(page.locator(".chat")).toHaveCount(0);
  await page.goto(`/c/${company.tenant}/settings`);
  await expect(page.getByLabel("Set up for you")).toContainText("£75k a month");
});

test("2. upload a clean file and see tiles", async ({ page }) => {
  const company = await signUp(page);
  await skipSetup(page);
  await addFile(page, company, "xero_pnl.csv");
  await waitUntilReady(page, "xero_pnl.csv");
  const revenue = page.locator(".tile", { hasText: "Revenue" }).first();
  await expect(revenue.locator(".figure")).toContainText("£");
  // A clean file is understood with no question.
  await expect(page.locator(".upload-body", { hasText: "xero_pnl.csv" }).locator(".question")).toHaveCount(0);
  await revenue.click();
  await expect(page.locator(".trace")).toContainText("Exact value");
});

test("3. upload a messy file and see tiles with at most one question", async ({ page }) => {
  const company = await signUp(page);
  await skipSetup(page);
  await addFile(page, company, "finance_ambiguous.csv");
  const upload = page.locator(".upload-body", { hasText: "finance_ambiguous.csv" });
  const question = upload.locator(".question");
  await expect(question).toHaveCount(1);
  await question.getByRole("button").first().click();

  await waitUntilReady(page, "finance_ambiguous.csv");
  await expect(question).toHaveCount(0);
  await expect(page.locator(".tile .figure").first()).toBeVisible();
});

test("4. draft commentary that passes the number check", async ({ page }) => {
  const company = await signUp(page);
  await skipSetup(page);
  await addFile(page, company, "xero_pnl.csv");
  await waitUntilReady(page, "xero_pnl.csv");

  await page.goto(`/c/${company.tenant}/pack`);
  await expect(page.getByText("Drafted by Claude").first()).toBeVisible();
  await expect(page.getByText("Number check: passed")).toBeVisible();
  await openUpdates(page, company);
  await expect(page.locator(".section-headline").first()).toContainText("Revenue grew 3.5%");
});

test("5. send an update and edit it", async ({ page }) => {
  const company = await signUp(page);
  await skipSetup(page);
  await addFile(page, company, "xero_pnl.csv");
  await waitUntilReady(page, "xero_pnl.csv");

  await openUpdates(page, company);
  const update = page.locator(".update").first();
  await update.getByRole("button", { name: "Approve and share" }).click();
  await expect(update.locator(".pill", { hasText: "Shared" })).toBeVisible();

  const revenue = update.locator(".update-figure", { hasText: "Revenue" }).first();
  await revenue.getByRole("button", { name: "Change" }).click();
  await update.locator(".figure-edit input[name=value]").fill("80000");
  await update.locator(".figure-edit").getByRole("button", { name: "Save" }).click();
  await expect(update).toContainText("Last edited");
  await expect(revenue).toContainText("Changed by Ellie Marsh");
});

// Also FR-1.4: from sign-up to an update investors can see, from a raw finance export and a
// raw pipeline export, with no template.
test("6. an investor sees the portfolio, opens a company, traces a figure and comments", async ({ page, browser }) => {
  const company = await signUp(page, "Northpath");
  await skipSetup(page);
  await addFile(page, company, "xero_pnl.csv");
  await waitUntilReady(page, "xero_pnl.csv");
  await addFile(page, company, "hubspot_deals.csv");
  await waitUntilReady(page, "hubspot_deals.csv");
  await openUpdates(page, company);
  for (const update of await page.locator(".update").all()) {
    await update.getByRole("button", { name: "Approve and share" }).click();
    await expect(update.locator(".pill", { hasText: "Shared" })).toBeVisible();
  }

  const investor = email("investor");
  await page.goto(`/c/${company.tenant}/team`);
  await page.fill("input[name=email]", investor);
  await page.getByRole("button", { name: "Send invitation" }).click();
  await expect(page.getByText(`Invitation sent to ${investor}`)).toBeVisible();

  const context = await browser.newContext();
  const them = await context.newPage();
  await them.goto(await invitationLink(investor));
  await them.fill("input[name=name]", "Priya Shah");
  await them.fill("input[name=email]", investor);
  await them.fill("input[name=password]", PASSWORD);
  await them.click("button.primary");
  await them.waitForURL(/\/(c\/|portfolio)/);

  await them.goto("/portfolio");
  const card = them.locator(".company-card", { hasText: "Northpath" });
  await expect(card).toBeVisible();
  await card.click();
  await expect(them.getByText("The Full Picture")).toBeVisible();

  await them.getByRole("tab", { name: "Cashflow" }).click();
  await them.locator(".tile", { hasText: "Revenue" }).first().click();
  await expect(them.locator(".trace")).toContainText("Exact value");
  await them.getByRole("tab", { name: "Market validation" }).click();
  await expect(them.locator(".tile").first()).toBeVisible();

  // Investors view and comment, and never approve or change.
  await them.getByRole("tab", { name: "Updates" }).click();
  const update = them.locator(".update").first();
  // Wait for the figures first, so the next two checks look at a loaded update.
  await expect(update.locator(".update-figure").first()).toBeVisible();
  await expect(update.getByRole("button", { name: "Approve and share" })).toHaveCount(0);
  await expect(update.getByRole("button", { name: "Change" })).toHaveCount(0);
  await update.getByPlaceholder("Add a comment. Type @ to tag someone").fill("Is the Q4 pipeline all enterprise?");
  await update.getByRole("button", { name: "Send", exact: true }).click();
  await expect(update.locator(".comment", { hasText: "Is the Q4 pipeline all enterprise?" })).toBeVisible();

  await openUpdates(page, company);
  await expect(page.locator(".comment", { hasText: "Is the Q4 pipeline all enterprise?" })).toBeVisible();
  await context.close();
});
