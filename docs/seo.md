# SEO Optimization Guide

How to make your llmwiki site discoverable by search engines and AI agents.

## What the build already generates

Every `llmwiki build` run emits these SEO artifacts automatically — no
configuration required.

### Meta tags on every page

```html
<meta property="og:type" content="article" />
<meta property="og:title" content="Session Title" />
<meta property="og:description" content="First 160 chars of the summary..." />
<meta property="article:published_time" content="2026-04-08T..." />
<link rel="canonical" href="https://yoursite.example/sessions/project/slug.html" />
```

Open Graph tags mean links shared on Twitter/LinkedIn/Slack render with a
title, description, and (when you add one) an image preview.

The `<link rel="canonical">` prevents duplicate-indexing when the same
page is reachable under multiple URLs (e.g. with and without a trailing
slash).

### Schema.org microdata

Every session page includes `itemscope` / `itemtype="https://schema.org/Article"`
with `headline`, `datePublished`, and `inLanguage` properties so Google can
render rich results.

### sitemap.xml

A standard XML sitemap is generated at `site/sitemap.xml` with
`<lastmod>` timestamps and priority hints:

| Page type | Priority |
|---|---|
| Home (`index.html`) | 1.0 |
| Project pages | 0.8 |
| Session pages | 0.6 |
| Changelog | 0.4 |

Submit this URL in Google Search Console (see below) and any other
webmaster tool.

### robots.txt

Generated at `site/robots.txt`:

```
User-agent: *
Allow: /

Sitemap: https://yoursite.example/sitemap.xml

# AI agent discovery (llmstxt.org spec)
# See: https://llmstxt.org
LLMsTxt: /llms.txt
```

The `LLMsTxt` directive follows the [llmstxt.org](https://llmstxt.org)
convention so AI agents (Claude, ChatGPT, Perplexity) know where to find
the machine-readable index of your wiki.

### AI-consumable exports

These are not strictly SEO but help AI crawlers index your content:

- `llms.txt` — short plain-text index per the llmstxt.org spec
- `llms-full.txt` — full wiki dump, capped at 5 MB
- `graph.jsonld` — Schema.org JSON-LD knowledge graph
- Nested `sources/<project>/<stem>.md` next to every session HTML page

## Custom domain setup

### GitHub Pages

1. Go to your repo **Settings > Pages**
2. Under **Custom domain**, enter your domain (e.g. `wiki.example.com`)
3. Add a `CNAME` DNS record pointing to `<username>.github.io`
4. Wait for DNS propagation (up to 24 hours)
5. Check **Enforce HTTPS** once the certificate provisions

GitHub Pages auto-provisions a Let's Encrypt certificate. The canonical
URLs in `sitemap.xml` and `<link rel="canonical">` will use whatever
base URL you configure in `llmwiki.toml`:

```toml
[site]
base_url = "https://wiki.example.com"
```

### GitLab Pages

See [`deploy/gitlab-pages.md`](deploy/gitlab-pages.md) for the full
`.gitlab-ci.yml` setup. Custom domain configuration is under
**Settings > Pages > New Domain**.

## Google Search Console setup

1. Go to [search.google.com/search-console](https://search.google.com/search-console)
2. Add your property (URL prefix method is simplest)
3. Verify ownership:
   - **GitHub Pages**: use the HTML tag method — add a `<meta name="google-site-verification">` tag via `llmwiki.toml`:
     ```toml
     [site]
     head_extra = '<meta name="google-site-verification" content="your-code-here" />'
     ```
   - **Self-hosted**: upload the verification HTML file to `site/` before building
4. Submit your sitemap: **Sitemaps > Add a new sitemap** > enter `sitemap.xml`
5. Request indexing of your home page under **URL Inspection > Request Indexing**

### What to check after indexing starts

- **Coverage report**: look for "Excluded" pages — these are usually
  pagination artifacts or duplicate URLs. llmwiki's canonical tags should
  prevent most issues.
- **Core Web Vitals**: llmwiki's static HTML with no JS framework
  typically scores 95+ on Lighthouse. If you see regressions, check
  whether a large `search-index.json` is blocking first paint.
- **Sitemaps**: confirm all submitted URLs are "Discovered" and trending
  toward "Indexed".

## Bing Webmaster Tools

1. Go to [bing.com/webmasters](https://www.bing.com/webmasters)
2. Import from Google Search Console (one click) or verify separately
3. Submit `sitemap.xml` under **Sitemaps**

Bing indexes smaller sites less aggressively — expect 2-4 weeks for
full coverage.

## Tips for better ranking

1. **Write good session summaries.** The first 160 characters of each
   session summary become the `og:description`. Make them descriptive.
2. **Use meaningful project names.** Project slugs appear in URLs
   (`/sessions/my-project/`). Descriptive names help both humans and
   search engines.
3. **Keep the changelog current.** The changelog page is a high-value
   landing page for people searching for your tool's version history.
4. **Link from your GitHub README.** A link from a high-authority GitHub
   repo to your Pages site is the single best SEO signal you can send.
5. **Add the site to your GitHub repo description.** The "Website" field
   in repo settings adds a nofollow link, but it drives click-through.
