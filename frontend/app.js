/* TDM — application monopage (sans framework). */
"use strict";

const app = document.getElementById("app");
const LEVELS = [
  ["debutant", "Débutant"],
  ["intermediaire", "Intermédiaire"],
  ["avance", "Avancé"],
  ["expert", "Expert"],
];
const LEVEL_LABEL = Object.fromEntries(LEVELS);
const CATEGORIES = {
  python: { title: "Python", icon: "🐍", api: "/api/python/exercises" },
  reseaux: { title: "Réseaux", icon: "🌐", api: "/api/network/exercises" },
  devops: { title: "DevOps", icon: "🚀", api: "/api/devops/labs" },
};

/* --- Utilitaires --------------------------------------------------------- */

const storage = {
  get(key, fallback) {
    try {
      const raw = localStorage.getItem("tdm." + key);
      return raw === null ? fallback : JSON.parse(raw);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem("tdm." + key, JSON.stringify(value));
    } catch {
      /* navigation privée : on continue sans mémoriser */
    }
  },
};

function clientId() {
  let id = storage.get("client", null);
  if (!id) {
    id = Math.random().toString(36).slice(2) + Date.now().toString(36);
    storage.set("client", id);
  }
  return id;
}

const progress = {
  all() { return storage.get("progress", {}); },
  isDone(cat, id) { return Boolean((this.all()[cat] || {})[id]); },
  markDone(cat, id) {
    const p = this.all();
    p[cat] = p[cat] || {};
    p[cat][id] = true;
    storage.set("progress", p);
  },
  count(cat) { return Object.keys(this.all()[cat] || {}).length; },
};

async function api(path, options = {}) {
  const init = { ...options };
  if (init.body && typeof init.body !== "string") {
    init.body = JSON.stringify(init.body);
    init.headers = { "Content-Type": "application/json" };
  }
  const res = await fetch(path, init);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Erreur ${res.status}`);
  return data;
}

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") el.className = value;
    else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (key === "html") el.innerHTML = value;
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

function markdown(text) {
  return h("div", { class: "markdown", html: DOMPurify.sanitize(marked.parse(text || "")) });
}

function levelBadge(level) {
  return h("span", { class: `badge ${level}` }, LEVEL_LABEL[level] || level);
}

function wsUrl(path) {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}${path}`;
}

function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

function renderResults(container, result) {
  container.replaceChildren();
  const ok = result.success;
  container.append(
    h("div", { class: `verdict ${ok ? "ok" : "ko"}` },
      ok ? "✓ Exercice validé !" : `✗ ${result.passed}/${result.total} test(s) réussi(s)`),
    ...result.results.map((r) =>
      h("div", { class: `result ${r.passed ? "pass" : "fail"}` },
        h("div", { class: "name" }, r.name),
        r.message ? h("div", { class: "msg" }, r.message) : null)),
  );
  if (result.output) {
    container.append(h("div", { class: "muted" }, "Affichages de ton code pendant les tests :"),
      h("pre", { class: "output" }, result.output));
  }
}

function createXterm(host) {
  const term = new Terminal({
    cursorBlink: true,
    fontFamily: '"JetBrains Mono", "Fira Code", Menlo, Consolas, monospace',
    fontSize: 14,
    theme: { background: "#0b0f14", foreground: "#e6edf3", cursor: "#22c55e" },
  });
  const fit = new FitAddon.FitAddon();
  term.loadAddon(fit);
  term.open(host);
  const observer = new ResizeObserver(() => {
    try { fit.fit(); } catch { /* terminal masqué */ }
  });
  observer.observe(host);
  return { term, fit, dispose() { observer.disconnect(); term.dispose(); } };
}

