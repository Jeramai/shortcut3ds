const $ = (id) => document.getElementById(id);
const worker = new Worker("worker.js", { type: "module" });
const steps = [
  "Loading the converter",
  "Preparing the app, icon and banner",
  "Making the HOME Menu icon",
  "Making the banner",
  "Packing the CIA",
];

let picked = null;
let kind = null;
let downloadUrl = null;

function mode() {
  return document.querySelector("input[name=mode]:checked").value;
}

function refresh() {
  for (const el of document.querySelectorAll("[data-show]")) {
    const need = el.dataset.show.split(" ");
    el.hidden = !need.every((word) => word === kind || word === mode());
    for (const input of el.querySelectorAll("input")) input.required = !el.hidden && input.id !== "unique-id";
  }
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
  if (!file) return;
  picked = file;
  showError("");
  $("done").hidden = true;
  busy(true);
  setStatus(steps[0]);
  worker.postMessage({ type: "inspect", name: file.name, buffer: await file.arrayBuffer() });
}

$("file").addEventListener("change", (e) => pick(e.target.files[0]));
$("change").addEventListener("click", () => $("file").click());
for (const radio of document.querySelectorAll("input[name=mode]")) radio.addEventListener("change", refresh);

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

async function input(id) {
  const file = $(id).files[0];
  return file && { name: file.name, buffer: await file.arrayBuffer() };
}

$("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  showError("");
  $("done").hidden = true;
  const files = { file: { name: picked.name, buffer: await picked.arrayBuffer() } };
  const icon = await input("icon");
  if (icon) files.icon = icon;
  const spec = {
    kind,
    mode: mode(),
    title: $("title").value,
    publisher: $("publisher").value,
    unique_id: $("unique-id").value || null,
    target: kind === "3dsx" ? $("target-3dsx").value : $("target-rom").value,
    emulator_target: $("target-mgba").value,
    rom_name: picked.name,
  };
  if (kind === "gba" && spec.mode === "native") files.emulator = await input("emulator");
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
    kind = data.value.kind;
    const stem = picked.name.replace(/\.[^.]+$/, "");
    $("title").value = data.value.title;
    $("publisher").value = data.value.publisher;
    $("target-3dsx").value = `/3ds/${stem}/${picked.name}`;
    $("target-rom").value = `/roms/gba/${picked.name}`;
    $("icon-preview").src = URL.createObjectURL(new Blob([data.value.icon], { type: "image/png" }));
    $("picked-name").textContent = picked.name;
    $("picked-kind").textContent = kind === "3dsx" ? "3DS homebrew app" : "Game Boy Advance ROM, opens in mGBA";
    $("drop").hidden = true;
    $("form").hidden = false;
    refresh();
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
