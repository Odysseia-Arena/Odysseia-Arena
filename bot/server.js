require('dotenv').config();
const http = require('http');

// 注册斜杠命令
require('./src/register-commands.js');

// 启动机器人
require('./src/bot.js');

// 创建一个简单的HTTP服务器以满足部署要求
const server = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'text/plain' });
  res.end('Discord Bot is active and running!');
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`服务器正在端口 ${PORT} 上运行。`);
});