/** Relie un xterm à un WebSocket du backend. Renvoie un objet pour envoyer des fichiers et fermer. */
function connectTerminal(host, path) {
  const { term, fit, dispose } = createXterm(host);
  const socket = new WebSocket(wsUrl(path));
  const pending = [];
  const send = (msg) => {
    if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(msg));
    else if (socket.readyState === WebSocket.CONNECTING) pending.push(msg);
  };
  socket.onopen = () => {
    pending.splice(0).forEach((msg) => socket.send(JSON.stringify(msg)));
    try { fit.fit(); } catch { /* ignore */ }
    send({ type: "resize", cols: term.cols, rows: term.rows });
    term.focus();
  };
  socket.onmessage = (event) => term.write(event.data);
  socket.onclose = () => term.write("\r\n\x1b[90m[connexion fermée]\x1b[0m\r\n");
  term.onData((data) => send({ type: "input", data }));
  term.onResize(({ cols, rows }) => send({ type: "resize", cols, rows }));
  return {
    term,
    sendFile(name, content) { send({ type: "file", name, content }); },
    close() { socket.close(); dispose(); },
  };
}

/* Ressources à libérer en quittant une page (terminaux, sockets...). */
let cleanups = [];
function onLeave(fn) { cleanups.push(fn); }

/* --- Routeur ------------------------------------------------------------ */

const routes = [
  [/^\/?$/, renderHome],
  [/^\/python\/?$/, () => renderList("python")],
  [/^\/python\/(.+)$/, (id) => renderPythonExercise(id)],
  [/^\/reseaux\/?$/, () => renderList("reseaux")],
  [/^\/reseaux\/(.+)$/, (id) => renderNetworkExercise(id)],
  [/^\/devops\/?$/, () => renderList("devops")],
  [/^\/devops\/(.+)$/, (id) => renderLab(id)],
];

