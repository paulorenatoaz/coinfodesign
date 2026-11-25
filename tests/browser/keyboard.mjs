// With the built report served locally and a disposable Chrome debugging session:
// node tests/browser/keyboard.mjs http://127.0.0.1:8000/ http://127.0.0.1:9222
import assert from "node:assert/strict";

const [, , siteUrl, chromeUrl] = process.argv;
assert(siteUrl && chromeUrl, "Pass the report URL and the Chrome DevTools HTTP URL.");
const targets = await (await fetch(new URL("/json/list", chromeUrl))).json();
const ws = new WebSocket(targets.find(target => target.type === "page").webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  ws.addEventListener("open", resolve, {once: true});
  ws.addEventListener("error", reject, {once: true});
});
let id = 0;
const pending = new Map();
ws.addEventListener("message", ({data}) => {
  const reply = JSON.parse(data);
  if (!reply.id) return;
  const {resolve, reject} = pending.get(reply.id);
  pending.delete(reply.id);
  if (reply.error) reject(new Error(reply.error.message));
  else resolve(reply.result);
});

function send(method, params) {
  return new Promise((resolve, reject) => {
    pending.set(++id, {resolve, reject});
    ws.send(JSON.stringify({id, method, params}));
  });
}

async function evaluate(expression) {
  const result = await send("Runtime.evaluate", {expression, returnByValue: true});
  assert(!result.exceptionDetails, result.exceptionDetails?.exception?.description);
  return result.result.value;
}

async function click(selector) {
  const [x, y] = await evaluate(`(() => {
    const target = document.querySelector(${JSON.stringify(selector)});
    target.scrollIntoView({block: "center"});
    const rect = target.getBoundingClientRect();
    return [rect.left + rect.width / 2, rect.top + rect.height / 2];
  })()`);
  await send("Input.dispatchMouseEvent", {type: "mousePressed", x, y, button: "left", clickCount: 1});
  await send("Input.dispatchMouseEvent", {type: "mouseReleased", x, y, button: "left", clickCount: 1});
}

async function key(code, value = code, keyCode = 13) {
  const params = {code, key: value, windowsVirtualKeyCode: keyCode};
  const text = code === "Enter" ? "\r" : (code === "Space" ? " " : "");
  await send("Input.dispatchKeyEvent", {type: text ? "keyDown" : "rawKeyDown", text, ...params});
  await send("Input.dispatchKeyEvent", {type: "keyUp", ...params});
}

const classroom = '[id="row-n512-tau0.10"]';
const other = '[id="row-n2-tau0.10"]';
const choose = row => row + " .choose";
const disclosure = row => row + " .details-btn";
const press = async (selector, ...keys) => {
  await evaluate(`document.querySelector(${JSON.stringify(selector)}).focus()`);
  await key(...keys);
  assert(await evaluate(`document.activeElement.matches(${JSON.stringify(selector)})`), "Activation moved focus");
};
const selected = () => evaluate('document.querySelector("#panorama-table .selected").id');
const expanded = row => evaluate(`(() => {
  const button = document.querySelector(${JSON.stringify(disclosure(row))});
  const detail = document.getElementById(button.getAttribute("aria-controls"));
  return [button.getAttribute("aria-expanded"), detail.hidden];
})()`);
const hasFocus = selector => evaluate(`document.activeElement.matches(${JSON.stringify(selector)})`);
const space = ["Space", " ", 32];

try {
  await send("Page.navigate", {url: siteUrl});
  let ready = false;
  for (let i = 0; !ready && i < 100; i++) {
    await new Promise(resolve => setTimeout(resolve, 30));
    ready = await evaluate('document.getElementById("n-select")?.disabled === false');
  }
  assert(ready, "The report did not load.");
  assert.equal(await selected(), "row-n512-tau0.10");

  await click(choose(other));
  assert.equal(await selected(), "row-n2-tau0.10");
  await press(choose(classroom), "Enter");
  assert.equal(await selected(), "row-n512-tau0.10");
  assert.equal(await evaluate('getComputedStyle(document.activeElement).outlineStyle'), "solid");
  await press(choose(other), ...space);
  assert.equal(await selected(), "row-n2-tau0.10");
  assert.deepEqual(await evaluate('[document.querySelector("#n-select").value, document.querySelector("#tau-select").value]'), ["2", "0.10"]);

  await click(disclosure(classroom));
  assert.deepEqual(await expanded(classroom), ["true", false]);
  assert(await hasFocus(disclosure(classroom)));
  assert.equal(await selected(), "row-n2-tau0.10");
  await click(disclosure(classroom));
  assert.deepEqual(await expanded(classroom), ["false", true]);

  for (const keys of [["Enter"], space]) {
    await press(disclosure(classroom), ...keys);
    assert.deepEqual(await expanded(classroom), ["true", false]);
    assert.equal(await selected(), "row-n2-tau0.10");
    await press(disclosure(classroom), ...keys);
    assert.deepEqual(await expanded(classroom), ["false", true]);
    assert.equal(await selected(), "row-n2-tau0.10");
  }

  await click(disclosure(classroom));
  await press("#p1", "End", "End", 35);
  assert.equal(await evaluate('document.getElementById("p1-out").textContent'), "100%");
  assert.deepEqual(await expanded(classroom), ["true", false]);
  assert.equal(await selected(), "row-n2-tau0.10");

  console.log("Seleção e detalhes verificados no Chrome com clique, Enter e Espaço.");
} finally {
  ws.close();
}
