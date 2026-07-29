import { test, expect } from "@playwright/test";

// #464: seed scenarios — three smoke checks that prove the harness
// works against a built llmwiki demo site. Real generated specs land
// via #466's Generator pass once this bootstrap is on master.

test.describe("seed — site reachability", () => {
  test("home renders the LLM Wiki hero", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/LLM Wiki/);
    await expect(page.locator("h1").first()).toContainText("LLM Wiki");
  });

  test("nav has the canonical links", async ({ page }) => {
    await page.goto("/");
    // Matches llmwiki.build.nav_bar labels (Changelog was replaced by Analytics/Raw).
    for (const label of ["Home", "Raw", "Graph", "Projects", "Sessions", "Analytics", "Docs"]) {
      await expect(
        page.getByRole("link", { name: label }).first(),
      ).toBeVisible();
    }
  });

  test("graph page carries the site nav (regression for #456)", async ({
    page,
  }) => {
    await page.goto("/graph.html");
    await expect(page.getByRole("link", { name: "Home" }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Graph" }).first()).toBeVisible();
  });
});