async function router() {
  cleanups.forEach((fn) => { try { fn(); } catch { /* ignore */ } });
  cleanups = [];
  const path = decodeURIComponent(location.hash.replace(/^#/, "")) || "/";
  const section = path.split("/")[1] || "";
  document.querySelectorAll("[data-nav]").forEach((a) => a.classList.toggle("active", a.dataset.nav === section));
  for (const [pattern, handler] of routes) {
    const match = path.match(pattern);
    if (match) {
      try {
        await handler(...match.slice(1));
      } catch (err) {
        app.replaceChildren(h("div", { class: "page" }, h("div", { class: "error-box" }, err.message)));
      }
      return;
    }
  }
  app.replaceChildren(h("div", { class: "page" }, h("h1", {}, "Page introuvable"), h("a", { href: "#/" }, "Retour à l'accueil")));
}

window.addEventListener("hashchange", router);

/* --- Accueil ------------------------------------------------------------ */

async function renderHome() {
  document.title = "TDM · Entraînement";
  const data = await api("/api/categories");
  app.replaceChildren(h("div", { class: "page" },
    h("section", { class: "hero" },
      h("h1", {}, "Entraîne-toi, pour de vrai."),
      h("p", {}, "Choisis une catégorie, ouvre un exercice, code dans le navigateur et laisse la moulinette valider ton travail.")),
    h("div", { class: "cards" }, data.categories.map((cat) => {
      const done = progress.count(cat.id);
      const pct = cat.count ? Math.round((done / cat.count) * 100) : 0;
      return h("a", { class: "card", href: `#/${cat.id}` },
        h("div", { class: "icon" }, CATEGORIES[cat.id].icon),
        h("h2", {}, cat.title),
        h("p", {}, cat.description),
        h("div", { class: "progress" }, h("span", { style: `width:${pct}%` })),
        h("div", { class: "progress-label" },
          cat.id === "devops" ? `${cat.count} lab(s) disponibles` : `${done} / ${cat.count} exercices validés`));
    }))));
}

/* --- Liste d'exercices -------------------------------------------------- */

async function renderList(cat) {
  const meta = CATEGORIES[cat];
  document.title = `TDM · ${meta.title}`;
  const items = await api(meta.api);
  const search = h("input", { class: "search", type: "search", placeholder: "Filtrer (titre, notion…)" });
  const body = h("div");

  const draw = () => {
    const q = search.value.trim().toLowerCase();
    body.replaceChildren();
    for (const [level, label] of LEVELS) {
      const group = items.filter((it) => it.level === level).filter((it) =>
        !q || [it.title, it.summary, ...(it.tags || [])].join(" ").toLowerCase().includes(q));
      if (!group.length) continue;
      body.append(h("section", { class: "level-section" },
        h("h2", {}, `${label} · ${group.length}`),
        h("div", { class: "ex-list" }, group.map((it) => {
          const done = cat === "devops" ? labDoneCount(it) === it.exercise_count && it.exercise_count > 0 : progress.isDone(cat, it.id);
          return h("a", { class: `ex-item ${done ? "done" : ""}`, href: `#/${cat}/${it.id}` },
            h("span", { class: "check" }, done ? "✓" : ""),
            h("div", {},
              h("div", { class: "title" }, it.title),
              it.summary ? h("div", { class: "summary" }, it.summary) : null,
              cat === "devops" ? h("div", { class: "summary" }, `${labDoneCount(it)} / ${it.exercise_count} exercice(s)`) : null,
              h("div", { class: "tags" }, (it.tags || []).map((t) => h("span", { class: "tag" }, t)))));
        }))));
    }
    if (!body.children.length) body.append(h("p", { class: "muted" }, "Aucun résultat."));
  };
  search.addEventListener("input", draw);
  draw();

  const doneCount = cat === "devops" ? null : items.filter((it) => progress.isDone(cat, it.id)).length;
  app.replaceChildren(h("div", { class: "page" },
    h("div", { class: "list-head" },
      h("h1", {}, `${meta.icon} ${meta.title}`),
      doneCount !== null ? h("span", { class: "badge ok" }, `${doneCount} / ${items.length} validés`) : null,
      search),
    cat === "reseaux" ? h("p", { class: "muted" },
      "Les exercices se font dans un terminal Cisco IOS simulé (switch 2960 / routeur ISR) : mêmes modes, mêmes commandes, abréviations comprises.") : null,
    cat === "devops" ? h("p", { class: "muted" },
      "Chaque lab démarre un environnement isolé dans Docker en un clic, avec un terminal intégré et des exercices vérifiés automatiquement.") : null,
    body));
}

function labDoneCount(lab) {
  return Object.keys(storage.get(`lab.${lab.id}`, {})).length;
}

function neighbours(items, id) {
  const index = items.findIndex((it) => it.id === id);
  return { prev: items[index - 1], next: items[index + 1] };
}

function exerciseHeader(cat, exercise) {
  return [
    h("div", { class: "crumbs" }, h("a", { href: `#/${cat}` }, `← ${CATEGORIES[cat].title}`)),
    h("h1", { class: "ex-title" }, exercise.title),
    h("div", { class: "ex-meta" }, levelBadge(exercise.level),
      ...(exercise.tags || []).map((t) => h("span", { class: "tag" }, t))),
  ];
}

function exerciseNav(cat, items, id) {
  const { prev, next } = neighbours(items, id);
  return h("div", { class: "ex-nav" },
    prev ? h("a", { class: "btn small", href: `#/${cat}/${prev.id}` }, `← ${prev.title}`) : h("span"),
    next ? h("a", { class: "btn small", href: `#/${cat}/${next.id}` }, `${next.title} →`) : h("span"));
}

/* --- Exercice Python ---------------------------------------------------- */

async function renderPythonExercise(id) {
  const [exercise, items] = await Promise.all([
    api(`/api/python/exercises/${encodeURIComponent(id)}`),
    api("/api/python/exercises"),
  ]);
  document.title = `TDM · ${exercise.title}`;
  const codeKey = `code.python.${id}`;
  const isStdio = exercise.mode === "stdio";

  const doneBadge = h("span", { class: "badge ok" }, "✓ Validé");
  const meta = exerciseHeader("python", exercise);
  if (!progress.isDone("python", id)) doneBadge.style.display = "none";
  meta[2].append(doneBadge);

  const editorHost = h("div", { class: "editor-wrap" });
  const runBtn = h("button", { class: "btn", title: "Exécuter (Ctrl+Entrée)" }, "▶ Exécuter");
  const submitBtn = h("button", { class: "btn primary", title: "Lancer la moulinette (Ctrl+Maj+Entrée)" }, "✔ Valider");
  const resetBtn = h("button", { class: "btn small danger" }, "Réinitialiser");

  const outputPane = h("pre", { class: "output muted" }, "Clique sur « Exécuter » pour lancer ton code, ou sur « Valider » pour la moulinette.");
  const resultsPane = h("div", { class: "results" }, h("p", { class: "muted" }, "Pas encore de correction."));
  const termPane = h("div", { class: "tab-body term" });
  const stdin = h("textarea", { rows: 2, placeholder: "Texte envoyé à input() (une valeur par ligne)" });
  const panes = {
    output: h("div", { class: "tab-body" }, isStdio ? h("div", { class: "stdin-box" }, h("span", { class: "muted" }, "Entrée standard"), stdin) : null, outputPane),
    results: h("div", { class: "tab-body" }, resultsPane),
    terminal: termPane,
  };
  const tabButtons = {};
  const tabs = h("div", { class: "tabs" });
  let terminal = null;

  const showTab = (name) => {
    for (const [key, pane] of Object.entries(panes)) {
      pane.style.display = key === name ? "" : "none";
      tabButtons[key].classList.toggle("active", key === name);
    }
    if (name === "terminal" && !terminal) {
      terminal = connectTerminal(termPane, `/ws/python/${encodeURIComponent(id)}?client=${clientId()}`);
      terminal.sendFile("solution.py", editor.getValue());
      onLeave(() => terminal.close());
      terminal.term.writeln("\x1b[90mTon code est synchronisé dans solution.py. Essaie : python3 solution.py\x1b[0m");
    }
  };
  for (const [key, label] of [["output", "Sortie"], ["results", "Moulinette"], ["terminal", "Terminal"]]) {
    tabButtons[key] = h("button", { onclick: () => showTab(key) }, label);
    tabs.append(tabButtons[key]);
  }

  app.replaceChildren(h("div", { class: "workspace" },
    h("section", { class: "left" }, ...meta, markdown(exercise.description), exerciseNav("python", items, id)),
    h("section", { class: "right" },
      h("div", { class: "toolbar" }, runBtn, submitBtn, h("span", { class: "spacer" }),
        h("span", { class: "hint" }, isStdio ? "Programme lu sur l'entrée standard" : "Fonctions testées par la moulinette"), resetBtn),
      editorHost,
      h("div", { class: "bottom" }, tabs, panes.output, panes.results, panes.terminal))));
  showTab("output");

  const editor = CodeMirror(editorHost, {
    value: storage.get(codeKey, null) ?? exercise.starter,
    mode: "python",
    lineNumbers: true,
    indentUnit: 4,
    tabSize: 4,
    matchBrackets: true,
    autoCloseBrackets: true,
    extraKeys: {
      Tab: (cm) => (cm.somethingSelected() ? cm.indentSelection("add") : cm.replaceSelection("    ", "end")),
      "Shift-Tab": (cm) => cm.indentSelection("subtract"),
      "Ctrl-Enter": () => run(),
      "Cmd-Enter": () => run(),
      "Shift-Ctrl-Enter": () => submit(),
      "Shift-Cmd-Enter": () => submit(),
      "Ctrl-S": () => sync(), "Cmd-S": () => sync(),
    },
  });
  editor.focus();
  const sync = () => {
    storage.set(codeKey, editor.getValue());
    if (terminal) terminal.sendFile("solution.py", editor.getValue());
  };
  editor.on("change", debounce(sync, 400));

  const busy = (btn, on, label) => {
    btn.disabled = on;
    btn.replaceChildren(...(on ? [h("span", { class: "spinner" }), " En cours…"] : [label]));
  };

  async function run() {
    showTab("output");
    busy(runBtn, true);
    try {
      const res = await api(`/api/python/exercises/${encodeURIComponent(id)}/run`, {
        method: "POST", body: { code: editor.getValue(), stdin: stdin.value },
      });
      outputPane.className = "output";
      outputPane.replaceChildren(
        res.stdout || "",
        res.stderr ? h("span", { class: "err" }, res.stderr) : "",
        res.timed_out ? h("span", { class: "err" }, "\n⏱ Temps dépassé.") : "",
        !res.stdout && !res.stderr && !res.timed_out ? h("span", { class: "muted" }, "(aucun affichage)") : "",
      );
    } catch (err) {
      outputPane.replaceChildren(h("span", { class: "err" }, err.message));
    } finally {
      busy(runBtn, false, "▶ Exécuter");
    }
  }

  async function submit() {
    showTab("results");
    busy(submitBtn, true);
    try {
      const res = await api(`/api/python/exercises/${encodeURIComponent(id)}/submit`, {
        method: "POST", body: { code: editor.getValue() },
      });
      renderResults(resultsPane, res);
      if (res.success) {
        progress.markDone("python", id);
        doneBadge.style.display = "";
      }
    } catch (err) {
      resultsPane.replaceChildren(h("div", { class: "error-box" }, err.message));
    } finally {
      busy(submitBtn, false, "✔ Valider");
    }
  }

  runBtn.addEventListener("click", run);
  submitBtn.addEventListener("click", submit);
  resetBtn.addEventListener("click", () => {
    if (editor.getValue() === exercise.starter) return;
    editor.setValue(exercise.starter);
    sync();
  });
}

/* --- Exercice réseau ---------------------------------------------------- */

async function renderNetworkExercise(id) {
  const [exercise, items] = await Promise.all([
    api(`/api/network/exercises/${encodeURIComponent(id)}`),
    api("/api/network/exercises"),
  ]);
  document.title = `TDM · ${exercise.title}`;
  const meta = exerciseHeader("reseaux", exercise);
  const doneBadge = h("span", { class: "badge ok" }, "✓ Validé");
  if (!progress.isDone("reseaux", id)) doneBadge.style.display = "none";
  meta[2].append(h("span", { class: "badge" }, exercise.device === "router" ? "Routeur" : "Switch"), doneBadge);

  const checklist = h("ul", { class: "checklist" }, exercise.checks.map((c) => h("li", {}, c)));
  const verdict = h("div");
  const checkBtn = h("button", { class: "btn primary" }, "✔ Vérifier ma configuration");
  const resetBtn = h("button", { class: "btn small danger" }, "Repartir de zéro");
  const cli = h("div", { class: "cli" });
  const scroll = h("pre");
  const promptEl = h("span", { class: "prompt" });
  const input = h("input", { autocomplete: "off", spellcheck: "false", autocapitalize: "off" });
  cli.append(scroll, h("div", { class: "line" }, promptEl, input));
  cli.addEventListener("click", () => { if (!getSelection().toString()) input.focus(); });

  app.replaceChildren(h("div", { class: "workspace" },
    h("section", { class: "left" }, ...meta, markdown(exercise.description),
      h("h3", {}, "Ce que la moulinette vérifie"), checklist, verdict,
      exerciseNav("reseaux", items, id)),
    h("section", { class: "right" },
      h("div", { class: "toolbar" }, checkBtn, h("span", { class: "spacer" }),
        h("span", { class: "hint" }, "↑/↓ historique · ? aide · Tab complète avec ?"), resetBtn),
      cli)));

  let sessionId = null;
  const history = [];
  let historyIndex = 0;
  const print = (text) => {
    scroll.append(text.endsWith("\n") || !text ? text : text + "\n");
    cli.scrollTop = cli.scrollHeight;
  };

  async function startSession() {
    const res = await api(`/api/network/exercises/${encodeURIComponent(id)}/session`, { method: "POST" });
    sessionId = res.session_id;
    scroll.replaceChildren();
    print(res.banner + "\n");
    promptEl.textContent = res.prompt;
    checklist.querySelectorAll("li").forEach((li) => { li.className = ""; li.querySelector(".msg")?.remove(); });
    verdict.replaceChildren();
    input.focus();
  }

  async function send(line) {
    print(promptEl.textContent + line);
    try {
      const res = await api(`/api/network/sessions/${sessionId}/command`, { method: "POST", body: { line } });
      if (res.output) print(res.output);
      promptEl.textContent = res.prompt;
    } catch (err) {
      print("% " + err.message);
    }
  }

  input.addEventListener("keydown", async (event) => {
    if (event.key === "Enter") {
      const line = input.value;
      input.value = "";
      if (line.trim()) { history.push(line); }
      historyIndex = history.length;
      await send(line);
      if (line.trim().endsWith("?")) {
        input.value = line.trim().slice(0, -1);
      }
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (historyIndex > 0) input.value = history[--historyIndex];
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      historyIndex = Math.min(history.length, historyIndex + 1);
      input.value = history[historyIndex] || "";
    } else if (event.key === "Tab") {
      event.preventDefault();
      const line = input.value;
      const res = await api(`/api/network/sessions/${sessionId}/command`, { method: "POST", body: { line: line + "?" } });
      const words = res.output.split("\n").map((l) => l.trim().split(/\s+/)[0]).filter((w) => w && !w.startsWith("%") && !w.startsWith("<"));
      if (words.length === 1) {
        const parts = line.split(" ");
        parts[parts.length - 1] = words[0];
        input.value = parts.join(" ") + " ";
      } else if (words.length > 1) {
        print(promptEl.textContent + line + "\n" + res.output);
      }
    } else if (event.key === "c" && event.ctrlKey && !getSelection().toString()) {
      print(promptEl.textContent + input.value + "^C");
      input.value = "";
    } else if (event.key === "z" && event.ctrlKey) {
      event.preventDefault();
      await send("end");
    }
  });

  checkBtn.addEventListener("click", async () => {
    checkBtn.disabled = true;
    try {
      const res = await api(`/api/network/sessions/${sessionId}/check`, { method: "POST" });
      checklist.querySelectorAll("li").forEach((li, i) => {
        const r = res.results[i];
        li.className = r.passed ? "pass" : "fail";
        li.querySelector(".msg")?.remove();
        if (r.message) li.append(h("span", { class: "msg" }, "Indice : " + r.message));
      });
      verdict.replaceChildren(h("p", { class: `verdict ${res.success ? "ok" : "ko"}` },
        res.success ? "✓ Configuration validée !" : `✗ ${res.passed}/${res.total} vérification(s) réussie(s)`));
      if (res.success) {
        progress.markDone("reseaux", id);
        doneBadge.style.display = "";
      }
    } catch (err) {
      verdict.replaceChildren(h("div", { class: "error-box" }, err.message));
    } finally {
      checkBtn.disabled = false;
      input.focus();
    }
  });
  resetBtn.addEventListener("click", startSession);
  await startSession();
}

/* --- Lab DevOps --------------------------------------------------------- */

async function renderLab(id) {
  const [lab, items] = await Promise.all([
    api(`/api/devops/labs/${encodeURIComponent(id)}`),
    api("/api/devops/labs"),
  ]);
  document.title = `TDM · ${lab.title}`;
  const doneKey = `lab.${id}`;
  const done = storage.get(doneKey, {});

  const statusDot = h("span", { class: "status-dot" });
  const statusText = h("span", { class: "muted" });
  const startBtn = h("button", { class: "btn primary" }, "▶ Démarrer le lab");
  const stopBtn = h("button", { class: "btn danger" }, "■ Arrêter");
  const resetBtn = h("button", { class: "btn small" }, "↺ Réinitialiser");
  const errorBox = h("div");
  const termArea = h("div", { class: "xterm-host" });
  const placeholder = h("div", { class: "term-placeholder" }, "Démarre le lab pour ouvrir le terminal.");
  const right = h("section", { class: "right" },
    h("div", { class: "toolbar" }, h("strong", {}, "Terminal du lab"), h("span", { class: "spacer" }),
      lab.ports.length ? h("span", { class: "hint" }, "Ports publiés : " + lab.ports.join(", ")) : null),
    placeholder);
  let terminal = null;

  const exerciseCards = lab.exercises.map((ex) => {
    const result = h("div", { class: "results" });
    result.style.padding = "8px 0 0";
    const card = h("article", { class: `lab-ex ${done[ex.id] ? "done" : ""}` });
    const btn = h("button", { class: "btn small" }, "Vérifier");
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      btn.replaceChildren(h("span", { class: "spinner" }));
      try {
        const res = await api(`/api/devops/labs/${encodeURIComponent(id)}/exercises/${encodeURIComponent(ex.id)}/check`, { method: "POST" });
        renderResults(result, res);
        if (res.success) {
          done[ex.id] = true;
          storage.set(doneKey, done);
          card.classList.add("done");
        }
      } catch (err) {
        result.replaceChildren(h("div", { class: "error-box" }, err.message));
      } finally {
        btn.disabled = false;
        btn.replaceChildren("Vérifier");
      }
    });
    card.append(h("header", {}, h("h3", {}, ex.title), btn), markdown(ex.description || ""), result);
    return card;
  });

  app.replaceChildren(h("div", { class: "workspace" },
    h("section", { class: "left" }, ...exerciseHeader("devops", lab), markdown(lab.description),
      h("div", { class: "lab-controls" }, statusDot, statusText, startBtn, stopBtn, resetBtn), errorBox,
      h("h3", {}, `Exercices (${lab.exercises.length})`), ...exerciseCards,
      exerciseNav("devops", items, id)),
    right));

  const openTerminal = () => {
    if (terminal) return;
    placeholder.remove();
    right.append(termArea);
    terminal = connectTerminal(termArea, `/ws/devops/${encodeURIComponent(id)}`);
  };
  const closeTerminal = () => {
    if (!terminal) return;
    terminal.close();
    terminal = null;
    termArea.remove();
    termArea.replaceChildren();
    right.append(placeholder);
  };
  onLeave(closeTerminal);

  const setStatus = (status) => {
    statusDot.className = `status-dot ${status}`;
    statusText.textContent = { running: "En cours d'exécution", stopped: "Arrêté", unavailable: "Docker indisponible" }[status] || status;
    startBtn.style.display = status === "running" ? "none" : "";
    stopBtn.style.display = resetBtn.style.display = status === "running" ? "" : "none";
    startBtn.disabled = status === "unavailable";
    if (status === "running") openTerminal(); else closeTerminal();
  };

  const action = async (name, btn, label) => {
    errorBox.replaceChildren();
    btn.disabled = true;
    btn.replaceChildren(h("span", { class: "spinner" }), name === "stop" ? " Arrêt…" : " Démarrage (construction de l'image au premier lancement)…");
    try {
      closeTerminal();
      const res = await api(`/api/devops/labs/${encodeURIComponent(id)}/${name}`, { method: "POST" });
      setStatus(res.status);
    } catch (err) {
      errorBox.replaceChildren(h("div", { class: "error-box" }, err.message));
    } finally {
      btn.disabled = false;
      btn.replaceChildren(label);
    }
  };
  startBtn.addEventListener("click", () => action("start", startBtn, "▶ Démarrer le lab"));
  stopBtn.addEventListener("click", () => action("stop", stopBtn, "■ Arrêter"));
  resetBtn.addEventListener("click", () => action("reset", resetBtn, "↺ Réinitialiser"));
  setStatus(lab.status);
  if (lab.status === "unavailable") {
    errorBox.append(h("div", { class: "error-box" }, "Docker n'est pas disponible : installe-le et lance-le pour utiliser les labs DevOps."));
  }
}

/* --- Démarrage ---------------------------------------------------------- */

api("/api/health").then((health) => {
  const badge = document.getElementById("sandbox-badge");
  badge.textContent = health.sandbox === "docker" ? "🐳 Bac à sable Docker" : "⚠ Exécution locale";
  badge.className = `badge ${health.sandbox === "docker" ? "ok" : "warn"}`;
  badge.title = health.sandbox === "docker"
    ? "Le code est exécuté dans des conteneurs isolés."
    : "Le code est exécuté directement sur cette machine (usage personnel uniquement).";
}).catch(() => {});

router();
