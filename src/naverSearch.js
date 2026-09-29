const BASE_URL = 'https://openapi.naver.com/v1/search';

async function search(type, query, display = 5) {
  const clientId = process.env.NAVER_CLIENT_ID;
  const clientSecret = process.env.NAVER_CLIENT_SECRET;
  if (!clientId || !clientSecret) {
    throw new Error('NAVER_CLIENT_ID / NAVER_CLIENT_SECRET is not set. Copy .env.example to .env and fill it in.');
  }

  const url = `${BASE_URL}/${type}.json?query=${encodeURIComponent(query)}&display=${display}`;
  const res = await fetch(url, {
    headers: {
      'X-Naver-Client-Id': clientId,
      'X-Naver-Client-Secret': clientSecret,
    },
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Naver API request failed (${res.status}): ${body}`);
  }

  return res.json();
}

function stripTags(text) {
  return text.replace(/<[^>]*>/g, '');
}

module.exports = { search, stripTags };
