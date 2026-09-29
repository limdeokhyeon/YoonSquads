const { fetchLatestNews: fetchRssNews } = require('./newsFeed');

function buildSearchFeedUrl(keyword) {
  return `https://news.google.com/rss/search?q=${encodeURIComponent(keyword)}&hl=ko&gl=KR&ceid=KR:ko`;
}

async function fetchLatestGoogleNews(keywords, limit = 10) {
  const results = await Promise.all(
    keywords.map(async (keyword) => {
      const items = await fetchRssNews(buildSearchFeedUrl(keyword), limit);
      return items.map((item) => ({ ...item, keyword }));
    })
  );

  const merged = results.flat();
  const seenIds = new Set();
  const deduped = merged.filter((item) => {
    if (seenIds.has(item.id)) return false;
    seenIds.add(item.id);
    return true;
  });

  deduped.sort((a, b) => new Date(b.pubDate) - new Date(a.pubDate));
  return deduped.slice(0, limit);
}

module.exports = { fetchLatestGoogleNews };
