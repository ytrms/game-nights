const PAGE_CONFIG = window.PAGE_CONFIG || {};
const DATA_URL = `${PAGE_CONFIG.source || "./leaderboard.json"}?v=${Date.now()}`;
const TOKENS_URL = "./guest_tokens.json?v=" + Date.now();

async function fetchLeaderboard() {
  const response = await fetch(DATA_URL, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load leaderboard: ${response.status}`);
  }
  return response.json();
}

function asLocaleDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

async function fetchGuestTokens() {
  const response = await fetch(TOKENS_URL, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load guest tokens: ${response.status}`);
  }
  return response.json();
}

function normalizeGuestTokens(raw) {
  if (!raw) return {};
  if (Array.isArray(raw)) {
    return raw.reduce((map, entry) => {
      if (entry && typeof entry === "object") {
        const { token, name } = entry;
        if (token && name) {
          map[String(token)] = String(name);
        }
      }
      return map;
    }, {});
  }
  if (typeof raw === "object") {
    const source = raw.tokens && typeof raw.tokens === "object" ? raw.tokens : raw;
    return Object.keys(source).reduce((map, key) => {
      const value = source[key];
      if (typeof value === "string" && value.trim()) {
        map[String(key)] = value.trim();
      }
      return map;
    }, {});
  }
  return {};
}

function normalizeName(value) {
  if (value === undefined || value === null) {
    return "";
  }
  return String(value)
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function renderLeaderboard(players = [], highlightedName = null, labels = { singular: "pt", plural: "pts" }) {
  const container = document.querySelector("#leaderboard-list");
  const template = document.querySelector("#player-template");
  if (!container || !template) return;
  container.innerHTML = "";

  if (!players.length) {
    const li = document.createElement("li");
    li.className = "leaderboard-item empty";
    li.textContent = "No scores yet. Check back after the next game night!";
    container.appendChild(li);
    return;
  }

  players.forEach((player) => {
    const node = template.content.cloneNode(true);
    const li = node.querySelector(".leaderboard-item");
    const rank = node.querySelector(".player-rank");
    const avatar = node.querySelector(".player-avatar");
    const avatarWrapper = node.querySelector(".player-avatar-wrapper");
    const name = node.querySelector(".player-name");
    const points = node.querySelector(".player-points");

    li.dataset.rank = String(player.rank);
    rank.dataset.rank = player.rank;
    rank.textContent = `#${player.rank}`;
    name.textContent = player.player;
    const unit = player.points === 1 ? labels.singular : labels.plural;
    points.textContent = `${player.points} ${unit}`;
    applyAvatar(avatar, player.player, avatarWrapper);
    if (highlightedName && normalizeName(player.player) === normalizeName(highlightedName)) {
      li.classList.add("highlight");
    }
    container.appendChild(node);
  });
}

function getGuestTokenFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const raw =
    params.get("guest") ??
    params.get("token") ??
    params.get("code") ??
    params.get("ticket");
  if (!raw) return null;
  const decoded = decodeURIComponent(raw.replace(/\+/g, " ")).trim();
  if (!decoded) return null;
  return decoded;
}

function getAvatarBases(playerName) {
  if (!playerName) return [];
  const trimmed = playerName.trim();
  const encoded = encodeURIComponent(trimmed);
  const underscored = trimmed.replace(/\s+/g, "_");
  const ascii = normalizeName(trimmed).replace(/\s+/g, "_");
  const bases = [trimmed, encoded, underscored, ascii];
  const unique = [];
  const seen = new Set();
  bases.forEach((base) => {
    if (!base) return;
    const key = base.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    unique.push(base);
  });
  return unique;
}

