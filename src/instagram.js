// Instagram API with Instagram Login (비즈니스/크리에이터 계정) 사진 게시
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function createInstagramClient({ userId, accessToken, version = 'v21.0' }) {
  const base = `https://graph.instagram.com/${version}`;

  async function request(method, path, params = {}) {
    const query = new URLSearchParams({ ...params, access_token: accessToken });
    const res = await fetch(
      method === 'GET' ? `${base}/${path}?${query}` : `${base}/${path}`,
      method === 'GET'
        ? undefined
        : { method, headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: query }
    );
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.error) {
      throw new Error(data.error?.message || `Instagram API ${res.status}`);
    }
    return data;
  }

  async function waitUntilReady(creationId, attempts = 10) {
    for (let i = 0; i < attempts; i += 1) {
      const { status_code: status } = await request('GET', creationId, { fields: 'status_code' });
      if (status === 'FINISHED') return;
      if (status === 'ERROR' || status === 'EXPIRED') {
        throw new Error(`미디어 처리 실패: ${status}`);
      }
      await sleep(2000);
    }
    throw new Error('미디어 처리 시간이 초과되었습니다.');
  }

  // 공개 접근 가능한 JPEG URL 을 게시하고 permalink 를 반환한다.
  async function publishPhoto(imageUrl, caption = '') {
    const container = await request('POST', `${userId}/media`, { image_url: imageUrl, caption });
    await waitUntilReady(container.id);
    const published = await request('POST', `${userId}/media_publish`, { creation_id: container.id });
    const { permalink } = await request('GET', published.id, { fields: 'permalink' });
    return permalink || published.id;
  }

  return { publishPhoto };
}

module.exports = { createInstagramClient };
