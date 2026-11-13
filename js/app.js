/* Same-origin JSON only. This file does not call RSS feeds or API-Football. */
(function () {
  const LIVE_SITE = "https://tulifulegend.github.io/arsenal-info-center/";
  const FAV_KEY = "aic-favorite-urls-v1";
  const TABS = ["news", "fixtures", "podcasts", "about"];
  const FILES = ["news", "fixtures", "podcasts", "status"];

  const fullTime = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "numeric",
    day: "numeric",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });

  const state = {
    data: null,
    snapshot: false,
    source: "all",
    favOnly: false,
    query: "",
    favs: loadFavs(),
    favError: "",
  };

  document.querySelectorAll("[data-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      const tab = button.getAttribute("data-tab");
      if (location.hash.replace("#", "") === tab) showTab(tab);
      else location.hash = tab;
    });
  });
  window.addEventListener("hashchange", () => showTab(currentTab()));

  const search = document.getElementById("search");
  search.addEventListener("input", () => {
    state.query = search.value.trim().toLowerCase();
    renderNews();
  });
  document.querySelectorAll("[data-source]").forEach((button) => {
    button.addEventListener("click", () => {
      state.source = button.getAttribute("data-source");
      document.querySelectorAll("[data-source]").forEach((item) => {
        item.setAttribute("aria-pressed", String(item === button));
      });
      renderNews();
    });
  });
  document.getElementById("fav-only").addEventListener("click", (event) => {
    state.favOnly = !state.favOnly;
    event.currentTarget.setAttribute("aria-pressed", String(state.favOnly));
    renderNews();
  });
  showTab(currentTab());

  load()
    .then((result) => {
      state.data = result.data;
      state.snapshot = result.snapshot;
      showTab(currentTab());
      renderBanner();
      renderSnapshotNote();
      renderNews();
      renderFixtures();
      renderPodcasts();
      renderStatus();
    })
    .catch(() => {
      const banner = document.getElementById("banner");
      banner.hidden = false;
      banner.className = "banner";
      banner.textContent =
        "页面没有读到数据文件。如果这是直接双击打开的 index.html，浏览器不允许它读取旁边的 JSON。请打开线上网站，或打开已经装进数据的 snapshot.html。自动更新不会在 file:// 里发生。";
    });

  function currentTab() {
    const name = location.hash.replace("#", "");
    return TABS.indexOf(name) === -1 ? "news" : name;
  }

  function showTab(name) {
    TABS.forEach((tab) => {
      const panel = document.getElementById("panel-" + tab);
      const button = document.getElementById("tab-" + tab);
      const active = tab === name;
      if (panel) panel.hidden = !active;
      if (button) {
        if (active) button.setAttribute("aria-current", "page");
        else button.removeAttribute("aria-current");
      }
    });
  }

  async function load() {
    if (window.__AIC_DATA__ && window.__AIC_DATA__.news) {
      return { data: window.__AIC_DATA__, snapshot: true };
    }
    const version = window.__AIC_VERSION__ || "";
    const query = version ? "?v=" + encodeURIComponent(version) : "";
    const pairs = await Promise.all(
      FILES.map(async (name) => {
        const response = await fetch("data/" + name + ".json" + query, { cache: "no-cache" });
        if (!response.ok) throw new Error(name);
        return [name, await response.json()];
      })
    );
    return { data: Object.fromEntries(pairs), snapshot: false };
  }

  function renderBanner() {
    const banner = document.getElementById("banner");
    const status = state.data.status || {};
    if (!status.banner) {
      banner.hidden = true;
      return;
    }
    banner.hidden = false;
    banner.className = status.bannerLevel === "info" ? "banner banner-info" : "banner";
    banner.textContent = status.banner;
  }

  function renderSnapshotNote() {
    const note = document.getElementById("snapshot-note");
    if (!state.snapshot) {
      note.hidden = true;
      return;
    }
    note.hidden = false;
    note.textContent = "";
    const when = bj(state.data.status && state.data.status.generatedAt, true);
    note.append(
      document.createTextNode(
        "你打开的是快照，生成于 " + when + "。它停在当时的数据，不会自己变新，也不会在这台电脑上请求第三方接口。要看持续更新的版本，请打开线上网站。"
      )
    );
    note.append(document.createTextNode(" "));
    const link = h("a", { href: LIVE_SITE }, "打开会自动更新的网站");
    note.append(link);
  }

  function renderNews() {
    const news = (state.data && state.data.news) || { items: [] };
    const list = document.getElementById("news-list");
    const count = document.getElementById("news-count");
    const note = document.getElementById("fav-note");
    list.textContent = "";
    const items = (news.items || []).filter(matchesNews);
    count.textContent = items.length ? "共 " + items.length + " 条" : "";
    note.hidden = !state.favError;
    note.textContent = state.favError;
    if (!items.length) {
      list.append(
        h(
          "p",
          { class: "empty" },
          news.items && news.items.length
            ? "没有符合条件的新闻。可以清空搜索，或关掉「只看收藏」。"
            : news.message || "暂时没有新闻。"
        )
      );
      return;
    }
    items.forEach((item) => list.append(newsCard(item)));
  }

  function matchesNews(item) {
    if (state.source !== "all" && item.sourceId !== state.source) return false;
    if (state.favOnly && !state.favs.has(item.url)) return false;
    if (!state.query) return true;
    const haystack = (item.title + " " + item.summary + " " + item.source).toLowerCase();
    return haystack.indexOf(state.query) !== -1;
  }

  function newsCard(item) {
    const card = h("article", { class: "card" });
    const top = h("div", { class: "card-top" });
    top.append(h("span", { class: "source" }, item.source || "来源"));
    const saved = state.favs.has(item.url);
    const star = h("button", {
      type: "button",
      class: "star",
      "aria-pressed": String(saved),
    }, saved ? "已收藏" : "收藏");
    star.addEventListener("click", () => toggleFav(item.url, star));
    top.append(star);
    card.append(top);
    const title = h("h3");
    title.append(externalLink(item.url, item.title));
    card.append(title);
    card.append(h("p", { class: "time" }, "发布时间 " + bj(item.publishedAt, true)));
    card.append(h("p", { class: "summary" }, item.summary || "（来源未提供摘要）"));
    const more = externalLink(item.url, "阅读原文");
    more.className = "more";
    card.append(more);
    return card;
  }

  function toggleFav(url, button) {
    if (state.favs.has(url)) state.favs.delete(url);
    else state.favs.add(url);
    const saved = saveFavs(state.favs);
    state.favError = saved ? "" : "这个浏览器没有存下收藏（可能是无痕模式），刷新后会消失。";
    button.setAttribute("aria-pressed", String(state.favs.has(url)));
    button.textContent = state.favs.has(url) ? "已收藏" : "收藏";
    renderNews();
  }

  function renderFixtures() {
    const root = document.getElementById("fixtures-root");
    const fixtures = (state.data && state.data.fixtures) || {};
    root.textContent = "";
    const coverage = fixtures.coverage || {};
    const note = h("div", {
      class: coverage.warning ? "coverage warn" : "coverage",
    });
    note.append(h("p", { class: "summary" }, fixtures.scoreDisclaimer || "比分来自最近一次成功更新，不是实时比分。"));
    if (fixtures.message) note.append(h("p", { class: "summary" }, fixtures.message));
    if (coverage.seasonLabel) {
      const names = (coverage.competitions || [])
        .map((item) => (item.nameZh || item.name || "赛事") + " " + item.matches + " 场")
        .join("、");
      note.append(
        h(
          "p",
          { class: "summary" },
          "赛季 " + coverage.seasonLabel + (names ? "。实际拿到的赛事：" + names + "。" : "。")
        )
      );
    }
    if (coverage.warning) note.append(h("p", { class: "summary" }, coverage.warning));
    root.append(note);

    if (!fixtures.available && !(fixtures.matches || []).length) {
      root.append(h("p", { class: "empty" }, "赛程列表是空的。新闻和播客不受影响。"));
      return;
    }
    if (fixtures.nextMatch) {
      root.append(h("h3", { class: "subhead" }, fixtures.nextMatch.status === "inplay" ? "当前这场" : "下一场"));
      root.append(matchHero(fixtures.nextMatch));
    } else {
      root.append(h("p", { class: "empty" }, "最近这次数据里没有尚未结束的比赛。"));
    }
    if ((fixtures.upcoming || []).length) {
      root.append(h("h3", { class: "subhead" }, "随后几场"));
      const list = h("div", { class: "result-list" });
      fixtures.upcoming.forEach((match) => list.append(resultRow(match)));
      root.append(list);
    }
    root.append(h("h3", { class: "subhead" }, "最近赛果"));
    if ((fixtures.results || []).length) {
      const list = h("div", { class: "result-list" });
      fixtures.results.forEach((match) => list.append(resultRow(match)));
      root.append(list);
    } else {
      root.append(h("p", { class: "empty" }, "还没有已结束的比赛。"));
    }
  }

  function matchHero(match) {
    const hero = h("article", { class: "hero" });
    hero.append(h("p", { class: "kicker" }, competitionLine(match)));
    hero.append(h("p", { class: "time" }, sideText(match) + " · " + bj(match.kickoff, true)));
    const board = h("div", { class: "scoreboard" });
    board.append(teamBlock(match.home, match.homeEn, ""));
    const middle = h("div", { class: "vs" });
    if (match.score) {
      middle.append(h("div", { class: "score" }, match.score.home + " - " + match.score.away));
      middle.append(h("div", { class: "fine" }, match.statusText || ""));
    } else {
      middle.append(h("div", null, "对"));
      middle.append(h("div", { class: "fine" }, match.statusText || "未开始"));
    }
    board.append(middle);
    board.append(teamBlock(match.away, match.awayEn, "away"));
    hero.append(board);
    if (match.venue) {
      const venue = match.venueEn && match.venueEn !== match.venue ? match.venue + "（" + match.venueEn + "）" : match.venue;
      hero.append(h("p", { class: "time" }, venue));
    }
    return hero;
  }

  function resultRow(match) {
    const row = h("article", { class: "result" });
    const top = h("div", { class: "result-top" });
    top.append(h("span", { class: "kicker" }, competitionLine(match)));
    top.append(h("span", { class: "time" }, bj(match.kickoff, true)));
    row.append(top);
    const main = h("div", { class: "result-main" });
    const names = [match.home, match.away].filter(Boolean).join(" 对 ");
    main.append(h("strong", null, names));
    main.append(h("span", { class: "score-num" }, scoreText(match)));
    row.append(main);
    const extra = [sideText(match), match.statusText, match.venue].filter(Boolean).join(" · ");
    if (extra) row.append(h("p", { class: "fine" }, extra));
    return row;
  }

  function competitionLine(match) {
    const parts = [match.competition || "赛事"];
    if (match.round) parts.push(match.round);
    if (match.competitionRaw && match.competitionRaw !== match.competition) parts.push(match.competitionRaw);
    return parts.join(" · ");
  }

  function sideText(match) {
    if (match.arsenalSide === "home") return "阿森纳主场";
    if (match.arsenalSide === "away") return "阿森纳客场";
    return "";
  }

  function scoreText(match) {
    if (!match.score) return match.statusText || "";
    return match.score.home + " - " + match.score.away;
  }

  function teamBlock(name, en, className) {
    const block = h("div", { class: className ? "team " + className : "team" });
    block.append(h("strong", null, name || "待定"));
    if (en) block.append(h("span", { class: "en" }, en));
    return block;
  }

  function renderPodcasts() {
    const root = document.getElementById("podcasts-root");
    const podcasts = (state.data && state.data.podcasts) || { items: [] };
    root.textContent = "";
    if (podcasts.message) root.append(h("p", { class: "fine" }, podcasts.message));
    const items = podcasts.items || [];
    if (!items.length) {
      root.append(h("p", { class: "empty" }, podcasts.message || "暂时没有播客。"));
      return;
    }
    ["episode", "extra", "women"].forEach((kind) => {
      const group = items.filter((item) => item.kind === kind);
      if (!group.length) return;
      root.append(h("h3", { class: "subhead" }, group[0].show || kind));
      const list = h("div", { class: "pod-list" });
      group.forEach((item) => list.append(podcastRow(item)));
      root.append(list);
    });
  }

  function podcastRow(item) {
    const row = h("article", { class: "pod" });
    const title = h("h3");
    title.append(externalLink(item.url, item.title));
    row.append(title);
    const bits = ["发布时间 " + bj(item.publishedAt, true)];
    if (item.duration) bits.push(item.duration);
    row.append(h("p", { class: "time" }, bits.join(" · ")));
    if (item.summary) row.append(h("p", { class: "summary" }, item.summary));
    const link = externalLink(item.url, "去官方页面收听");
    link.className = "more";
    row.append(link);
    return row;
  }

  function renderStatus() {
    const root = document.getElementById("status-root");
    const status = (state.data && state.data.status) || {};
    root.textContent = "";
    const card = h("div", { class: "about-card" });
    card.append(h("h3", null, "最近一次生成"));
    card.append(kv("生成时间", status.generatedAt, "页面打包数据的时间，北京时间"));
    ["news", "fixtures", "podcasts"].forEach((key) => {
      const block = status[key];
      if (!block) return;
      const section = h("div", { class: "status-block" });
      section.append(h("h3", null, block.label || key));
      section.append(kv("抓取时间", block.fetchedAt, block.stale ? "最近一次成功，不是刚才失败的那次" : "最近一次成功取到数据"));
      section.append(kv("来源时间", block.sourceUpdatedAt, block.sourceTimeLabel || ""));
      if (block.message) section.append(h("p", null, block.message));
      if (block.scheduleNote) section.append(h("p", null, block.scheduleNote));
      (block.sources || []).forEach((source) => {
        const line = source.name + "：" + (source.ok ? "这次已更新" : source.keptCache ? "仍是上次缓存" : "暂时没有条目");
        section.append(h("p", { class: "fine" }, line + (source.error ? "（" + source.error + "）" : "")));
      });
      card.append(section);
    });
    if (typeof status.requestsToday === "number") {
      card.append(
        h(
          "p",
          { class: "fine" },
          "今天已经向赛程接口发出 " + status.requestsToday + " 次请求，脚本自己的保护上限是 " + status.requestCap + "，免费套餐平台上限是每天 " + (status.providerDailyCap || 100) + " 次、每分钟 10 次。"
        )
      );
    }
    root.append(card);
  }

  function kv(label, iso, hint) {
    const row = h("div", { class: "kv" });
    row.append(h("div", null, label));
    const value = h("div");
    value.append(h("div", null, iso ? bj(iso, true) : "还没有"));
    if (hint) value.append(h("small", null, hint));
    row.append(value);
    return row;
  }

  function bj(iso) {
    if (!iso) return "时间未知";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "时间未知";
    return fullTime.format(date) + " 北京时间";
  }

  function externalLink(url, text) {
    const safe = safeUrl(url);
    if (!safe) return h("span", null, text || "");
    return h("a", { href: safe, target: "_blank", rel: "noopener noreferrer" }, text || safe);
  }

  function safeUrl(url) {
    try {
      const parsed = new URL(url);
      if (parsed.protocol === "https:" || parsed.protocol === "http:") return parsed.href;
    } catch (error) {
      return "";
    }
    return "";
  }

  function loadFavs() {
    try {
      const raw = JSON.parse(localStorage.getItem(FAV_KEY) || "[]");
      if (!Array.isArray(raw)) return new Set();
      return new Set(raw.filter((item) => typeof item === "string"));
    } catch (error) {
      return new Set();
    }
  }

  function saveFavs(favs) {
    try {
      localStorage.setItem(FAV_KEY, JSON.stringify(Array.from(favs)));
      return true;
    } catch (error) {
      return false;
    }
  }

  function h(tag, props, text) {
    const node = document.createElement(tag);
    if (props) {
      Object.keys(props).forEach((key) => {
        const value = props[key];
        if (value == null || value === false) return;
        if (key === "class") node.className = value;
        else node.setAttribute(key, String(value));
      });
    }
    if (text != null) node.textContent = text;
    return node;
  }
})();
