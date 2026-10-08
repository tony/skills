#!/usr/bin/env bash
# A small app with an unrelated signup form and payment webhook handler.
set -euo pipefail

git init -b main >/dev/null
mkdir -p src/signup src/payments tests

cat >src/signup/form.js <<'JS'
export function submitSignup(fields) {
  return fetch("/api/signup", { method: "POST", body: JSON.stringify(fields) });
}
JS

cat >src/payments/webhook.js <<'JS'
export async function handleWebhook(event, retry = 3) {
  for (let i = 0; i < retry; i++) {
    if (await deliver(event)) return true;
  }
  return false;
}
async function deliver(event) {
  return Math.random() > 0.5;
}
JS

cat >tests/webhook.test.js <<'JS'
import { handleWebhook } from "../src/payments/webhook.js";
test("retries until delivered", async () => {
  expect(await handleWebhook({ id: 1 })).toBe(true);
});
JS

git add -A
git -c user.name=eval -c user.email=eval@example.com commit -qm "Add signup form and payment webhook"
