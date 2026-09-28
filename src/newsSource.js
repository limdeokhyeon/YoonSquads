const { fetchLatestNews: fetchRssNews } = require('./newsFeed');
const { fetchLatestNaverNews } = require('./naverNews');

function buildNewsSource(env = process.env) {
  const source = (env.NEWS_SOURCE || 'rss').toLowerCase();

  if (source === 'naver') {
    const clientId = env.NAVER_CLIENT_ID;
    const clientSecret = env.NAVER_CLIENT_SECRET;
    const keywords = (env.NAVER_NEWS_KEYWORDS || '')
      .split(',')
      .map((k) => k.trim())
      .filter(Boolean);

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

  const feedUrl = env.RSS_FEED_URL || 'https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko';
  return {
    description: `RSS 피드 (${feedUrl})`,
    fetchLatestNews: (limit) => fetchRssNews(feedUrl, limit),
  };
}

module.exports = { buildNewsSource };
