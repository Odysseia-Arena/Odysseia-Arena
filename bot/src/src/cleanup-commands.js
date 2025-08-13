require('dotenv').config();
const { REST, Routes } = require('discord.js');

const { TOKEN, CLIENT_ID, GUILD_ID } = process.env;

if (!TOKEN || !CLIENT_ID) {
  console.error('错误：请确保 .env 文件中已配置 TOKEN 和 CLIENT_ID。');
  process.exit(1);
}

const rest = new REST({ version: '10' }).setToken(TOKEN);

(async () => {
  console.log('正在开始清除应用的斜杠 (/) 命令...');

  try {
    // 清除指定服务器的命令
    if (GUILD_ID) {
      console.log(`正在清除服务器 (ID: ${GUILD_ID}) 的命令...`);
      await rest.put(
        Routes.applicationGuildCommands(CLIENT_ID, GUILD_ID),
        { body: [] },
      );
      console.log('已成功清除服务器的命令。');
    } else {
      console.log('未提供 GUILD_ID，跳过清除服务器命令的步骤。');
    }

    // 清除全局命令
    console.log('正在清除应用的全局命令...');
    await rest.put(
      Routes.applicationCommands(CLIENT_ID),
      { body: [] },
    );
    console.log('已成功清除应用的全局命令。');
    console.log('注意：全局命令的更新可能需要长达一小时才能在所有服务器上生效。');

    console.log('\n所有命令清除任务已完成。');

  } catch (error) {
    console.error('清除命令时发生错误:', error);
  }
})();