function applyAvatar(img, playerName, wrapper) {
  if (!img) return;

  if (img._avatarErrorHandler) {
    img.removeEventListener("error", img._avatarErrorHandler);
    delete img._avatarErrorHandler;
  }

  const extensions = ["png", "jpg", "jpeg", "webp"];
  const bases = getAvatarBases(playerName);
  const sources = [];
  bases.forEach((base) => {
    extensions.forEach((ext) => {
      sources.push(`./avatars/${base}.${ext}`);
    });
  });

  let index = 0;

  if (!sources.length) {
    if (wrapper) wrapper.hidden = true;
    img.hidden = true;
    img.removeAttribute("src");
    img.alt = "";
    return;
  }

  const onError = () => {
    if (index >= sources.length) {
      img.removeEventListener("error", onError);
      if (wrapper) wrapper.hidden = true;
      img.hidden = true;
      img.removeAttribute("src");
      img.alt = "";
      return;
    }
    img.src = sources[index++];
  };

  img._avatarErrorHandler = onError;
  img.addEventListener("error", onError);
  if (wrapper) wrapper.hidden = false;
  img.hidden = false;
  img.alt = playerName ? `${playerName}'s avatar` : "";
  img.src = sources[index++];
}
function renderGreeting(tokens = {}) {
  const greetingEl = document.querySelector("#guest-greeting");
  if (!greetingEl) return null;
  const token = getGuestTokenFromUrl();
  if (!token) {
    greetingEl.hidden = true;
    greetingEl.textContent = "";
    return null;
  }
  const guestName = tokens[token];
  if (!guestName) {
    greetingEl.hidden = true;
    greetingEl.textContent = "";
    return null;
  }
  greetingEl.hidden = false;
  greetingEl.textContent = `Welcome to the party, ${guestName}!`;
  return guestName;
}

function renderScoringRules(rules = []) {
  const list = document.querySelector("#scoring-rules");
  const template = document.querySelector("#scoring-rule-template");
  if (!list || !template) return;
  list.innerHTML = "";

  if (!rules.length) {
    const li = document.createElement("li");
    li.className = "scoring-rule";
    li.textContent = "No scoring rules set. Add some in config.json.";
    list.appendChild(li);
    return;
  }

  rules.forEach((rule) => {
    const node = template.content.cloneNode(true);
    node.querySelector(".rule-label").textContent = rule.label;
    node.querySelector(".rule-points").textContent = `${rule.points} pts`;
    list.appendChild(node);
  });
}

function renderEvents(events = [], highlightedName = null, options = {}) {
  const {
    containerSelector = "#events-timeline",
    limit,
    emptyMessage = "No points logged yet. Awards will show here automatically.",
    awardPreviewLimit = null,
    allowExpand = false,
  } = options;

  const list = document.querySelector(containerSelector);
  const template = document.querySelector("#event-template");
  const awardTemplate = document.querySelector("#timeline-award-template");
  if (!list || !template || !awardTemplate) return;
  list.innerHTML = "";

  const items = typeof limit === "number" ? events.slice(0, limit) : events;

  if (!items.length) {
    const li = document.createElement("li");
    li.className = "timeline-item";
    li.textContent = emptyMessage;
    list.appendChild(li);
    return;
  }

  items.forEach((event) => {
    const node = template.content.cloneNode(true);
    node.querySelector(".timeline-title").textContent = event.name;
    node.querySelector(".timeline-date").textContent = asLocaleDate(event.date);
    const awardsList = node.querySelector(".timeline-awards");
    const expandButton = node.querySelector(".timeline-expand");

    if (!event.awards?.length) {
      const placeholder = document.createElement("li");
      placeholder.className = "timeline-award";
      placeholder.textContent = "Awards logged, details pending.";
      awardsList.appendChild(placeholder);
      if (expandButton) {
        expandButton.hidden = true;
      }
    } else {
      const previewCount =
        allowExpand && typeof awardPreviewLimit === "number" ? Math.max(0, awardPreviewLimit) : event.awards.length;
      const collapsedItems = [];

      event.awards.forEach((award, idx) => {
        const awardNode = awardTemplate.content.cloneNode(true);
        const awardItem = awardNode.querySelector(".timeline-award");
        const playerEl = awardNode.querySelector(".award-player");
        const reasonEl = awardNode.querySelector(".award-reason");
        const pointsEl = awardNode.querySelector(".award-points");

        playerEl.textContent = award.player;
        reasonEl.textContent = award.reason;
        pointsEl.textContent = `+${award.points}`;

        if (highlightedName && normalizeName(award.player) === normalizeName(highlightedName)) {
          playerEl.classList.add("highlighted-player");
          pointsEl.classList.add("highlighted-player");
          reasonEl.classList.add("highlighted-player-text");
        }

        if (allowExpand && idx >= previewCount) {
          if (awardItem) {
            awardItem.classList.add("is-collapsed");
            collapsedItems.push(awardItem);
          }
        }

        awardsList.appendChild(awardNode);
      });

      if (allowExpand && collapsedItems.length && expandButton) {
        expandButton.hidden = false;
        const hiddenCount = collapsedItems.length;
        const updateLabel = (expanded) => {
          expandButton.textContent = expanded
            ? "Hide awards"
            : hiddenCount === 1
            ? "Show 1 more"
            : `Show ${hiddenCount} more`;
        };
        const setExpanded = (expanded) => {
          collapsedItems.forEach((item) => {
            if (!item) return;
            item.classList.toggle("is-collapsed", !expanded);
          });
          updateLabel(expanded);
        };
        expandButton.dataset.expanded = "false";
        updateLabel(false);
        expandButton.addEventListener("click", () => {
          const expanded = expandButton.dataset.expanded === "true";
          const next = !expanded;
          expandButton.dataset.expanded = String(next);
          setExpanded(next);
        });
      } else if (expandButton) {
        expandButton.hidden = true;
        expandButton.textContent = "";
      }
    }

    list.appendChild(node);
  });
}

