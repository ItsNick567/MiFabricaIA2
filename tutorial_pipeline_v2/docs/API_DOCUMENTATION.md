# API Documentation

## Dev.to

- Base URL: `https://dev.to/api`
- Auth header: `api-key: <DEVTO_API_KEY>`
- Publish endpoint: `POST /articles`
- Used by: `publishers/devto_publisher.py`

## Hashnode

- Base URL: `https://gql.hashnode.com`
- Auth header: `Authorization: <HASHNODE_API_KEY>`
- Publish operation: GraphQL `publishPost`
- Required variable: `HASHNODE_PUBLICATION_ID`
- Used by: `publishers/hashnode_publisher.py`

## Telegram Bot API

- Base URL: `https://api.telegram.org/bot<TOKEN>`
- Endpoint used: `POST /sendMessage`
- Required vars: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`
- Used by: `publishers/telegram_publisher.py`

## Blogger API v3

- Base URL: `https://www.googleapis.com/blogger/v3`
- Auth header: `Authorization: Bearer <BLOGGER_ACCESS_TOKEN>`
- Publish endpoint: `POST /blogs/{blogId}/posts/`
- Token refresh endpoint: `POST https://oauth2.googleapis.com/token`
- Required vars: `BLOGGER_BLOG_ID`, plus either:
  - `BLOGGER_ACCESS_TOKEN` (manual refresh), or
  - `BLOGGER_CLIENT_ID` + `BLOGGER_CLIENT_SECRET` + `BLOGGER_REFRESH_TOKEN` (auto-refresh)
- Used by: `publishers/blogger_publisher.py`

## Trends sources (scraping/data)

- Dev.to: `GET https://dev.to/api/articles?top=7&per_page=50`
- Hashnode: `GET https://hashnode.com/trending` (HTML parsing)
- GitHub: `GET https://api.github.com/search/repositories`
- Reddit: `GET https://www.reddit.com/r/programming/hot.json`

All source clients are implemented in `core/trend_analyzer.py`.
