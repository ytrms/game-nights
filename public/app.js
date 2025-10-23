const DATA_URL = "./leaderboard.json?v=" + Date.now();

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

function renderLeaderboard(players = []) {
  const container = document.querySelector("#leaderboard-list");
  const template = document.querySelector("#player-template");
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
    const name = node.querySelector(".player-name");
    const points = node.querySelector(".player-points");
    const awardsList = node.querySelector(".player-awards");
    const awardTemplate = document.querySelector("#award-row-template");

    li.dataset.rank = String(player.rank);
    rank.dataset.rank = player.rank;
    rank.textContent = `#${player.rank}`;
    name.textContent = player.player;
    points.innerHTML = `<strong>${player.points}</strong> point${player.points === 1 ? "" : "s"} total`;

    if (!player.breakdown?.length) {
      awardsList.innerHTML =
        '<div class="award-row"><dt>Points so far</dt><dd>Keep it rolling!</dd></div>';
    } else {
      player.breakdown.forEach((award) => {
        const awardNode = awardTemplate.content.cloneNode(true);
        awardNode.querySelector(".award-reason").textContent = award.reason;
        awardNode.querySelector(".award-count").textContent = `${award.count} × ${award.points} pts`;
        awardsList.appendChild(awardNode);
      });
    }
    container.appendChild(node);
  });
}

function renderScoringRules(rules = []) {
  const list = document.querySelector("#scoring-rules");
  const template = document.querySelector("#scoring-rule-template");
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

function renderEvents(events = []) {
  const list = document.querySelector("#events-timeline");
  const template = document.querySelector("#event-template");
  const awardTemplate = document.querySelector("#timeline-award-template");
  list.innerHTML = "";

  if (!events.length) {
    const li = document.createElement("li");
    li.className = "timeline-item";
    li.textContent = "No events logged yet. Awards will show here automatically.";
    list.appendChild(li);
    return;
  }

  events.slice(0, 8).forEach((event) => {
    const node = template.content.cloneNode(true);
    node.querySelector(".timeline-title").textContent = event.name;
    node.querySelector(".timeline-date").textContent = asLocaleDate(event.date);
    const awardsList = node.querySelector(".timeline-awards");

    if (!event.awards?.length) {
      const placeholder = document.createElement("li");
      placeholder.className = "timeline-award";
      placeholder.textContent = "Awards logged, details pending.";
      awardsList.appendChild(placeholder);
    } else {
      event.awards.forEach((award) => {
        const awardNode = awardTemplate.content.cloneNode(true);
        awardNode.querySelector(".award-player").textContent = award.player;
        awardNode.querySelector(".award-reason").textContent = award.reason;
        awardNode.querySelector(".award-points").textContent = `+${award.points}`;
        awardsList.appendChild(awardNode);
      });
    }

    list.appendChild(node);
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
  leaderboard.innerHTML = "";
  const li = document.createElement("li");
  li.className = "leaderboard-item error";
  li.textContent =
    "We could not load the leaderboard right now. Refresh to try again or contact Lorenzo.";
  leaderboard.appendChild(li);
}

async function init() {
  try {
    const data = await fetchLeaderboard();
    hydrateMeta(data);
    renderLeaderboard(data.leaderboard);
    renderScoringRules(data.scoringRules);
    renderEvents(data.recentEvents);
  } catch (error) {
    handleError(error);
  }
}

document.addEventListener("DOMContentLoaded", init);
