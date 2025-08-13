require('dotenv').config();
const { REST, Routes, ApplicationCommandOptionType } = require('discord.js');

const commands = [
  {
    name: 'battle',
    description: '开始一场新的模型对战',
    // 默认不授予任何成员使用权限（在“集成 -> 你的机器人 -> 命令权限”里再授予指定用户/角色）
    // 禁止私信里使用
    dm_permission: false,
  },
  {
    name: 'leaderboard',
    description: '查看模型排行榜',
    dm_permission: false,
  },
  {
    name: 'battleinfo',
    description: '查看指定对战详情',
    options: [
      {
        name: 'battle_id',
        description: '对战ID',
        type: ApplicationCommandOptionType.String,
        required: true,
      }
    ],
    dm_permission: false,
  },
  {
    name: 'health',
    description: '检查后端健康状态',
    dm_permission: false,
  }
];

const rest = new REST({ version: '10' }).setToken(process.env.TOKEN);

(async () => {
  try {
    console.log('开始刷新斜杠 (/) 命令。');

    await rest.put(
      Routes.applicationGuildCommands(
        process.env.CLIENT_ID,
        process.env.GUILD_ID
      ),
      { body: commands }
    );

    console.log('成功重新加载斜杠 (/) 命令。');
  } catch (error) {
    console.error(error);
  }
})();