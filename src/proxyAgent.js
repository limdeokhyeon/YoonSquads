const { HttpsProxyAgent } = require('https-proxy-agent');

function getProxyAgent() {
  const proxyUrl = process.env.HTTPS_PROXY || process.env.https_proxy;
  return proxyUrl ? new HttpsProxyAgent(proxyUrl) : undefined;
}

module.exports = { getProxyAgent };