function formatPlacementLabel(placement) {
  if (placement === 1) return "1st place";
  if (placement === 2) return "2nd place";
  if (placement === 3) return "3rd place";
  return "Participated";
}

function renderPlays(plays = [], highlightedName = null, options = {}) {
  const {
    containerSelector = "#recent-plays",
    limit,
    emptyMessage = "No plays logged yet. Add one with the plays command.",
  } = options;

  const list = document.querySelector(containerSelector);
  const template = document.querySelector("#play-template");
  const awardTemplate = document.querySelector("#timeline-award-template");
  if (!list || !template || !awardTemplate) return;
  list.innerHTML = "";

  const items = typeof limit === "number" ? plays.slice(0, limit) : plays;

  if (!items.length) {
    const li = document.createElement("li");
    li.className = "timeline-item";
    li.textContent = emptyMessage;
    list.appendChild(li);
    return;
  }

  items.forEach((play) => {
    const node = template.content.cloneNode(true);
    node.querySelector(".timeline-title").textContent = play.game;
    node.querySelector(".timeline-date").textContent = asLocaleDate(play.date);
    const meta = node.querySelector(".timeline-meta");
    const parts = [];
    parts.push(play.scored ? "Ranked" : "Unranked");
    if (play.event) {
      parts.push(`@ ${play.event}`);
    }
    meta.textContent = parts.join(" • ");

    const resultsList = node.querySelector(".play-results");
    const results = play.results || [];
    if (!results.length) {
      const item = document.createElement("li");
      item.className = "timeline-award";
      item.textContent = "Players pending";
      resultsList.appendChild(item);
    } else {
      results.forEach((result) => {
        const resultNode = awardTemplate.content.cloneNode(true);
        const playerEl = resultNode.querySelector(".award-player");
        const reasonEl = resultNode.querySelector(".award-reason");
        const pointsEl = resultNode.querySelector(".award-points");
        playerEl.textContent = result.player;
        reasonEl.textContent = formatPlacementLabel(result.placement);
        pointsEl.textContent = result.points ? `+${result.points}` : "—";

        if (highlightedName && normalizeName(result.player) === normalizeName(highlightedName)) {
          playerEl.classList.add("highlighted-player");
          pointsEl.classList.add("highlighted-player");
          reasonEl.classList.add("highlighted-player-text");
        }

        resultsList.appendChild(resultNode);
      });
    }

    const notesEl = node.querySelector(".timeline-notes");
    if (play.notes) {
      notesEl.textContent = play.notes;
    } else {
      notesEl.remove();
    }

    list.appendChild(node);
  });
}

