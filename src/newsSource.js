const { fetchLatestNews: fetchRssNews } = require('./newsFeed');
const { fetchLatestNaverNews } = require('./naverNews');
const { fetchLatestGoogleNews } = require('./googleNewsSearch');

function parseKeywords(value) {
  return (value || '')
    .split(',')
    .map((k) => k.trim())
    .filter(Boolean);
}

function buildNewsSource(env = process.env) {
  const source = (env.NEWS_SOURCE || 'google').toLowerCase();

  if (source === 'naver') {
    const clientId = env.NAVER_CLIENT_ID;
    const clientSecret = env.NAVER_CLIENT_SECRET;
    const keywords = parseKeywords(env.NAVER_NEWS_KEYWORDS);

    if (!clientId || !clientSecret) {
      throw new Error('NAVER_CLIENT_ID / NAVER_CLIENT_SECRET must be set when NEWS_SOURCE=naver.');
    }
    if (keywords.length === 0) {
      throw new Error('NAVER_NEWS_KEYWORDS must be set when NEWS_SOURCE=naver (comma-separated).');
    }

    return {
      description: `네이버 뉴스 검색 (키워드: ${keywords.join(', ')})`,
      fetchLatestNews: (limit) => fetchLatestNaverNews(keywords, clientId, clientSecret, limit),
    };
  }

  if (source === 'google') {
    const keywords = parseKeywords(env.NEWS_KEYWORDS);
    if (keywords.length === 0) {
      throw new Error('NEWS_KEYWORDS must be set when NEWS_SOURCE=google (comma-separated).');
    }

    return {
      description: `구글 뉴스 검색 (키워드: ${keywords.join(', ')})`,
      fetchLatestNews: (limit) => fetchLatestGoogleNews(keywords, limit),
    };
  }

  const feedUrl = env.RSS_FEED_URL || 'https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko';
  return {
    description: `RSS 피드 (${feedUrl})`,
    fetchLatestNews: (limit) => fetchRssNews(feedUrl, limit),
  };
}

module.exports = { buildNewsSource };
