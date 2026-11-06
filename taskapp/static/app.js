"use strict";
const $ = (selector) => document.querySelector(selector);
let filter = "all";
let currentTheme = localStorage.getItem('theme') || 'light';
applyTheme();
function applyTheme() {
  const toggle = $("#theme-toggle");
  if (currentTheme === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
    toggle.setAttribute('aria-pressed', 'true');
    toggle.querySelector('.icon-sun').style.display = 'inline';
    toggle.querySelector('.icon-moon').style.display = 'none';
  } else {
    document.documentElement.removeAttribute('data-theme');
    toggle.setAttribute('aria-pressed', 'false');
    toggle.querySelector('.icon-sun').style.display = 'none';
    toggle.querySelector('.icon-moon').style.display = 'inline';
  }
  localStorage.setItem('theme', currentTheme);
}
$("#theme-toggle").addEventListener('click', () => {
  currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
  applyTheme();
});
let editing = null;
let loadSequence = 0;

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options, headers: {"Content-Type": "application/json", ...options.headers},
  });
  if (!response.ok) throw new Error(response.status === 503
    ? "La base de datos no está disponible. Intenta actualizar en un momento."
    : "No se pudo completar la operación. Revisa los datos e inténtalo otra vez.");
  return response.status === 204 ? null : response.json();
}

function showError(error) {
  $("#error").textContent = error.message || "Ocurrió un error de conexión.";
  $("#error").hidden = false;
}

function resetForm() {
  editing = null;
  $("#task-form").reset();
  $("#form-heading").textContent = "Mis tareas";
  // Updated button text to match new requirement
  $("#submit").textContent = "Crear tarea ↗";
  $("#cancel").hidden = true;
}

function taskCard(task) {
  const card = document.createElement("article");
  card.className = `task${task.completed ? " done" : ""}`;
  card.dataset.testid = "task-card";
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = task.completed;
  checkbox.setAttribute("aria-label", `Completar ${task.title}`);
  checkbox.addEventListener("change", async () => {
    checkbox.disabled = true;
    try {
      await api(`/api/tasks/${task.id}`, {method: "PATCH", body: JSON.stringify({completed: checkbox.checked})});
      await reload();
    } catch (error) { checkbox.checked = task.completed; showError(error); }
    finally { checkbox.disabled = false; }
  });
  const content = document.createElement("div");
  const title = document.createElement("h3");
  title.textContent = task.title;
  const description = document.createElement("p");
  description.textContent = task.description;
  const state = document.createElement("small");
  state.textContent = `${task.completed ? "COMPLETADA" : "PENDIENTE"} · ${new Date(task.created_at).toLocaleDateString("es-PE")}`;
  content.append(title, description, state);
  const actions = document.createElement("div");
  actions.className = "task-actions";
  const edit = document.createElement("button");
  edit.textContent = "Editar";
  edit.addEventListener("click", () => {
    editing = task.id;
    $("#title").value = task.title;
    $("#description").value = task.description;
    $("#form-heading").textContent = "Editar tarea";
    $("#submit").textContent = "Guardar cambios ↗";
    $("#cancel").hidden = false;
    $("#title").focus();
  });
  const remove = document.createElement("button");
  remove.textContent = "Eliminar";
  remove.addEventListener("click", async () => {
    if (!window.confirm("¿Eliminar esta tarea de demostración?")) return;
    remove.disabled = true;
    try {
      await api(`/api/tasks/${task.id}`, {method: "DELETE"});
      if (editing === task.id) resetForm();
      await reload();
    } catch (error) { showError(error); }
    finally { remove.disabled = false; }
  });
  actions.append(edit, remove);
  card.append(checkbox, content, actions);
  return card;
}

async function updatePendingCounter() {
  try {
    const tasks = await api("/api/tasks?status=pending");
    const count = tasks.length;
    const counterText = $("#pending-count-text");
    if (counterText) {
      counterText.textContent = `${count} ${count === 1 ? "pendiente" : "pendientes"}`;
    }
  } catch (e) {
    // Silently ignore counter update errors
  }
}

async function reload() {
  const sequence = ++loadSequence;
  $("#error").hidden = true;
  try {
    const tasks = await api(`/api/tasks?status=${filter}`);
    if (sequence !== loadSequence) return;
    $("#task-list").replaceChildren(...tasks.map(taskCard));
    $("#empty").hidden = tasks.length !== 0;
    $("#count").textContent = `${tasks.length} ${tasks.length === 1 ? "tarea" : "tareas"} en esta vista`;
    await updatePendingCounter();
  } catch (error) { if (sequence === loadSequence) showError(error); }
}

$("#task-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const title = $("#title").value.trim();
  if (!title) { showError(new Error("Escribe un título para la tarea.")); return; }
  $("#submit").disabled = true;
  try {
    await api(editing ? `/api/tasks/${editing}` : "/api/tasks", {
      method: editing ? "PATCH" : "POST",
      body: JSON.stringify({title, description: $("#description").value.trim()}),
    });
    $("#notice").textContent = editing ? "Cambios guardados." : "Tarea creada.";
    resetForm();
    await reload();
  } catch (error) { showError(error); }
  finally { $("#submit").disabled = false; }
});
$("#cancel").addEventListener("click", resetForm);
$("#refresh").addEventListener("click", reload);

document.querySelectorAll("[data-filter]").forEach((button) => button.addEventListener("click", () => {
  filter = button.dataset.filter;
  document.querySelectorAll("[data-filter]").forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
  $("#notice").textContent = "";
  reload();
}));
reload();