function renderPlayerActivity(activity = [], highlightedName = null) {
  const container = document.querySelector("#player-activity");
  const template = document.querySelector("#activity-card-template");
  if (!container || !template) return;
  container.innerHTML = "";

  const meaningful = activity.filter((entry) => entry.totalPlays > 0 || entry.games?.length);
  if (!meaningful.length) {
    const placeholder = document.createElement("p");
    placeholder.className = "timeline-notes";
    placeholder.textContent = "Log plays to build up player activity stats.";
    container.appendChild(placeholder);
    return;
  }

  meaningful.forEach((entry) => {
    const node = template.content.cloneNode(true);
    const card = node.querySelector(".activity-card");
    const nameEl = node.querySelector(".activity-player");
    const totalEl = node.querySelector(".activity-total");
    const statsEl = node.querySelector(".activity-stats");

    nameEl.textContent = entry.player;
    totalEl.textContent = `${entry.totalPlays} play${entry.totalPlays === 1 ? "" : "s"}`;

    const games = entry.games || [];
    if (games.length) {
      games.slice(0, 3).forEach((game) => {
        const dt = document.createElement("dt");
        dt.textContent = game.game;
        const dd = document.createElement("dd");
        dd.textContent = `${game.count}×`;
        statsEl.appendChild(dt);
        statsEl.appendChild(dd);
      });
    } else {
      const dt = document.createElement("dt");
      dt.textContent = "Games";
      const dd = document.createElement("dd");
      dd.textContent = "None yet";
      statsEl.appendChild(dt);
      statsEl.appendChild(dd);
    }

    const podiums = entry.podiums || {};
    const podiumTotal = (Number(podiums["1"] || 0) + Number(podiums["2"] || 0) + Number(podiums["3"] || 0));
    if (podiumTotal > 0) {
      const dt = document.createElement("dt");
      dt.textContent = "Podiums";
      const dd = document.createElement("dd");
      dd.textContent = `${podiums["1"] || 0}/${podiums["2"] || 0}/${podiums["3"] || 0}`;
      statsEl.appendChild(dt);
      statsEl.appendChild(dd);
    }

    if (highlightedName && normalizeName(entry.player) === normalizeName(highlightedName)) {
      card.classList.add("highlight");
    }

    container.appendChild(node);
  });
}

function hydrateMeta({ title, tagline, seasonLabel, lastUpdated }) {
  const titleEl = document.querySelector("#page-title");
  const taglineEl = document.querySelector("#page-tagline");
  const seasonEl = document.querySelector("#season-label");
  const updatedEl = document.querySelector("#last-updated");

  if (title) {
    document.title = title;
    titleEl.textContent = title;
  }
  if (tagline) {
    taglineEl.textContent = tagline;
  }
  if (seasonLabel) {
    seasonEl.textContent = seasonLabel;
    seasonEl.style.display = "inline-flex";
  } else {
    seasonEl.style.display = "none";
  }
  if (lastUpdated) {
    updatedEl.textContent = `Updated ${asLocaleDate(lastUpdated)}`;
  } else {
    updatedEl.textContent = "Updated automatically";
  }
}

function handleError(error) {
  console.error(error);
  const leaderboard = document.querySelector("#leaderboard-list");
  if (leaderboard) {
    leaderboard.innerHTML = "";
    const li = document.createElement("li");
    li.className = "leaderboard-item error";
    li.textContent =
      "We could not load the leaderboard right now. Refresh to try again or contact Lorenzo.";
    leaderboard.appendChild(li);
  }

  const plays = document.querySelector("#recent-plays");
  if (plays) {
    plays.innerHTML = "";
    const placeholder = document.createElement("li");
    placeholder.className = "timeline-item";
    placeholder.textContent = "Could not load plays.";
    plays.appendChild(placeholder);
  }

  const eventsList = document.querySelector("#events-timeline");
  if (eventsList) {
    eventsList.innerHTML = "";
    const placeholder = document.createElement("li");
    placeholder.className = "timeline-item";
    placeholder.textContent = "Could not load point log.";
    eventsList.appendChild(placeholder);
  }

  const allEventsList = document.querySelector("#all-events-list");
  if (allEventsList) {
    allEventsList.innerHTML = "";
    const placeholder = document.createElement("li");
    placeholder.className = "timeline-item";
    placeholder.textContent = "Could not load point log.";
    allEventsList.appendChild(placeholder);
  }

  const fullPlaysList = document.querySelector("#all-plays-list");
  if (fullPlaysList) {
    fullPlaysList.innerHTML = "";
    const placeholder = document.createElement("li");
    placeholder.className = "timeline-item";
    placeholder.textContent = "Could not load plays.";
    fullPlaysList.appendChild(placeholder);
  }

  const activity = document.querySelector("#player-activity");
  if (activity) {
    activity.innerHTML = "";
    const placeholder = document.createElement("p");
    placeholder.className = "timeline-notes";
    placeholder.textContent = "Player activity unavailable.";
    activity.appendChild(placeholder);
  }
}

