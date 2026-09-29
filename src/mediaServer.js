// Instagram 은 이미지를 URL 로만 가져가므로 다운로드한 사진을 임시로 공개 서빙한다.
// (텔레그램 파일 URL 에는 봇 토큰이 들어 있어 Meta 에 넘기면 안 된다.)
const fs = require('fs');
const http = require('http');
const path = require('path');

const FILE_PATTERN = /^[a-f0-9-]{36}\.jpg$/;

function startMediaServer(dir, port) {
  fs.mkdirSync(dir, { recursive: true });
  const server = http.createServer((req, res) => {
    const name = path.basename(req.url.split('?')[0]);
    const file = path.join(dir, name);
    if (req.method !== 'GET' || !req.url.startsWith('/media/') || !FILE_PATTERN.test(name) || !fs.existsSync(file)) {
      res.writeHead(404).end();
      return;
    }
    res.writeHead(200, { 'Content-Type': 'image/jpeg' });
    fs.createReadStream(file).pipe(res);
  });
  server.listen(port);
  return server;
}

module.exports = { startMediaServer };
