const Parser = require('rss-parser');
const { getProxyAgent } = require('./proxyAgent');

const proxyAgent = getProxyAgent();
const parser = new Parser(proxyAgent ? { requestOptions: { agent: proxyAgent } } : {});

async function fetchLatestNews(feedUrl, limit = 10) {
  const feed = await parser.parseURL(feedUrl);
  return (feed.items || [])
    .slice(0, limit)
    .map((item) => ({
      id: item.guid || item.link,
      title: item.title,
      link: item.link,
      pubDate: item.pubDate,
    }));
}

module.exports = { fetchLatestNews };
