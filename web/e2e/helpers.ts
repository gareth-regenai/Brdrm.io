import { expect, type Page } from "@playwright/test";
import { fileURLToPath } from "node:url";

export const API = process.env.E2E_API_URL ?? "http://localhost:8000";
export const PASSWORD = "correct horse battery";
const FILES = fileURLToPath(new URL("../../backend/tests/fixtures/files/", import.meta.url));

let n = 0;
export function email(who: string): string {
  return `${who}-${Date.now()}-${n++}@example.com`;
}

export interface Company {
  tenant: string;
  email: string;
}

// Sign up through the page, as a new customer would. Lands on the dashboard.
export async function signUp(page: Page, company = "Kestrel Field", name = "Ellie Marsh"): Promise<Company> {
  const address = email("ceo");
  await page.goto("/signup");
  await page.fill("input[name=company_name]", company);
  await page.fill("input[name=name]", name);
  await page.fill("input[name=email]", address);
  await page.fill("input[name=password]", PASSWORD);
  await page.click("button.primary");
  await expect(page.getByText("Set up in a minute")).toBeVisible();
  const tenant = new URL(page.url()).pathname.split("/")[2];
  return { tenant, email: address };
}

export async function skipSetup(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Skip for now" }).click();
  await expect(page.getByText("Set up in a minute")).toBeHidden();
}

export async function addFile(page: Page, company: Company, name: string): Promise<void> {
  await page.goto(`/c/${company.tenant}/files`);
  await page.setInputFiles(".dropzone input[type=file]", FILES + name);
  await expect(page.locator(".upload-body", { hasText: name })).toBeVisible();
}

export async function waitUntilReady(page: Page, name: string): Promise<void> {
  const upload = page.locator(".upload-body", { hasText: name });
  await expect(upload.locator(".pill.ok")).toBeVisible({ timeout: 60_000 });
}

// The invitation link, read from the capture mailer (MAILER=capture on the stack or preview).
export async function invitationLink(to: string): Promise<string> {
  let link: string | undefined;
  await expect
    .poll(async () => {
      const r = await fetch(`${API}/e2e/mail?to=${encodeURIComponent(to)}`);
      const mail = (await r.json()) as { body: string }[];
      link = mail.map((m) => m.body.match(/https?:\/\/\S+\/invite\?token=[\w-]+/)?.[0]).find(Boolean);
      return link;
    })
    .toBeTruthy();
  return new URL(link!).pathname + new URL(link!).search;
}
