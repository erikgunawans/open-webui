/**
 * Run a program as Erik inside his signed-in ops.axiara.ai tab, through Interceptor.
 *
 * The app sits behind IAP, so admin writes go through the browser session rather than a CLI
 * credential. Two measured limits shape this:
 *
 * - `interceptor eval` stops answering somewhere between 7 and 9 KB of source (2026-09-23), so
 *   the payload is staged into `window.__jupBuf` in chunks well under that, and the program
 *   itself carries none.
 * - Each eval times out after 15 s, so the program is started without awaiting, leaves its
 *   result on `window.__jupResult`, and is polled.
 *
 * Every eval checks the host first, because the driven tab has drifted to another app before.
 */

export const HOST = process.env.JUP_OPS_HOST ?? "ops.axiara.ai";
const CHUNK = 2500;
const POLL_MS = 3000;
const TIMEOUT_MS = 10 * 60 * 1000;

const guard = `if (location.host !== ${JSON.stringify(HOST)}) return 'WRONG HOST ' + location.host;`;

async function interceptor(args: string[]): Promise<string> {
  const proc = Bun.spawn(["interceptor", ...args], { stdout: "pipe", stderr: "pipe" });
  const out = (await new Response(proc.stdout).text()).trim();
  const err = (await new Response(proc.stderr).text()).trim();
  const code = await proc.exited;
  if (code !== 0) throw new Error(`interceptor ${args[0]} exited ${code}: ${out} ${err}`.trim());
  return out.split("\n").pop() ?? "";
}

async function evalMain(program: string, expect: string): Promise<void> {
  const answer = await interceptor(["eval", "--main", program]);
  if (answer !== expect) throw new Error(`refused before anything was written: ${answer}`);
}

/**
 * Stage `payload` as `P`, then run `body` (the inside of an async function) with `P`, `call`,
 * `h` and `json` in scope. `body` must end by returning a JSON-serialisable result.
 */
export async function runInTab<T>(payload: unknown, body: string): Promise<T> {
  const text = JSON.stringify(payload);
  await evalMain(`(() => { ${guard} window.__jupBuf = ''; return 'staged'; })()`, "staged");
  for (let i = 0; i < text.length; i += CHUNK) {
    const chunk = JSON.stringify(text.slice(i, i + CHUNK));
    await evalMain(`(() => { ${guard} window.__jupBuf += ${chunk}; return 'staged'; })()`, "staged");
  }
  await evalMain(
    `(() => {
  ${guard}
  const P = JSON.parse(window.__jupBuf);
  delete window.__jupBuf;
  window.__jupResult = { state: 'running' };
  const h = { Authorization: 'Bearer ' + localStorage.token };
  const json = { ...h, 'Content-Type': 'application/json' };
  const call = async (url, init) => {
    const r = await fetch(url, init);
    const text = await r.text();
    if (!r.ok) throw new Error(url + ' -> ' + r.status + ' ' + text.slice(0, 200));
    return text ? JSON.parse(text) : null;
  };
  (async () => { ${body} })()
    .then((value) => { window.__jupResult = { state: 'done', value }; })
    .catch((err) => { window.__jupResult = { state: 'error', error: String(err) }; });
  return 'started';
})()`,
    "started",
  );

  const deadline = Date.now() + TIMEOUT_MS;
  for (;;) {
    if (Date.now() > deadline) throw new Error("timed out waiting for the in-tab program");
    await Bun.sleep(POLL_MS);
    const result = JSON.parse(await interceptor(["eval", "--main", "JSON.stringify(window.__jupResult)"]));
    if (result.state === "done") return result.value as T;
    if (result.state === "error") throw new Error(result.error);
  }
}
