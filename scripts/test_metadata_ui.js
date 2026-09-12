const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

process.on("unhandledRejection", (reason) => {
  if (reason && /Invalid (financial )?metadata/.test(reason.message || "")) return;
  throw reason;
});

const source = fs.readFileSync("js/monthly-options.js", "utf8");

async function selectorOptions(metadata, transactions) {
  const context = {
    document: { createElement: () => ({}) },
    fetch(url) {
      const payload = url.includes("finances/finances.json") ? transactions : metadata;
      return Promise.resolve({ ok: true, json: async () => payload });
    },
    window: {},
  };
  vm.runInNewContext(source, context);
  const select = {
    firstChild: null,
    options: [],
    removeChild() {},
    appendChild(option) { this.options.push(option); },
  };
  await context.window.populateMonthlySelector(select);
  return select.options;
}

async function main() {
  const period = { period_id: "2026-01", period_label: "January 2026", start_date: "2026-01-01", end_date: "2026-01-31", file: "financials/01.2026.pdf" };
  const options = await selectorOptions({ financials: [period] }, { transactions: [] });
  assert.deepStrictEqual(options.map((option) => option.textContent), ["January 2026"]);

  const outOfOrder = [
    { period_id: "2026-02", period_label: "February 2026", start_date: "2026-02-01", end_date: "2026-02-28", file: "financials/02.2026.pdf" },
    period,
  ];
  const ordered = await selectorOptions({ financials: outOfOrder }, { transactions: [{ source_file: "02.2026.pdf" }, { source_file: "03.2026.pdf" }] });
  assert.deepStrictEqual(ordered.map((option) => option.textContent), ["January 2026", "February 2026"]);

  await assert.rejects(
    selectorOptions({ financials: "invalid" }, { transactions: [] }),
    /Invalid (financial )?metadata/,
  );
  console.log("Metadata UI tests passed: canonical periods drive selector options");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
