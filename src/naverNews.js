// NAVER_API_PROVIDER=developers (기본): developers.naver.com 에서 발급한 키
// NAVER_API_PROVIDER=ncp: 네이버 클라우드 플랫폼 NAVER API HUB 에서 발급한 키
const PROVIDERS = {
  developers: {
    url: 'https://openapi.naver.com/v1/search/news.json',
    headers: (id, secret) => ({ 'X-Naver-Client-Id': id, 'X-Naver-Client-Secret': secret }),
  },
  ncp: {
    url: 'https://naverapihub.apigw.ntruss.com/search/v1/news',
    headers: (id, secret) => ({ 'X-NCP-APIGW-API-KEY-ID': id, 'X-NCP-APIGW-API-KEY': secret }),
  },
};

function getProvider() {
  const name = (process.env.NAVER_API_PROVIDER || 'developers').toLowerCase();
  const provider = PROVIDERS[name];
  if (!provider) {
    throw new Error(`NAVER_API_PROVIDER must be one of: ${Object.keys(PROVIDERS).join(', ')}`);
  }
  return provider;
}

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
  const provider = getProvider();
  const url = `${provider.url}?query=${encodeURIComponent(keyword)}&display=${display}&sort=date`;
  const res = await fetch(url, { headers: provider.headers(clientId, clientSecret) });

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
