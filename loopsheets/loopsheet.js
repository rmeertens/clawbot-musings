// Shared loopsheet renderer.
// Each song page calls renderLoopsheet({ loops, song, defaultBpm }).
//
// Data shape:
//   loops = {
//     red:    { name, instrument, how, notation },
//     blue:   { ... },
//     ...
//   }
//   song = [
//     {
//       tag, title, meta,
//       bars: [
//         { loops: ["red","blue"], text: "lyric for this bar", silent?: false, colSpan?: 1 },
//         ...
//       ],
//     },
//     ...
//   ]
//
// Each bar holds its own slice of text and lists the loops active during that bar.
// A bar with colSpan: N occupies N grid cells AND counts as N bars for playback timing —
// handy for stage directions ("record 4 bars of percussion") or long-held vocal moments.

const LOOP_COLOR_VAR = {
  red:    "var(--loop-red)",
  blue:   "var(--loop-blue)",
  green:  "var(--loop-green)",
  yellow: "var(--loop-yellow)",
  purple: "var(--loop-purple)",
  orange: "var(--loop-orange)",
};

const LOOP_LABEL = {
  red:    "Red",
  blue:   "Blue",
  green:  "Green",
  yellow: "Yellow",
  purple: "Purple",
  orange: "Orange",
};

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function renderLoopLibrary(loops, mountEl) {
  mountEl.innerHTML = Object.entries(loops).map(([id, l]) => `
    <article class="loop-card c-${id}">
      <div class="swatch-row">
        <div class="loop-swatch"></div>
        <span class="name">${escapeHtml(LOOP_LABEL[id])}</span>
      </div>
      <h3>${escapeHtml(l.name)}</h3>
      <p class="instrument">${escapeHtml(l.instrument)}</p>
      <p class="how">${l.how}</p>
      ${l.notation ? `<pre class="notation">${escapeHtml(l.notation)}</pre>` : ""}
    </article>
  `).join("");
}

function renderLegend(loops, mountEl) {
  mountEl.innerHTML = Object.entries(loops).map(([id, l]) => `
    <span class="item">
      <span class="dot" style="--loop-color: ${LOOP_COLOR_VAR[id]}"></span>
      ${escapeHtml(LOOP_LABEL[id])} — ${escapeHtml(l.name)}
    </span>
  `).join("");
}

function renderSong(song, mountEl) {
  mountEl.innerHTML = "";
  const allBarEls = [];

  song.forEach((section, sIdx) => {
    const sec = document.createElement("section");
    sec.className = "song-section card";
    sec.innerHTML = `
      <span class="section-tag">${escapeHtml(section.tag)}</span>
      <h3>${escapeHtml(section.title)}</h3>
      <p class="meta">${escapeHtml(section.meta)}</p>
    `;

    const barsEl = document.createElement("div");
    barsEl.className = "bars";

    let barCursor = 1;
    section.bars.forEach((bar) => {
      const span = Math.max(1, bar.colSpan || 1);
      const fromBar = barCursor;
      const toBar = barCursor + span - 1;
      const numLabel = span > 1 ? `${fromBar}–${toBar}` : `${fromBar}`;

      const stripes = (bar.loops || []).map((id) =>
        `<span class="stripe" style="--loop-color: ${LOOP_COLOR_VAR[id]}" title="${escapeHtml(LOOP_LABEL[id] || "")} — ${escapeHtml((loopsLookup && loopsLookup[id] && loopsLookup[id].name) || "")}"></span>`
      ).join("");

      const text = bar.text || "";
      const textHtml = bar.silent
        ? `<span class="silent">${escapeHtml(text)}</span>`
        : escapeHtml(text);

      const barEl = document.createElement("div");
      barEl.className = "bar" + (text.trim() === "" ? " empty" : "");
      barEl.dataset.section = sIdx;
      barEl.dataset.bar = fromBar;
      if (span > 1) barEl.style.gridColumn = `span ${span}`;
      barEl.innerHTML = `
        <span class="bar-num">${numLabel}</span>
        <div class="stripes">${stripes}</div>
        <p class="text">${textHtml}</p>
      `;

      barsEl.appendChild(barEl);
      allBarEls.push({
        el: barEl,
        sectionTag: section.tag,
        fromBar, toBar, span,
      });
      barCursor += span;
    });

    sec.appendChild(barsEl);
    mountEl.appendChild(sec);
  });

  return allBarEls;
}

// Shared state used by renderSong for stripe tooltips
let loopsLookup = null;

function setupPlayer(allBarEls, defaultBpm) {
  const playBtn = document.getElementById("playBtn");
  const stopBtn = document.getElementById("stopBtn");
  const bpm = document.getElementById("bpm");
  const bpmLabel = document.getElementById("bpmLabel");
  const nowPlaying = document.getElementById("nowPlaying");

  bpm.value = defaultBpm;
  bpmLabel.textContent = `${defaultBpm} BPM`;

  const totalBars = allBarEls.reduce((acc, b) => acc + b.span, 0);
  const initLabel = allBarEls.length
    ? `${allBarEls[0].sectionTag} · bar ${allBarEls[0].fromBar}`
    : "—";
  nowPlaying.textContent = initLabel;

  let timer = null;
  let barIdx = 0; // position in bar-units (not array-units) across whole song

  function findBarEl(barIndex) {
    let cum = 0;
    for (const b of allBarEls) {
      if (barIndex >= cum && barIndex < cum + b.span) return { b, relBar: barIndex - cum };
      cum += b.span;
    }
    return null;
  }

  function highlight(barIndex) {
    allBarEls.forEach((b) => b.el.classList.remove("active"));
    const hit = findBarEl(barIndex);
    if (hit) {
      hit.b.el.classList.add("active");
      const n = hit.b.fromBar + hit.relBar;
      nowPlaying.textContent = `${hit.b.sectionTag} · bar ${n}`;
      hit.b.el.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }

  function barMs() { return (60 / Number(bpm.value)) * 4 * 1000; }

  function tick() {
    highlight(barIdx);
    barIdx = (barIdx + 1) % totalBars;
    timer = setTimeout(tick, barMs());
  }

  playBtn.addEventListener("click", () => {
    if (timer) {
      clearTimeout(timer);
      timer = null;
      playBtn.textContent = "▶ Play";
    } else {
      playBtn.textContent = "⏸ Pause";
      tick();
    }
  });

  stopBtn.addEventListener("click", () => {
    clearTimeout(timer);
    timer = null;
    barIdx = 0;
    playBtn.textContent = "▶ Play";
    allBarEls.forEach((b) => b.el.classList.remove("active"));
    nowPlaying.textContent = initLabel;
  });

  bpm.addEventListener("input", () => {
    bpmLabel.textContent = `${bpm.value} BPM`;
  });
}

// Convenience helpers for song data:

// One bar. `text` defaults to "" for instrumental/silent bars.
function b(loops, text = "", opts = {}) {
  return { loops: [...loops], text, ...opts };
}

// N identical bars (same loops, same text — often empty for pure build sections).
function rep(n, loops, text = "") {
  return Array.from({ length: n }, () => ({ loops: [...loops], text }));
}

// One bar that visually spans several (for multi-bar stage directions).
function span(n, loops, text, opts = {}) {
  return { loops: [...loops], text, colSpan: n, ...opts };
}

function renderLoopsheet({ loops, song, defaultBpm }) {
  loopsLookup = loops;
  renderLoopLibrary(loops, document.getElementById("loopLibrary"));
  renderLegend(loops, document.getElementById("legend"));
  const allBarEls = renderSong(song, document.getElementById("songRoot"));
  setupPlayer(allBarEls, defaultBpm);
}
