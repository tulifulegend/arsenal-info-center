# 阿森纳足球信息中心

给想看阿森纳新闻、赛程和播客的人用。用浏览器打开就行，不用写代码，也不用登录。

网站是公开的。任何人拿到链接都能看。不要把密钥、密码发到这个仓库、Issues 或网页上。

## 网站地址

https://tulifulegend.github.io/arsenal-info-center/

这个地址要等下面几步做完才能打开。

## 你需要做的事

这些步骤只有仓库管理员能完成，程序代替不了点击。

1. 合并这个更新（Pull Request）到 `main`。
2. 添加赛程密钥。
   - 打开仓库的 **Settings → Secrets and variables → Actions → New repository secret**。
   - 名字必须完全是 `API_FOOTBALL_KEY`。
   - 内容是你自己在 [API-Football](https://www.api-football.com/) 免费计划里申请的密钥。
   - 没填密钥时，新闻和播客仍会更新，赛程页面会说明暂时不可用。
3. 打开 GitHub Pages。
   - **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**。
   - 这一步现在还没开。仓库里看不到现成的 Pages 站点，需要你亲手选一次。
4. 到 **Actions**，选 **Update site data and deploy**，点 **Run workflow**。想马上拉赛程，可以勾上「立即拉取赛程」。不勾也会按计划以后再拉。
5. 等它变成绿色后，用浏览器打开上面的网址。如果你人在中国大陆，`github.io` 有时打不开，换一个网络再试。打不开通常是访问 GitHub Pages 的网络问题，不是网页把你拦下了。

## 打开之后能做什么

- **新闻**：来自 Arseblog 和卫报阿森纳订阅源。可以搜索、按来源筛选、收藏。收藏存在你自己的浏览器里，换电脑就没有了。
- **赛程**：男足一线队的下一场和最近赛果，写明赛事，时间是北京时间。比分是最近一次更新时的结果，不是实时比分，也不是直播。
- **播客**：Arsecast 正集、Extra，以及源里如果有的女足节目。点进去是官方页面。不含 Patreon 付费内容。
- **说明**：能看到每块数据的抓取时间和来源时间。某次更新失败时，页面会写明仍在显示上次成功的缓存，不会用失败结果把好数据盖掉。

文章标题保持原文。页面只放标题、短摘要和链接，不转载全文。

## 什么会自动更新

自动更新只发生在上面的网站上。

- 工作流大约每 30 分钟跑一次，新闻和播客每次都会尝试更新。GitHub 的定时任务有时会晚几分钟到几十分钟，这是正常的。
- 赛程平时大约每 8 小时拉一次（一天大约 2 到 4 次）。如果缓存里的比赛临近（开球前约 2 小时到开球后约 3 小时），会大约每 30 分钟再看一次。
- 脚本自己把赛程请求限制在每天 80 次以内，低于免费套餐的每天 100 次、每分钟 10 次。到了保护线就暂停赛程请求，并在页面上说明。
- 每次更新发布的是 GitHub Actions 构建出来的网页，不会为了数据每半小时往 Git 历史里塞一次提交。Actions 缓存负责记住上次成功的数据。仓库里的 `data/*.json` 是初始种子：缓存丢了、网络又失败时，就退回这份种子，并标明那是较早的数据。

## 下载快照

网页底部有「下载当前快照」。那是一个单独的 HTML 文件，里面已经装进了下载当时的新闻、赛程和播客。

- 用浏览器打开这个文件就能看。
- 它不会继续自动更新。
- 它不会在你的电脑上请求 Arseblog、卫报、播客或赛程接口。
- 不要把仓库里的 `index.html` 用 `file://` 直接打开，指望它自己联网更新。那种打开方式连旁边的数据文件都读不到。

要看持续变新的内容，请一直用线上网站。

## 数据来源和使用界限

- Arseblog 新闻：<https://arseblog.com/feed/>
- 卫报足球 · 阿森纳：<https://www.theguardian.com/football/arsenal/rss>
- Arsecast：<https://rss.acast.com/arseblog>
- 赛程：API-Football 免费套餐，球队是男足一线队。密钥只放在 GitHub Actions secret `API_FOOTBALL_KEY`。

卫报内容只使用标题、短摘要和链接，供个人、非商业查看。不抓网页正文，不转载付费墙后面的全文。

播客源很大（一千多期）。生成的 JSON 只保留最近少量正集、Extra 和女足节目，不收录 Patreon / 付费条目，也不把整份源提交进仓库。

football-data.org 不是这一版的数据源。BBC 和泰晤士报也不使用。没有公共 CORS 代理，浏览器也不会自己去请求这些第三方接口。

如果免费接口没有覆盖当前赛季或杯赛，页面会直接写明缺了什么。脚本不会改去猜，也不会升级到付费计划。

原创代码使用 MIT 许可，见 `LICENSE`。抓来的标题和摘要仍属于原作者和原网站，不因 MIT 许可而改变。详见 `NOTICE`。

## 可选：在自己电脑上看一眼

需要已安装 Python 3.11 或更新版本。没有密钥时，赛程显示不可用是正常的。

```bash
python3 -m unittest tests.test_update -v
python3 scripts/update_data.py
python3 scripts/verify_data.py data
python3 scripts/build_dist.py
python3 -m http.server 8765 --directory dist
```

然后在浏览器打开 <http://127.0.0.1:8765/> 。

本地预览不会带上赛程密钥。赛程要等密钥放进 GitHub Actions 的 Secret 之后，由线上工作流去拉。不要把密钥写进任何文件。
