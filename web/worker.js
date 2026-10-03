import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";
import createMakerom from "./tools/makerom.mjs";
import createBannertool from "./tools/bannertool.mjs";

const factories = { makerom: createMakerom, bannertool: createBannertool };
let ready = null;

function engine() {
  ready ??= start().catch((error) => {
    ready = null;
    throw error;
  });
  return ready;
}

async function start() {
  post("status", "Loading the converter (about 15 MB, only the first time)");
  const py = await loadPyodide();
  await py.loadPackage(["pillow", "micropip"]);
  const manifest = await (await fetch("manifest.json", { cache: "no-store" })).json();
  await py.pyimport("micropip").install(new URL(manifest.wheel, self.location.href).href);
  py.runPython("from shortcut3ds import web");
  return py;
}

function post(type, value, extra = {}) {
  self.postMessage({ type, value, ...extra });
}

function writeInput(fs, name, buffer) {
  const path = "/input/" + name;
  fs.mkdirTree(path.slice(0, path.lastIndexOf("/")));
  fs.writeFile(path, new Uint8Array(buffer));
  return path;
}

function walk(fs, dir, visit, rel = "") {
  for (const name of fs.readdir(dir + "/" + rel)) {
    if (name === "." || name === "..") continue;
    const path = rel ? rel + "/" + name : name;
    if (fs.isDir(fs.stat(dir + "/" + path).mode)) {
      visit(path, null);
      walk(fs, dir, visit, path);
    } else {
      visit(path, fs.readFile(dir + "/" + path));
    }
  }
}

async function runTool(fs, tool, args) {
  let log = "";
  const mod = await factories[tool]({
    print: (s) => (log += s + "\n"),
    printErr: (s) => (log += s + "\n"),
  });
  mod.FS.mkdir("/work");
  walk(fs, "/work", (path, data) =>
    data === null ? mod.FS.mkdirTree("/work/" + path) : mod.FS.writeFile("/work/" + path, data),
  );
  mod.FS.chdir("/work");
  const code = mod.callMain(args);
  if (code !== 0) throw new Error(`${tool} failed:\n${log}`);
  walk(mod.FS, "/work", (path, data) =>
    data === null ? fs.mkdirTree("/work/" + path) : fs.writeFile("/work/" + path, data),
  );
}

const handlers = {
  async inspect({ name, buffer }) {
    const p = await engine();
    const info = JSON.parse(p.globals.get("web").inspect(writeInput(p.FS, name, buffer)));
    info.icon = p.FS.readFile("/work-icon.png");
    post("inspected", info);
  },

  async build({ spec, files }) {
    const p = await engine();
    for (const [key, file] of Object.entries(files)) {
      if (!file) continue;
      const path = writeInput(p.FS, `${key.replace(":", "-")}/${file.name}`, file.buffer);
      if (key.startsWith("option:")) spec.options[key.slice(7)] = { file: path };
      else spec[key] = path;
    }
    post("status", "Preparing the app, icon and banner");
    const plan = JSON.parse(p.globals.get("web").prepare(JSON.stringify(spec)));
    const labels = { makesmdh: "Making the HOME Menu icon", makebanner: "Making the banner" };
    for (const [tool, ...args] of plan.commands) {
      post("status", labels[args[0]] || "Packing the CIA");
      await runTool(p.FS, tool, args);
    }
    const cia = p.FS.readFile("/work/out.cia");
    post("built", cia, { filename: plan.filename, titleId: plan.title_id });
  },
};

self.onmessage = async ({ data }) => {
  try {
    await handlers[data.type](data);
  } catch (error) {
    const message = String(error.message || error);
    const last = message.trim().split("\n").pop();
    const pythonError = last.match(/^[\w.]+: (.+)$/);
    post("error", pythonError ? pythonError[1] : message);
  }
};
