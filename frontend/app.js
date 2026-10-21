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
  systemes: { title: "Systèmes & réseaux", icon: "🖧", api: "/api/devops/labs?category=systemes", labs: true },
  devops: { title: "DevOps", icon: "🚀", api: "/api/devops/labs?category=devops", labs: true },
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

/* Profil actif : sa progression et son XP sont enregistrées par le serveur. */
const profile = {
  id: storage.get("profile", null),
  data: null,
  async load() {
    this.data = null;
    if (this.id) {
      try {
        this.data = await api(`/api/profiles/${this.id}`);
      } catch {
        this.select(null);
      }
    }
    renderProfileChip();
  },
  select(id) {
    this.id = id;
    storage.set("profile", id);
  },
  isGod() { return Boolean(this.data && this.data.title.god); },
};

const progress = {
  items(cat) { return (profile.data && profile.data.completed_items[cat]) || []; },
  isDone(cat, id) { return this.items(cat).includes(id); },
  markDone(cat, id) {
    if (!profile.data) return;
    const list = (profile.data.completed_items[cat] = this.items(cat));
    if (!list.includes(id)) list.push(id);
  },
  count(cat) { return this.items(cat).length; },
};

async function api(path, options = {}) {
  const init = { ...options, headers: { ...(options.headers || {}) } };
  if (profile.id) init.headers["X-TDM-Profile"] = String(profile.id);
  if (init.body && typeof init.body !== "string") {
    init.body = JSON.stringify(init.body);
    init.headers["Content-Type"] = "application/json";
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

DOMPurify.addHook("afterSanitizeAttributes", (node) => {
  if (node.tagName === "A" && /^https?:/.test(node.getAttribute("href") || "")) {
    node.setAttribute("target", "_blank");
    node.setAttribute("rel", "noopener");
  }
});

function markdown(text) {
  return h("div", { class: "markdown", html: DOMPurify.sanitize(marked.parse(text || "")) });
}

function docLinks(docs) {
  if (!docs || !docs.length) return null;
  return h("div", { class: "doc-links" }, h("h4", {}, "Pour aller plus loin"),
    h("ul", {}, docs.map((d) => h("li", {}, h("a", { href: d.url, target: "_blank", rel: "noopener" }, d.title || d.url)))));
}

/* Énoncé et cours dans deux onglets ; sans cours, l'énoncé seul. */
function withCours(enonce, cours, docs) {
  if (!cours && !(docs && docs.length)) return h("div", {}, ...enonce);
  const panes = { enonce: h("div", {}, ...enonce), cours: h("div", { class: "cours" }, markdown(cours), docLinks(docs)) };
  const buttons = {};
  const show = (name) => {
    for (const [key, pane] of Object.entries(panes)) {
      pane.style.display = key === name ? "" : "none";
      buttons[key].classList.toggle("active", key === name);
    }
  };
  buttons.enonce = h("button", { onclick: () => show("enonce") }, "Énoncé");
  buttons.cours = h("button", { onclick: () => show("cours") }, "📖 Cours");
  const node = h("div", {}, h("div", { class: "tabs doc-tabs" }, buttons.enonce, buttons.cours), panes.enonce, panes.cours);
  show("enonce");
  return node;
}

function coursDetails(item) {
  if (!item.cours && !(item.docs && item.docs.length)) return null;
  return h("details", { class: "cours" }, h("summary", {}, "📖 Cours"), markdown(item.cours || ""), docLinks(item.docs));
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
    theme: { background: "#000000", foreground: "#c8ffd8", cursor: "#00ff66", selectionBackground: "#0f4d26",
             green: "#00ff66", brightGreen: "#5bff9b" },
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
  [/^\/profils\/?$/, renderProfilePicker],
  [/^\/profil\/?$/, renderProfile],
  [/^\/classement\/?$/, renderLeaderboard],
  [/^\/python\/?$/, () => renderList("python")],
  [/^\/python\/(.+)$/, (id) => renderPythonExercise(id)],
  [/^\/reseaux\/?$/, () => renderList("reseaux")],
  [/^\/reseaux\/(.+)$/, (id) => renderNetworkExercise(id)],
  [/^\/systemes\/?$/, () => renderList("systemes")],
  [/^\/systemes\/(.+)$/, (id) => renderLab(id, "systemes")],
  [/^\/devops\/?$/, () => renderList("devops")],
  [/^\/devops\/(.+)$/, (id) => renderLab(id, "devops")],
];

async function router() {
  cleanups.forEach((fn) => { try { fn(); } catch { /* ignore */ } });
  cleanups = [];
  const path = decodeURIComponent(location.hash.replace(/^#/, "")) || "/";
  if (!profile.data && path !== "/profils") {
    location.hash = "#/profils";
    return;
  }
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

/** Pluie de caractères verte en fond d'accueil (arrêtée en quittant la page). */
function matrixRain() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const canvas = h("canvas", { id: "matrix" });
  document.body.append(canvas);
  const ctx = canvas.getContext("2d");
  const chars = "アカサタナハマヤラワ0123456789ABCDEF<>/{}$#@%";
  let columns = [];
  const size = 16;
  const resize = () => {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    columns = Array.from({ length: Math.ceil(canvas.width / size) }, () => Math.random() * -50);
  };
  resize();
  window.addEventListener("resize", resize);
  const timer = setInterval(() => {
    ctx.fillStyle = "rgba(3, 6, 4, 0.12)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#00ff66";
    ctx.font = `${size}px monospace`;
    columns.forEach((y, i) => {
      ctx.fillText(chars[Math.floor(Math.random() * chars.length)], i * size, y * size);
      columns[i] = y * size > canvas.height && Math.random() > 0.975 ? 0 : y + 1;
    });
  }, 60);
  onLeave(() => {
    clearInterval(timer);
    window.removeEventListener("resize", resize);
    canvas.remove();
  });
}

async function renderHome() {
  document.title = "TDM · Entraînement";
  matrixRain();
  const data = await api("/api/categories");
  app.replaceChildren(h("div", { class: "page" },
    h("section", { class: "hero" },
      h("h1", {}, h("span", { class: "glitch", "data-text": "Entraîne-toi, pour de vrai." }, "Entraîne-toi, pour de vrai."),
        h("span", { class: "cursor" })),
      h("p", {}, "Choisis une catégorie, ouvre un exercice, code dans le navigateur et laisse la moulinette valider ton travail.")),
    h("div", { class: "cards" }, data.categories.map((cat) => {
      const done = progress.count(cat.id);
      const isLabs = CATEGORIES[cat.id].labs;
      const total = isLabs ? (profile.data.categories[cat.id] || {}).total || 0 : cat.count;
      const pct = total ? Math.round((done / total) * 100) : 0;
      return h("a", { class: "card", href: `#/${cat.id}` },
        h("div", { class: "icon" }, CATEGORIES[cat.id].icon),
        h("h2", {}, cat.title),
        h("p", {}, cat.description),
        h("div", { class: "progress" }, h("span", { style: `width:${pct}%` })),
        h("div", { class: "progress-label" },
          isLabs ? `${cat.count} labs · ${done} / ${total} exercices validés` : `${done} / ${cat.count} exercices validés`));
    }))));
}

/* --- Liste d'exercices -------------------------------------------------- */

async function renderList(cat) {
  const meta = CATEGORIES[cat];
  document.title = `TDM · ${meta.title}`;
  const allItems = await api(meta.api);
  const osList = [["windows", "🪟 Windows"], ["linux", "🐧 Linux"]];
  const hasOs = cat === "systemes";
  let os = storage.get(`${cat}.os`, "windows");
  let items = hasOs ? allItems.filter((it) => (it.os || "linux") === os) : allItems;
  const osButtons = hasOs ? osList.map(([key, label]) => h("button", {
    class: `os-btn ${key === os ? "active" : ""}`,
    onclick: () => { storage.set(`${cat}.os`, key); router(); },
  }, label, h("span", { class: "os-count" }, String(allItems.filter((it) => (it.os || "linux") === key).length)))) : [];
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
          const done = meta.labs ? labDoneCount(cat, it) === it.exercise_count && it.exercise_count > 0 : progress.isDone(cat, it.id);
          return h("a", { class: `ex-item ${done ? "done" : ""}`, href: `#/${cat}/${it.id}` },
            h("span", { class: "check" }, done ? "✓" : ""),
            h("div", {},
              h("div", { class: "title" }, it.title),
              it.summary ? h("div", { class: "summary" }, it.summary) : null,
              meta.labs ? h("div", { class: "summary" },
                `${it.kind === "vagrant" ? (it.os === "windows" ? "🪟 VM Windows" : "🖥 VM Vagrant") : "🐳 Docker"} · ${labDoneCount(cat, it)} / ${it.exercise_count} exercice(s)`) : null,
              h("div", { class: "tags" }, (it.tags || []).map((t) => h("span", { class: "tag" }, t)))));
        }))));
    }
    if (!body.children.length) body.append(h("p", { class: "muted" }, q ? "Aucun résultat." : "Aucun lab pour ce système pour l'instant."));
  };
  search.addEventListener("input", draw);
  draw();

  const doneCount = meta.labs ? null : items.filter((it) => progress.isDone(cat, it.id)).length;
  app.replaceChildren(h("div", { class: "page" },
    h("div", { class: "list-head" },
      h("h1", {}, `${meta.icon} ${meta.title}`),
      doneCount !== null ? h("span", { class: "badge ok" }, `${doneCount} / ${items.length} validés`) : null,
      search),
    hasOs ? h("div", { class: "os-switch" }, h("span", { class: "muted" }, "Système :"), ...osButtons) : null,
    cat === "reseaux" ? h("p", { class: "muted" },
      "Les exercices se font dans un terminal Cisco IOS simulé (switch 2960 / routeur ISR) : mêmes modes, mêmes commandes, abréviations comprises.") : null,
    meta.labs ? h("p", { class: "muted" }, hasOs && os === "windows"
      ? "Chaque lab démarre de vraies machines virtuelles Windows Server et Windows 11 (Vagrant + VirtualBox) en un clic, avec un terminal PowerShell intégré et des exercices vérifiés automatiquement."
      : "Chaque lab démarre un environnement isolé dans Docker en un clic, avec un terminal intégré et des exercices vérifiés automatiquement.") : null,
    body));
}