async function init() {
  let guestTokens = {};
  let highlightedName = null;
  try {
    const tokensData = await fetchGuestTokens();
    guestTokens = normalizeGuestTokens(tokensData);
  } catch (error) {
    console.warn(error);
  }
  highlightedName = renderGreeting(guestTokens);

  try {
    const data = await fetchLeaderboard();
    hydrateMeta(data);

    const allPlays = data.allPlays || data.recentPlays || [];
    const allEvents = data.allEvents || data.recentEvents || [];
    const recentEvents = data.recentEvents || [];
    const searchSuffix = window.location.search || "";

    const pointsLabels = {
      singular: data.pointsLabelSingular || "pt",
      plural: data.pointsLabelPlural || "pts",
    };

    renderLeaderboard(data.leaderboard, highlightedName, pointsLabels);
    renderPlays(allPlays, highlightedName, { limit: 3 });
    renderScoringRules(data.scoringRules);
    renderEvents(recentEvents, highlightedName, {
      limit: 5,
      awardPreviewLimit: 5,
      allowExpand: true,
    });
    renderPlayerActivity(data.playerActivity, highlightedName);

    const basePlaysPage = data.mode === "unranked" ? "./plays-unranked.html" : "./plays.html";
    const baseEventsPage = data.mode === "unranked" ? "./points-unranked.html" : "./points.html";

    const viewAllPlaysButton = document.querySelector("#view-all-plays");
    if (viewAllPlaysButton) {
      viewAllPlaysButton.href = `${basePlaysPage}${searchSuffix}`;
      viewAllPlaysButton.style.display = allPlays.length > 3 ? "inline-flex" : "none";
    }

    const viewAllEventsButton = document.querySelector("#view-all-events");
    if (viewAllEventsButton) {
      viewAllEventsButton.href = `${baseEventsPage}${searchSuffix}`;
      viewAllEventsButton.style.display = allEvents.length > recentEvents.length ? "inline-flex" : "none";
    }

    const switchViewButton = document.querySelector("#switch-view");
    if (switchViewButton) {
      const targetHref = switchViewButton.getAttribute("href") || "./index.html";
      switchViewButton.href = `${targetHref}${searchSuffix}`;
    }

    if (document.querySelector("#all-plays-list")) {
      renderPlays(allPlays, highlightedName, {
        containerSelector: "#all-plays-list",
        emptyMessage: "No plays logged yet. Add one with the plays command.",
      });
      const backLink = document.querySelector("#back-to-leaderboard");
      if (backLink) {
        const base = backLink.getAttribute("href") || "./index.html";
        backLink.href = `${base}${searchSuffix}`;
      }
    }

    if (document.querySelector("#all-events-list")) {
      renderEvents(allEvents, highlightedName, {
        containerSelector: "#all-events-list",
        emptyMessage: "No points logged yet. Awards will show here automatically.",
        allowExpand: false,
      });
      const backLink = document.querySelector("#back-to-leaderboard");
      if (backLink) {
        const base = backLink.getAttribute("href") || "./index.html";
        backLink.href = `${base}${searchSuffix}`;
      }
    }
  } catch (error) {
    handleError(error);
  }
}

document.addEventListener("DOMContentLoaded", init);
