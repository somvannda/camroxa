(() => {
  const AUTH_KEY = "camxora_auth";

  const setAuth = () => {
    document.body.dataset.auth = localStorage.getItem(AUTH_KEY) === "1" ? "in" : "out";
  };
  setAuth();

  const faIcons = {
    "i-home": "fa-house",
    "i-compass": "fa-compass",
    "i-plus": "fa-plus",
    "i-chart": "fa-chart-simple",
    "i-library": "fa-rectangle-list",
    "i-users": "fa-users",
    "i-heart": "fa-heart",
    "i-bell": "fa-bell",
    "i-panel": "fa-table-columns",
    "i-chev-r": "fa-chevron-right",
    "i-chev-d": "fa-chevron-down",
    "i-chev-l": "fa-chevron-left",
    "i-arrow-r": "fa-arrow-right",
    "i-play": "fa-play",
    "i-prev": "fa-backward-step",
    "i-next": "fa-forward-step",
    "i-shuffle": "fa-shuffle",
    "i-repeat": "fa-repeat",
    "i-volume": "fa-volume-high",
    "i-queue": "fa-list-ul",
    "i-search": "fa-magnifying-glass",
    "i-text": "fa-file-lines",
    "i-lyrics": "fa-comment-dots",
    "i-remix": "fa-wand-magic-sparkles",
    "i-mic": "fa-microphone",
    "i-pause": "fa-pause",
    "i-music": "fa-music",
    "i-video": "fa-clapperboard",
    "i-calendar": "fa-calendar-days",
    "i-bar": "fa-chart-column",
    "i-folder": "fa-folder",
    "i-settings": "fa-gear",
    "i-grid": "fa-table-cells-large",
    "i-sun": "fa-sun",
    "i-moon": "fa-moon",
    "i-login": "fa-arrow-right-to-bracket",
    "i-user-plus": "fa-user-plus",
  };

  document.querySelectorAll("svg use").forEach((use) => {
    const href = use.getAttribute("href") || use.getAttribute("xlink:href") || "";
    const key = href.replace("#", "");
    const fa = faIcons[key];
    if (!fa) return;
    const svg = use.closest("svg");
    if (!svg) return;
    const size = parseFloat(getComputedStyle(svg).width) || 16;
    const icon = document.createElement("i");
    const classes = svg.getAttribute("class") || "";
    icon.className = `${classes} fa-classic fa-solid ${fa} fa-replaced`;
    icon.setAttribute("aria-hidden", "true");
    icon.style.fontSize = `${size}px`;
    icon.style.width = `${size}px`;
    icon.style.height = `${size}px`;
    svg.replaceWith(icon);
  });

  const closeMenus = (except) => {
    document.querySelectorAll(".menu.open").forEach((menu) => {
      if (menu !== except) menu.classList.remove("open");
    });
    document.querySelectorAll("[data-menu].open").forEach((btn) => {
      if (!except || !except.contains(btn)) btn.classList.remove("open");
    });
  };

  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-menu]");
    if (trigger) {
      event.preventDefault();
      const wrap = trigger.closest(".menu-wrap");
      const panel = wrap ? wrap.querySelector("[data-panel]") : null;
      if (panel) {
        const willOpen = !panel.classList.contains("open");
        closeMenus(panel);
        panel.classList.toggle("open", willOpen);
        trigger.classList.toggle("open", willOpen);
      }
      return;
    }

    if (!event.target.closest(".menu")) closeMenus();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeMenus();
      document.querySelectorAll(".modal-backdrop.open").forEach((modal) => closeModal(modal));
    }
  });

  document.querySelectorAll("[data-signout]").forEach((btn) => {
    btn.addEventListener("click", () => {
      localStorage.removeItem(AUTH_KEY);
      location.href = "index.html";
    });
  });

  document.querySelectorAll("[data-auth-form]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      localStorage.setItem(AUTH_KEY, "1");
      location.href = "index.html";
    });
  });

  const search = document.querySelector("[data-search-form]");
  if (search) {
    search.addEventListener("submit", (event) => {
      event.preventDefault();
      const input = search.querySelector("input");
      const q = (input?.value || "").trim();
      location.href = q ? `search.html?q=${encodeURIComponent(q)}` : "search.html";
    });
  }

  document.querySelectorAll("[data-guest]").forEach((el) => {
    el.addEventListener("click", () => {
      localStorage.setItem(AUTH_KEY, "1");
      location.href = "index.html";
    });
  });

  document.querySelectorAll("[data-tabs]").forEach((group) => {
    const tabs = [...group.querySelectorAll("[data-tab]")];
    if (!tabs.length) return;
    const panels = [...group.querySelectorAll("[data-panel-tab]")];

    const activate = (name) => {
      tabs.forEach((tab) => {
        const on = tab.dataset.tab === name;
        tab.classList.toggle("on", on);
        tab.setAttribute("aria-selected", on ? "true" : "false");
      });
      panels.forEach((panel) => {
        panel.hidden = panel.dataset.panelTab !== name;
      });
    };

    tabs.forEach((tab) => {
      tab.addEventListener("click", (event) => {
        event.preventDefault();
        activate(tab.dataset.tab);
        try {
          history.replaceState(null, "", `#${tab.dataset.tab}`);
        } catch {}
      });
    });

    const hash = location.hash.slice(1);
    const initial = hash && tabs.some((tab) => tab.dataset.tab === hash) ? hash : tabs[0].dataset.tab;
    activate(initial);
  });

  const closeModal = (modal) => {
    if (!modal) return;
    modal.classList.remove("open");
    setTimeout(() => {
      if (!modal.classList.contains("open")) modal.hidden = true;
    }, 180);
  };

  document.querySelectorAll("[data-modal-open]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      const modal = document.querySelector(`[data-modal-panel="${button.dataset.modalOpen}"]`);
      if (!modal) return;
      modal.hidden = false;
      requestAnimationFrame(() => modal.classList.add("open"));
    });
  });

  document.querySelectorAll("[data-modal-close]").forEach((button) => {
    button.addEventListener("click", () => closeModal(button.closest(".modal-backdrop")));
  });

  document.querySelectorAll(".modal-backdrop").forEach((modal) => {
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeModal(modal);
    });
  });

  document.querySelectorAll(".pack-option").forEach((option) => {
    option.addEventListener("click", () => {
      const modal = option.closest(".modal");
      if (!modal) return;
      modal.querySelectorAll(".pack-option").forEach((item) => item.classList.remove("on"));
      option.classList.add("on");
      const total = modal.querySelector("[data-pack-total]");
      if (total) total.textContent = `$${Number(option.dataset.price).toFixed(2)}`;
    });
  });

  const player = document.querySelector("[data-player]");
  if (player) {
    const tracks = [
      { title: "Phnom Penh Tonight", artist: "Sochcat AI", cover: "hero.png", duration: 252, elapsed: 208 },
      { title: "Bassac Moon", artist: "Kanya", cover: "hero.png", duration: 204, elapsed: 0 },
      {
        title: "Golden Hour",
        artist: "Malis",
        cover: "https://images.unsplash.com/photo-1461360228754-6e81c478b882?auto=format&fit=crop&w=600&q=80",
        duration: 182,
        elapsed: 0,
      },
    ];

    let current = { ...tracks[0] };
    let playing = false;
    let timer = null;
    let muted = false;

    const fmt = (value) => {
      const seconds = Math.max(0, Math.round(Number(value) || 0));
      return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
    };

    const parseTime = (value) => {
      const match = String(value || "").match(/(\d+):(\d{2})/);
      return match ? Number(match[1]) * 60 + Number(match[2]) : 240;
    };

    const toggleIcon = (button) => button?.querySelector(".fa-replaced, i");

    const syncPlayIcon = () => {
      const icon = toggleIcon(player.querySelector("[data-p-toggle]"));
      if (!icon) return;
      icon.classList.toggle("fa-play", !playing);
      icon.classList.toggle("fa-pause", playing);
      const button = player.querySelector("[data-p-toggle]");
      button.setAttribute("aria-pressed", String(playing));
      button.setAttribute("aria-label", playing ? "Pause" : "Play");
    };

    const render = () => {
      player.querySelectorAll("[data-p-title]").forEach((el) => {
        el.textContent = current.title;
      });
      player.querySelectorAll("[data-p-artist]").forEach((el) => {
        el.textContent = current.artist;
      });
      const cover = player.querySelector("[data-p-cover]");
      if (cover) cover.src = current.cover;
      const elapsed = player.querySelector("[data-p-elapsed]");
      const duration = player.querySelector("[data-p-duration]");
      const seek = player.querySelector("[data-p-seek]");
      if (elapsed) elapsed.textContent = fmt(current.elapsed);
      if (duration) duration.textContent = fmt(current.duration);
      if (seek) {
        seek.max = String(current.duration);
        seek.value = String(current.elapsed);
        seek.style.setProperty("--p", `${Math.min(100, (current.elapsed / current.duration) * 100)}%`);
      }
      player.querySelectorAll("[data-queue-index]").forEach((item) => {
        const track = tracks[Number(item.dataset.queueIndex)];
        item.classList.toggle("on", Boolean(track && track.title === current.title));
      });
      player.classList.toggle("is-playing", playing);
      syncPlayIcon();
    };

    const stopTimer = () => {
      if (timer) window.clearInterval(timer);
      timer = null;
    };

    const setPlaying = (next) => {
      playing = Boolean(next);
      stopTimer();
      if (playing) {
        timer = window.setInterval(() => {
          current.elapsed = Math.min(current.duration, current.elapsed + 1);
          if (current.elapsed >= current.duration) setPlaying(false);
          render();
        }, 1000);
      }
      render();
    };

    const load = (track, autoplay = true) => {
      current = { ...track };
      current.elapsed = Math.max(0, Math.min(current.elapsed || 0, current.duration || 240));
      render();
      setPlaying(autoplay);
    };

    const markPlaying = (card) => {
      document.querySelectorAll(".card.is-playing, .continue-card.is-playing").forEach((item) => {
        item.classList.remove("is-playing");
      });
      if (card) card.classList.add("is-playing");
    };

    const queuePanel = player.querySelector("[data-p-queue-panel]");
    const queueButton = player.querySelector("[data-p-queue]");

    const setQueue = (open) => {
      if (!queuePanel || !queueButton) return;
      queueButton.setAttribute("aria-expanded", String(open));
      if (open) {
        queuePanel.hidden = false;
        window.requestAnimationFrame(() => queuePanel.classList.add("open"));
      } else {
        queuePanel.classList.remove("open");
        window.setTimeout(() => {
          if (!queuePanel.classList.contains("open")) queuePanel.hidden = true;
        }, 160);
      }
    };

    player.querySelector("[data-p-toggle]")?.addEventListener("click", () => setPlaying(!playing));

    player.querySelector("[data-p-shuffle]")?.addEventListener("click", (event) => {
      const button = event.currentTarget;
      const on = button.getAttribute("aria-pressed") !== "true";
      button.setAttribute("aria-pressed", String(on));
      button.classList.toggle("on", on);
    });

    player.querySelector("[data-p-repeat]")?.addEventListener("click", (event) => {
      const button = event.currentTarget;
      const on = button.getAttribute("aria-pressed") !== "true";
      button.setAttribute("aria-pressed", String(on));
      button.classList.toggle("on", on);
    });

    const moveTrack = (delta) => {
      const found = tracks.findIndex((track) => track.title === current.title);
      const base = found === -1 ? 0 : found;
      const next = tracks[(base + delta + tracks.length) % tracks.length];
      load(next, playing);
    };

    player.querySelector("[data-p-prev]")?.addEventListener("click", () => moveTrack(-1));
    player.querySelector("[data-p-next]")?.addEventListener("click", () => moveTrack(1));

    player.querySelector("[data-p-like]")?.addEventListener("click", (event) => {
      const button = event.currentTarget;
      const on = button.getAttribute("aria-pressed") !== "true";
      button.setAttribute("aria-pressed", String(on));
      button.classList.toggle("liked", on);
      button.setAttribute("aria-label", on ? "Unlike this track" : "Like this track");
    });

    player.querySelector("[data-p-mute]")?.addEventListener("click", (event) => {
      const button = event.currentTarget;
      muted = !muted;
      button.setAttribute("aria-pressed", String(muted));
      button.setAttribute("aria-label", muted ? "Unmute" : "Mute");
      button.classList.toggle("on", muted);
      const icon = toggleIcon(button);
      if (icon) {
        icon.classList.toggle("fa-volume-high", !muted);
        icon.classList.toggle("fa-volume-xmark", muted);
      }
    });

    player.querySelector("[data-p-seek]")?.addEventListener("input", (event) => {
      current.elapsed = Number(event.currentTarget.value);
      render();
    });

    queueButton?.addEventListener("click", (event) => {
      event.stopPropagation();
      setQueue(queueButton.getAttribute("aria-expanded") !== "true");
    });

    player.querySelectorAll("[data-queue-index]").forEach((item) => {
      item.addEventListener("click", () => {
        const track = tracks[Number(item.dataset.queueIndex)];
        if (!track) return;
        load({ ...track, elapsed: 0 }, true);
        setQueue(false);
      });
    });

    document.addEventListener("click", (event) => {
      if (!queuePanel || queuePanel.hidden) return;
      if (event.target.closest("[data-p-queue-panel], [data-p-queue]")) return;
      setQueue(false);
    });

    document.querySelectorAll(".card .play").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        const card = button.closest(".card");
        if (!card) return;
        const img = card.querySelector(".art img");
        const title = card.querySelector("h3")?.textContent.trim();
        const artist = card.querySelector("p")?.textContent.trim();
        const time = card.querySelector(".stats span:last-child")?.textContent.trim();
        if (!title) return;
        markPlaying(card);
        load(
          {
            title,
            artist: artist || "Camxora",
            cover: img?.getAttribute("src") || "hero.png",
            duration: parseTime(time),
            elapsed: 0,
          },
          true
        );
      });
    });

    document.querySelectorAll(".continue-card").forEach((card) => {
      const button = card.querySelector(".cc-play");
      if (!button) return;
      button.addEventListener("click", (event) => {
        event.preventDefault();
        const img = card.querySelector("img");
        const title = card.querySelector(".cc-copy strong")?.textContent.trim();
        const artist = card.querySelector(".cc-copy span")?.textContent.trim();
        if (!title) return;
        markPlaying(card);
        load(
          {
            title,
            artist: artist || "Camxora",
            cover: img?.getAttribute("src") || "hero.png",
            duration: Number(card.dataset.duration) || 204,
            elapsed: Number(card.dataset.elapsed) || 0,
          },
          true
        );
      });
    });

    document.addEventListener("keydown", (event) => {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.target.closest("input, textarea, select, button, a, [contenteditable='true']")) return;
      if (event.code === "Space") {
        event.preventDefault();
        setPlaying(!playing);
      } else if (event.key === "ArrowRight") {
        current.elapsed = Math.min(current.duration, current.elapsed + 5);
        render();
      } else if (event.key === "ArrowLeft") {
        current.elapsed = Math.max(0, current.elapsed - 5);
        render();
      } else if (event.key.toLowerCase() === "m") {
        player.querySelector("[data-p-mute]")?.click();
      } else if (event.key.toLowerCase() === "l") {
        player.querySelector("[data-p-like]")?.click();
      } else if (event.key.toLowerCase() === "q") {
        setQueue(queueButton?.getAttribute("aria-expanded") !== "true");
      }
    });

    render();
  }

  const generateButton = document.querySelector("[data-create-generate]");
  if (generateButton) {
    const status = document.querySelector("[data-create-status]");
    generateButton.addEventListener("click", () => {
      if (generateButton.disabled) return;
      const original = generateButton.innerHTML;
      generateButton.disabled = true;
      generateButton.classList.add("is-busy");
      generateButton.textContent = "Generating 2 versions…";
      if (status) {
        status.classList.remove("is-ready");
        status.textContent = "Composing melody, vocal and mix…";
      }
      window.setTimeout(() => {
        generateButton.disabled = false;
        generateButton.classList.remove("is-busy");
        generateButton.innerHTML = original;
        if (status) {
          status.classList.add("is-ready");
          status.innerHTML = "<b>2 versions ready</b> — preview them below.";
        }
      }, 2400);
    });
  }
})();