function labDoneCount(cat, lab) {
  return progress.items(cat).filter((item) => item.startsWith(lab.id + "/")).length;
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
  const resetBtn = h("button", { class: "btn small danger" }, "Effacer");
  // L'éditeur démarre vide : le squelette (signatures attendues) n'est inséré qu'à la demande.
  const blank = "# Écris ton code ici\n";
  const hasSkeleton = exercise.starter.trim() && exercise.starter.trim() !== blank.trim();
  const skeletonBtn = hasSkeleton ? h("button", { class: "btn small", title: "Insérer les signatures attendues par la moulinette" }, "Squelette") : null;

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
    h("section", { class: "left" }, ...meta, withCours([markdown(exercise.description)], exercise.cours, exercise.docs),
      exerciseNav("python", items, id)),
    h("section", { class: "right" },
      h("div", { class: "toolbar" }, runBtn, submitBtn, h("span", { class: "spacer" }),
        h("span", { class: "hint" }, isStdio ? "Programme lu sur l'entrée standard" : "Fonctions testées par la moulinette"), skeletonBtn, resetBtn),
      editorHost,
      h("div", { class: "bottom" }, tabs, panes.output, panes.results, panes.terminal))));
  showTab("output");

  const editor = CodeMirror(editorHost, {
    value: storage.get(codeKey, null) ?? blank,
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
        celebrate(res.reward);
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
    editor.setValue(blank);
    sync();
  });
  skeletonBtn?.addEventListener("click", () => {
    const current = editor.getValue().trim();
    if (!current || current === blank.trim()) editor.setValue(exercise.starter);
    else editor.replaceSelection(exercise.starter);
    sync();
    editor.focus();
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
    h("section", { class: "left" }, ...meta,
      withCours([markdown(exercise.description), h("h3", {}, "Ce que la moulinette vérifie"), checklist],
        exercise.cours, exercise.docs), verdict,
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
        celebrate(res.reward);
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

async function renderLab(id, cat = "devops") {
  const [lab, items] = await Promise.all([
    api(`/api/devops/labs/${encodeURIComponent(id)}`),
    api(CATEGORIES[cat].api),
  ]);
  document.title = `TDM · ${lab.title}`;

  const statusDot = h("span", { class: "status-dot" });
  const statusText = h("span", { class: "muted" });
  const startBtn = h("button", { class: "btn primary" }, "▶ Démarrer le lab");
  // VM Windows : « Arrêter » met en pause (reprise en quelques secondes), voir scripts/vagrant_agent.py.
  const stopLabel = lab.kind === "vagrant" && lab.os === "windows" ? "⏸ Mettre en pause" : "■ Arrêter";
  const stopBtn = h("button", { class: "btn danger" }, stopLabel);
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
    const card = h("article", { class: `lab-ex ${progress.isDone(cat, `${id}/${ex.id}`) ? "done" : ""}` });
    const btn = h("button", { class: "btn small" }, "Vérifier");
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      btn.replaceChildren(h("span", { class: "spinner" }));
      try {
        const res = await api(`/api/devops/labs/${encodeURIComponent(id)}/exercises/${encodeURIComponent(ex.id)}/check`, { method: "POST" });
        renderResults(result, res);
        if (res.success) {
          progress.markDone(cat, `${id}/${ex.id}`);
          card.classList.add("done");
          celebrate(res.reward);
        }
      } catch (err) {
        result.replaceChildren(h("div", { class: "error-box" }, err.message));
      } finally {
        btn.disabled = false;
        btn.replaceChildren("Vérifier");
      }
    });
    card.append(h("header", {}, h("h3", {}, ex.title), btn), markdown(ex.description || ""), coursDetails(ex), result);
    return card;
  });

  app.replaceChildren(h("div", { class: "workspace" },
    h("section", { class: "left" }, ...exerciseHeader(cat, lab),
      lab.kind === "vagrant" ? h("p", {}, h("span", { class: "badge warn" },
        lab.os === "windows" ? "🪟 Machine virtuelle Windows (Vagrant)" : "🖥 Machine virtuelle Vagrant")) : null,
      withCours([markdown(lab.description)], lab.cours, lab.docs),
      h("div", { class: "lab-controls" }, statusDot, statusText, startBtn, stopBtn, resetBtn), errorBox,
      h("h3", {}, `Exercices (${lab.exercises.length})`), ...exerciseCards,
      exerciseNav(cat, items, id)),
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

  const isVm = lab.kind === "vagrant";
  const logBox = h("pre", { class: "output lab-log" });
  logBox.style.display = "none";
  errorBox.after(logBox);
  let pollTimer = null;
  onLeave(() => clearTimeout(pollTimer));

  const STATUS_LABELS = {
    running: "En cours d'exécution",
    stopped: "Arrêté",
    starting: !isVm ? "Démarrage…" : lab.os === "windows"
      ? "Démarrage des VM : le tout premier lancement télécharge la box Windows (plusieurs Go) et prépare Windows, comptez de 20 à 60 minutes ; ensuite, la reprise après une pause ne prend que quelques secondes…"
      : "Démarrage de la VM (plusieurs minutes au premier lancement)…",
    stopping: "Arrêt en cours…",
    error: "Échec du dernier lancement (voir le journal)",
    unavailable: isVm ? "Agent Vagrant injoignable" : "Docker indisponible",
  };
  const setStatus = (status, log = "") => {
    const busy = status === "starting" || status === "stopping";
    statusDot.className = `status-dot ${status}`;
    statusText.textContent = STATUS_LABELS[status] || status;
    startBtn.style.display = status === "running" || busy ? "none" : "";
    stopBtn.style.display = resetBtn.style.display = status === "running" ? "" : "none";
    startBtn.disabled = status === "unavailable";
    logBox.style.display = log && (busy || status === "error") ? "" : "none";
    logBox.textContent = log;
    if (status === "running") openTerminal(); else closeTerminal();
    clearTimeout(pollTimer);
    if (busy) {
      pollTimer = setTimeout(async () => {
        try {
          const fresh = await api(`/api/devops/labs/${encodeURIComponent(id)}`);
          setStatus(fresh.status, fresh.log);
        } catch { setStatus(status, log); }
      }, 4000);
    }
  };

  const action = async (name, btn, label) => {
    errorBox.replaceChildren();
    btn.disabled = true;
    const waiting = name === "stop" ? " Arrêt…" : isVm ? " Envoi à Vagrant…" : " Démarrage (construction de l'image au premier lancement)…";
    btn.replaceChildren(h("span", { class: "spinner" }), waiting);
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
  stopBtn.addEventListener("click", () => action("stop", stopBtn, stopLabel));
  resetBtn.addEventListener("click", () => action("reset", resetBtn, "↺ Réinitialiser"));
  setStatus(lab.status, lab.log);
  if (lab.status === "unavailable") {
    errorBox.append(h("div", { class: "error-box" }, isVm
      ? "Ce lab tourne dans une machine virtuelle : lance l'agent Vagrant sur ta machine (start.bat le démarre automatiquement si Vagrant est installé)."
      : "Docker n'est pas disponible : installe-le et lance-le pour utiliser les labs DevOps."));
  }
}

/* --- Profils, XP et classement ----------------------------------------- */

const CATEGORY_KEYS = ["python", "reseaux", "systemes", "devops"];

function avatar(p, size = "") {
  return h("span", { class: `avatar ${size} ${p.title.god ? "god" : ""}` }, p.name.slice(0, 1).toUpperCase());
}

function titleBadge(title) {
  return h("span", { class: `title-badge ${title.god ? "god" : ""}`, title: title.description }, title.name);
}

function xpBar(p) {
  const span = Math.max(1, p.next_level_xp - p.level_xp);
  const pct = Math.min(100, Math.round(((p.xp - p.level_xp) / span) * 100));
  return h("div", { class: "xp" },
    h("div", { class: `progress xp-bar ${p.title.god ? "god" : ""}` }, h("span", { style: `width:${pct}%` })),
    h("div", { class: "progress-label" }, `${p.xp} XP · encore ${p.next_level_xp - p.xp} XP pour le niveau ${p.level + 1}`));
}

function renderProfileChip() {
  const chip = document.getElementById("profile-chip");
  if (!chip) return;
  const p = profile.data;
  if (!p) {
    chip.replaceChildren(h("span", { class: "muted" }, "Choisir un profil"));
    chip.setAttribute("href", "#/profils");
    return;
  }
  chip.setAttribute("href", "#/profil");
  const span = Math.max(1, p.next_level_xp - p.level_xp);
  const pct = Math.min(100, Math.round(((p.xp - p.level_xp) / span) * 100));
  chip.replaceChildren(avatar(p, "small"),
    h("span", { class: "chip-text" },
      h("span", { class: "chip-name" }, p.name, " ", titleBadge(p.title)),
      h("span", { class: "chip-level" }, `Niv. ${p.level} · ${p.xp} XP`,
        h("span", { class: `chip-bar ${p.title.god ? "god" : ""}` }, h("span", { style: `width:${pct}%` })))));
}

function toast(content, kind = "") {
  let host = document.getElementById("toasts");
  if (!host) {
    host = h("div", { id: "toasts" });
    document.body.append(host);
  }
  const el = h("div", { class: `toast ${kind}` }, content);
  host.append(el);
  setTimeout(() => el.classList.add("leave"), 3200);
  setTimeout(() => el.remove(), 3800);
}

/** Met à jour le profil après une validation réussie et fête l'XP gagnée. */
function celebrate(reward) {
  if (!reward || !profile.data) return;
  Object.assign(profile.data, reward.profile);
  renderProfileChip();
  if (reward.xp_gained > 0) toast(`+${reward.xp_gained} XP`, "xp");
  else toast("Déjà validé : pas d'XP en plus");
  if (reward.level_up) {
    const p = reward.profile;
    const overlay = h("div", { class: "levelup", onclick: () => overlay.remove() },
      h("div", { class: "levelup-card" },
        h("div", { class: "levelup-kicker" }, "Niveau supérieur !"),
        h("div", { class: "levelup-level" }, String(p.level)),
        reward.new_title ? h("div", {}, "Nouveau titre : ", titleBadge(p.title)) : titleBadge(p.title),
        h("button", { class: "btn primary" }, "Continuer")));
    document.body.append(overlay);
  }
}

async function renderProfilePicker() {
  document.title = "TDM · Profils";
  const list = await api("/api/profiles");
  const input = h("input", { class: "search", placeholder: "Ton pseudo", maxlength: 24, autofocus: true });
  const error = h("div");
  const choose = async (id) => {
    profile.select(id);
    await profile.load();
    location.hash = "#/";
  };
  const create = async (event) => {
    event.preventDefault();
    error.replaceChildren();
    try {
      const created = await api("/api/profiles", { method: "POST", body: { name: input.value } });
      await choose(created.id);
    } catch (err) {
      error.replaceChildren(h("div", { class: "error-box" }, err.message));
    }
  };
  app.replaceChildren(h("div", { class: "page narrow" },
    h("section", { class: "hero" },
      h("h1", {}, "Qui s'entraîne ?"),
      h("p", {}, "Chaque exercice réussi rapporte de l'XP : monte de niveau, débloque des titres et grimpe au classement.")),
    list.length ? h("div", { class: "profile-grid" }, list.map((p) =>
      h("button", { class: `profile-card ${p.title.god ? "god" : ""}`, onclick: () => choose(p.id) },
        avatar(p, "large"),
        h("strong", {}, p.name),
        titleBadge(p.title),
        h("span", { class: "muted" }, `Niveau ${p.level} · ${p.xp} XP`)))) : null,
    h("form", { class: "create-profile", onsubmit: create },
      h("h2", {}, list.length ? "Nouveau profil" : "Crée ton profil"),
      h("div", { class: "row" }, input, h("button", { class: "btn primary", type: "submit" }, "Créer")),
      error)));
}

async function renderProfile() {
  await profile.load();
  const p = profile.data;
  document.title = `TDM · ${p.name}`;
  const categories = CATEGORY_KEYS.map((key) => {
    const c = p.categories[key];
    const pct = c.total ? Math.round((c.done / c.total) * 100) : 0;
    return h("div", { class: "stat-card" },
      h("div", { class: "stat-head" }, h("span", { class: "icon" }, CATEGORIES[key].icon), h("strong", {}, CATEGORIES[key].title),
        c.title ? h("span", { class: "badge ok" }, c.title) : null),
      h("div", { class: "stat-value" }, `${c.done} / ${c.total}`),
      h("div", { class: "progress" }, h("span", { style: `width:${pct}%` })),
      h("div", { class: "progress-label" }, `${pct} % · ${c.xp} XP`),
      h("div", { class: "level-split" }, LEVELS.map(([level, label]) =>
        h("span", { class: `badge ${level}` }, `${label} ${c.levels[level] || 0}`))));
  });
  const ladder = p.titles.map((t) => {
    const unlocked = p.level >= t.level;
    return h("li", { class: unlocked ? "unlocked" : "" },
      h("span", { class: "ladder-mark" }, unlocked ? "✓" : "🔒"),
      h("strong", {}, t.name), h("span", { class: "muted" }, ` · niveau ${t.level} (${t.xp} XP)`),
      h("div", { class: "muted small" }, t.description));
  });
  if (p.title.god) {
    ladder.push(h("li", { class: "unlocked god" }, h("span", { class: "ladder-mark" }, "⚡"),
      h("strong", {}, "GOD"), h("div", { class: "muted small" }, p.title.description)));
  }
  const recent = p.recent.length ? h("ul", { class: "recent" }, p.recent.map((r) =>
    h("li", {}, h("span", { class: "icon" }, CATEGORIES[r.category].icon), " ", r.title || r.item_id,
      " ", levelBadge(r.level), h("span", { class: "muted" }, ` +${r.xp} XP · ${new Date(r.completed_at * 1000).toLocaleString("fr-FR")}`))))
    : h("p", { class: "muted" }, "Aucun exercice validé pour l'instant. Lance-toi !");
  const removeBtn = h("button", { class: "btn small danger" }, "Supprimer ce profil");
  removeBtn.addEventListener("click", async () => {
    if (removeBtn.dataset.confirm !== "1") {
      removeBtn.dataset.confirm = "1";
      removeBtn.textContent = "Confirmer la suppression (définitif)";
      return;
    }
    await api(`/api/profiles/${p.id}`, { method: "DELETE" });
    profile.select(null);
    await profile.load();
    location.hash = "#/profils";
  });

  app.replaceChildren(h("div", { class: "page" },
    h("section", { class: `profile-hero ${p.title.god ? "god" : ""}` },
      avatar(p, "xl"),
      h("div", { class: "profile-main" },
        h("h1", {}, p.name, " ", titleBadge(p.title)),
        h("div", { class: "profile-sub" },
          h("span", { class: "big-level" }, `Niveau ${p.level}`),
          h("a", { href: "#/classement" }, `#${p.rank} au classement sur ${p.total_profiles}`),
          h("span", { class: "muted" }, `${p.completed} exercice(s) validé(s)`)),
        xpBar(p)),
      h("div", { class: "profile-actions" },
        h("a", { class: "btn small", href: "#/profils" }, "Changer de profil"), removeBtn)),
    h("h2", {}, "Progression"),
    h("div", { class: "stat-grid" }, categories),
    h("div", { class: "two-cols" },
      h("section", {}, h("h2", {}, "Titres"), h("ul", { class: "ladder" }, ladder),
        h("p", { class: "muted small" }, "XP par exercice : Débutant 10 · Intermédiaire 25 · Avancé 50 · Expert 100.")),
      h("section", {}, h("h2", {}, "Activité récente"), recent))));
}

async function renderLeaderboard() {
  document.title = "TDM · Classement";
  const list = await api("/api/profiles");
  const medal = (rank) => ({ 1: "🥇", 2: "🥈", 3: "🥉" })[rank] || `#${rank}`;
  app.replaceChildren(h("div", { class: "page" },
    h("h1", {}, "🏆 Classement"),
    h("p", { class: "muted" }, "Classé par XP. Chaque exercice compte une seule fois."),
    h("table", { class: "leaderboard" },
      h("thead", {}, h("tr", {}, ["Rang", "Joueur", "Titre", "Niveau", "XP", "Exercices"].map((t) => h("th", {}, t)))),
      h("tbody", {}, list.map((p) =>
        h("tr", { class: `${p.id === profile.id ? "me" : ""} ${p.title.god ? "god" : ""}` },
          h("td", { class: "rank" }, medal(p.rank)),
          h("td", {}, h("span", { class: "who" }, avatar(p, "small"), p.name)),
          h("td", {}, titleBadge(p.title)),
          h("td", {}, String(p.level)),
          h("td", {}, h("strong", {}, String(p.xp))),
          h("td", {}, String(p.completed))))))));
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

profile.load().then(router);
