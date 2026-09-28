const API_URL = 'https://openapi.naver.com/v1/search/news.json';

function stripHtml(text) {
  return text
    .replace(/<\/?b>/g, '')
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&#39;/g, "'");
}

async function searchNews(keyword, clientId, clientSecret, display = 10) {
  const url = `${API_URL}?query=${encodeURIComponent(keyword)}&display=${display}&sort=date`;
  const res = await fetch(url, {
    headers: {
      'X-Naver-Client-Id': clientId,
      'X-Naver-Client-Secret': clientSecret,
    },
  });

  if (!res.ok) {
    throw new Error(`Naver News API error: ${res.status} ${await res.text()}`);
  }

  const data = await res.json();
  return (data.items || []).map((item) => ({
    id: item.link,
    title: stripHtml(item.title),
    link: item.link,
    pubDate: item.pubDate,
    keyword,
  }));
}

async function fetchLatestNaverNews(keywords, clientId, clientSecret, limit = 10) {
  const results = await Promise.all(
    keywords.map((keyword) => searchNews(keyword, clientId, clientSecret, limit))
  );

  const merged = results.flat();
  const seenLinks = new Set();
  const deduped = merged.filter((item) => {
    if (seenLinks.has(item.id)) return false;
    seenLinks.add(item.id);
    return true;
  });

  deduped.sort((a, b) => new Date(b.pubDate) - new Date(a.pubDate));
  return deduped.slice(0, limit);
}

module.exports = { fetchLatestNaverNews };
