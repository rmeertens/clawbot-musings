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
//     { tag, title, meta, bars: [["red", "blue"], ...], lyrics: [{ span, text, silent? }, ...] },
//     ...
//   ]

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

    let barCursor = 0;
    section.lyrics.forEach((line) => {
      const lineEl = document.createElement("div");
      lineEl.className = "lyric-line";
      lineEl.style.setProperty("--bars", line.span);

      const barsEl = document.createElement("div");
      barsEl.className = "bars";

      for (let b = 0; b < line.span; b++) {
        const bar = section.bars[barCursor] || [];
        const barEl = document.createElement("div");
        barEl.className = "bar";
        barEl.dataset.section = sIdx;
        barEl.dataset.bar = barCursor + 1;
        barEl.innerHTML = `
          <span class="bar-num">bar ${barCursor + 1}</span>
          <div class="dots">
            ${bar.map((id) => `<span class="dot" style="--loop-color: ${LOOP_COLOR_VAR[id]}" title="${escapeHtml(LOOP_LABEL[id])}"></span>`).join("")}
          </div>
        `;
        barsEl.appendChild(barEl);
        allBarEls.push({ el: barEl, sectionTag: section.tag, barNum: barCursor + 1 });
        barCursor++;
      }

      const text = document.createElement("p");
      if (line.silent) {
        text.innerHTML = `<span class="silent">${escapeHtml(line.text)}</span>`;
      } else {
        text.textContent = line.text;
      }

      lineEl.appendChild(barsEl);
      lineEl.appendChild(text);
      sec.appendChild(lineEl);
    });

    mountEl.appendChild(sec);
  });

  return allBarEls;
}

function setupPlayer(allBarEls, defaultBpm) {
  const playBtn = document.getElementById("playBtn");
  const stopBtn = document.getElementById("stopBtn");
  const bpm = document.getElementById("bpm");
  const bpmLabel = document.getElementById("bpmLabel");
  const nowPlaying = document.getElementById("nowPlaying");

  bpm.value = defaultBpm;
  bpmLabel.textContent = `${defaultBpm} BPM`;

  const initLabel = allBarEls.length
    ? `${allBarEls[0].sectionTag} · bar ${allBarEls[0].barNum}`
    : "—";
  nowPlaying.textContent = initLabel;

  let timer = null;
  let idx = 0;

  function highlight(i) {
    allBarEls.forEach((b, j) => b.el.classList.toggle("active", i === j));
    if (allBarEls[i]) {
      const b = allBarEls[i];
      nowPlaying.textContent = `${b.sectionTag} · bar ${b.barNum}`;
      b.el.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }

  function barMs() { return (60 / Number(bpm.value)) * 4 * 1000; }

  function tick() {
    highlight(idx);
    idx = (idx + 1) % allBarEls.length;
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
    idx = 0;
    playBtn.textContent = "▶ Play";
    allBarEls.forEach((b) => b.el.classList.remove("active"));
    nowPlaying.textContent = initLabel;
  });

  bpm.addEventListener("input", () => {
    bpmLabel.textContent = `${bpm.value} BPM`;
  });
}

// Convenience helper: repeat a layer set across N bars.
function rep(n, layers) {
  return Array.from({ length: n }, () => [...layers]);
}

function renderLoopsheet({ loops, song, defaultBpm }) {
  renderLoopLibrary(loops, document.getElementById("loopLibrary"));
  renderLegend(loops, document.getElementById("legend"));
  const allBarEls = renderSong(song, document.getElementById("songRoot"));
  setupPlayer(allBarEls, defaultBpm);
}
