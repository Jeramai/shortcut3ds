const $ = (id) => document.getElementById(id);
const worker = new Worker("worker.js", { type: "module" });
const steps = [
  "Loading the converter",
  "Preparing the app, icon and banner",
  "Making the HOME Menu icon",
  "Making the banner",
  "Packing the CIA",
];

let catalogue = [];
const optionInputs = new Map();
let picked = null;
let pending = null;
let source = null;
let downloadUrl = null;

function mode() {
  return document.querySelector("input[name=mode]:checked").value;
}

function element(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value !== undefined && value !== false) el.setAttribute(key, value === true ? "" : value);
  }
  el.append(...children);
  return el;
}

function renderOptions() {
  const box = $("options");
  box.replaceChildren();
  $("target-field").hidden = mode() !== "shortcut";
  $("target").disabled = $("target-field").hidden;
  for (const option of source.options) {
    const need = option.needs[mode()];
    if (!need || need === "list") continue;
    const id = `option-${option.name}`;
    const key = `${source.name}/${option.name}/${need}`;
    if (!optionInputs.has(key)) {
      optionInputs.set(
        key,
        need === "file"
          ? element("input", { type: "file", id, accept: option.accept || undefined, required: !option.bundled })
          : element("input", {
              id,
              value: option.sd_default,
              pattern: need === "sd_path" ? "/.*" : undefined,
              required: need === "sd_path",
            }),
      );
    }
    const input = optionInputs.get(key);
    const label = element("label", { for: id }, need === "sd_path" ? `Where ${option.label} is on the SD card` : option.label, input);
    const help = element("span", { class: "muted" });
    if (option.bundled && need === "file") {
      help.append(`Leave empty to use the included ${option.bundled}, or choose your own. `);
    } else if (option.bundled && need === "sd_path") {
      const download = element("a", { href: `tools/${option.bundled}`, download: option.bundled }, `Download ${option.bundled}`);
      help.append("Not on your card yet? ", download, " and copy it there.");
    } else {
      if (option.help) help.append(option.help + " ");
      if (option.link) help.append(element("a", { href: option.link }, "Download"));
    }
    if (help.childNodes.length) label.append(help);
    box.append(label);
  }
  $("notes").textContent = source.notes.join(" ");
  $("notes").hidden = source.notes.length === 0;
}

function showError(message) {
  $("error").textContent = message;
  $("error").hidden = !message;
}

function setStatus(text) {
  $("status").hidden = false;
  $("status-text").textContent = text;
  const index = Math.max(0, steps.findIndex((step) => text.startsWith(step)));
  $("status").querySelector(".bar span").style.transform = `scaleX(${(index + 1) / (steps.length + 1)})`;
}

function busy(on) {
  $("build").disabled = on;
  $("file").disabled = on;
  if (!on) $("status").hidden = true;
}

async function pick(file) {
  if (!file || $("file").disabled) return;
  pending = file;
  showError("");
  $("done").hidden = true;
  busy(true);
  setStatus(steps[0]);
  worker.postMessage({ type: "inspect", name: file.name, buffer: await file.arrayBuffer() });
}

async function readInput(input) {
  const file = input.files[0];
  return file && { name: file.name, buffer: await file.arrayBuffer() };
}

fetch("sources.json", { cache: "no-store" })
  .then((response) => response.json())
  .then((list) => {
    catalogue = list;
    const extensions = list.flatMap((s) => s.extensions);
    $("file").accept = extensions.join(",");
    $("drop-kinds").textContent = extensions.join(" or ");
  })
  .catch(() => showError("The page could not load its file types. Reload to try again."));

$("file").addEventListener("change", (e) => pick(e.target.files[0]));
$("change").addEventListener("click", () => $("file").click());
for (const radio of document.querySelectorAll("input[name=mode]")) radio.addEventListener("change", renderOptions);

const drop = $("drop");
drop.addEventListener("dragover", (e) => {
  e.preventDefault();
  drop.classList.add("over");
});
drop.addEventListener("dragleave", () => drop.classList.remove("over"));
drop.addEventListener("drop", (e) => {
  e.preventDefault();
  drop.classList.remove("over");
  pick(e.dataTransfer.files[0]);
});

$("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  showError("");
  $("done").hidden = true;
  const files = { file: { name: picked.name, buffer: await picked.arrayBuffer() } };
  const icon = await readInput($("icon"));
  if (icon) files.icon = icon;
  const spec = {
    source: source.name,
    mode: mode(),
    title: $("title").value,
    publisher: $("publisher").value,
    unique_id: $("unique-id").value || null,
    target: $("target").value,
    options: {},
  };
  for (const option of source.options) {
    const need = option.needs[spec.mode];
    const input = $(`option-${option.name}`);
    if (!input) continue;
    if (need === "file") {
      files[`option:${option.name}`] =
        (await readInput(input)) || (option.bundled && { name: option.bundled, url: `tools/${option.bundled}` });
    }
    else if (need === "sd_path") spec.options[option.name] = { sd_path: input.value };
    else spec.options[option.name] = input.value;
  }
  busy(true);
  setStatus(steps[0]);
  worker.postMessage({ type: "build", spec, files });
});

worker.onerror = (event) => {
  busy(false);
  showError(`The converter could not start: ${event.message || "check your connection and reload"}`);
};

worker.onmessage = ({ data }) => {
  if (data.type === "status") {
    setStatus(data.value);
  } else if (data.type === "inspected") {
    busy(false);
    const found = catalogue.find((s) => s.name === data.value.source);
    if (!found) {
      showError("The page is out of date. Reload to try again.");
      return;
    }
    picked = pending;
    source = found;
    const stem = picked.name.replace(/\.[^.]+$/, "");
    $("title").value = data.value.title;
    $("publisher").value = data.value.publisher;
    $("target").value = `${source.sd_folder.replace("{stem}", stem)}/${picked.name}`;
    $("icon-preview").src = URL.createObjectURL(new Blob([data.value.icon], { type: "image/png" }));
    $("picked-name").textContent = picked.name;
    $("picked-kind").textContent = source.label;
    $("drop").hidden = true;
    $("form").hidden = false;
    renderOptions();
  } else if (data.type === "built") {
    busy(false);
    if (downloadUrl) URL.revokeObjectURL(downloadUrl);
    downloadUrl = URL.createObjectURL(new Blob([data.value], { type: "application/octet-stream" }));
    $("download").href = downloadUrl;
    $("download").download = data.filename;
    $("download").textContent = `Download ${data.filename}`;
    const size = (data.value.byteLength / 1048576).toFixed(1);
    $("done-info").textContent = `${size} MB, title ID ${data.titleId}. Install it with FBI.`;
    $("done").hidden = false;
  } else if (data.type === "error") {
    busy(false);
    showError(data.value);
  }
};
