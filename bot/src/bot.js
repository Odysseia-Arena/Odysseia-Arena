require('dotenv').config();
const { Client, IntentsBitField, ActionRowBuilder, ButtonBuilder, ButtonStyle, EmbedBuilder } = require('discord.js');
const axios = require('axios');
const crypto = require('crypto');

const client = new Client({
  intents: [
    IntentsBitField.Flags.Guilds,
    IntentsBitField.Flags.GuildMembers,
    IntentsBitField.Flags.GuildMessages,
    IntentsBitField.Flags.MessageContent,
  ],
});

const API_URL = process.env.API_URL;

// 频道白名单，逗号分隔，留空表示不限制
const RAW_ALLOWED = process.env.ALLOWED_CHANNEL_IDS || '';
const ALLOWED_CHANNEL_IDS = new Set(
  RAW_ALLOWED.split(',').map(s => s.trim()).filter(Boolean)
);
const isChannelAllowed = (channelId) =>
  ALLOWED_CHANNEL_IDS.size === 0 || ALLOWED_CHANNEL_IDS.has(channelId);
const allowedMentionList = () =>
  ALLOWED_CHANNEL_IDS.size === 0
    ? ''
    : Array.from(ALLOWED_CHANNEL_IDS).map(id => `<#${id}>`).join('、');

// 用户/角色白名单（仅这些用户/角色可用命令/投票）；留空表示不限制
const RAW_USER_IDS = process.env.ALLOWED_USER_IDS || '';
const RAW_ROLE_IDS = process.env.ALLOWED_ROLE_IDS || '';
const ALLOWED_USER_IDS = new Set(RAW_USER_IDS.split(',').map(s => s.trim()).filter(Boolean));
const ALLOWED_ROLE_IDS = new Set(RAW_ROLE_IDS.split(',').map(s => s.trim()).filter(Boolean));

function isMemberAllowed(interaction) {
  // 不配置即不限制
  if (ALLOWED_USER_IDS.size === 0 && ALLOWED_ROLE_IDS.size === 0) return true;
  // 指定用户直通
  if (ALLOWED_USER_IDS.has(interaction.user.id)) return true;
  // 检查成员角色
  const member = interaction.member;
  if (!member || !member.roles) return false;
  const hasRole = typeof member.roles.cache !== 'undefined'
    ? Array.from(ALLOWED_ROLE_IDS).some(rid => member.roles.cache.has(rid))
    : Array.from(ALLOWED_ROLE_IDS).some(rid => member.roles?.includes?.(rid));
  return hasRole;
}

function allowedUserRoleMentions() {
  const users = Array.from(ALLOWED_USER_IDS).map(id => `<@${id}>`);
  const roles = Array.from(ALLOWED_ROLE_IDS).map(id => `<@&${id}>`);
  return [...users, ...roles].join('、');
}

// 用于存储进行中的对战信息
const activeBattles = new Map();

 // --- 新增：格式化模型名称，添加专属Emoji ---
function formatModelName(modelName) {
  if (!modelName) return 'N/A';
  const lowerCaseName = modelName.toLowerCase();
  if (lowerCaseName.includes('gemini') || lowerCaseName.includes('gemma')) return `<:Gemini:1397074784520765522> ${modelName}`;
  if (lowerCaseName.includes('claude')) return `<:Claude:1300123863329406998> ${modelName}`;
  if (lowerCaseName.includes('gpt')) return `<:Gpt_purple:1398207128451416084> ${modelName}`;
  if (lowerCaseName.includes('grok')) return `<:Grok:1397075985706385561> ${modelName}`;
  if (lowerCaseName.includes('kimi')) return `<:Kimi:1397069865239707841> ${modelName}`;
  if (lowerCaseName.includes('deepseek')) return `<:Deepseek:1397067318902788106> ${modelName}`;
  if (lowerCaseName.includes('glm')) return `<:GLM:1399344285870063647> ${modelName}`;
  if (lowerCaseName.includes('qwen')) return `<:Qwen:1397067824287060068> ${modelName}`;
  if (lowerCaseName.includes('anon')) return `<:__:1331570533078274061> ${modelName}`;
  if (lowerCaseName.includes('doubao')) return `<:doubao:1409041294218756159> ${modelName}`;
  if (lowerCaseName.includes('step')) return `<:step:1409011619924803624> ${modelName}`;
  if (lowerCaseName.includes('mistral')) return `<:Mistral:1409599047353897002> ${modelName}`;
  if (lowerCaseName.includes('llama')) return `<:Llama:1409598678607462520> ${modelName}`;
  if (lowerCaseName.includes('ernie')) return `<:ERNIE:1409597501128052837> ${modelName}`;
  if (lowerCaseName.includes('command')) return `<:Cohere:1310420456385544263> ${modelName}`;
  return modelName;
}

// 统一安全截断 Embed 描述，保证 <= 4096 且补齐未闭合的代码块
function safeTruncateEmbed(text) {
  const MAX = 4096;
  if (text == null) return '';
  let s = String(text);
  if (s.length <= MAX) return s;
  // 先截断并添加省略号
  s = s.slice(0, MAX - 3) + '...';
  // 如有未闭合的 ``` 代码块，补齐并确保总长度不超限
  const fences = (s.match(/```/g) || []).length;
  if (fences % 2 !== 0) {
    s = s.slice(0, MAX - 7) + '...\n```';
  }
  // 再保险：硬性裁剪到上限
  if (s.length > MAX) s = s.slice(0, MAX);
  return s;
}

client.on('ready', () => {
  console.log(`✅ 机器人 ${client.user.tag} 已上线并准备就绪`);
});

client.on('interactionCreate', async (interaction) => {
  if (interaction.isChatInputCommand()) {
    handleCommand(interaction);
  } else if (interaction.isButton()) {
    handleButton(interaction);
  }
});

async function sendPaginatedLeaderboard(interaction, leaderboard, title, nextUpdateTime) {
  const ITEMS_PER_PAGE = 10;
  let currentPage = 0;
  const totalPages = Math.ceil(leaderboard.length / ITEMS_PER_PAGE);

  const generateEmbed = (page) => {
    const start = page * ITEMS_PER_PAGE;
    const end = start + ITEMS_PER_PAGE;
    const pagedItems = leaderboard.slice(start, end);

    let description = '';
    pagedItems.forEach((model, index) => {
      const rank = start + index + 1;
      const ratingDiff = model.rating_realtime - model.rating;
      const ratingSymbol = ratingDiff > 0 ? '🔼' : (ratingDiff < 0 ? '🔽' : '');
      
      description += `# **${rank}. ${formatModelName(model.model_name)}**\n`;
      description += `> **评分:** ${model.rating} -> **${model.rating_realtime}** ${ratingSymbol}\n`;
      description += `> **(评分偏差:** ${model.rating_deviation} -> **${model.rating_deviation_realtime}** / **波动率:** ${(model.volatility * 1000).toFixed(2)}‰ -> **${(model.volatility_realtime * 1000).toFixed(2)}‰**)\n`;
      description += `> **胜率:** ${model.win_rate_percentage.toFixed(2)}%\n`;
      description += `> **对战:** ${model.battles} (胜: ${model.wins}, 平: ${model.ties}, 弃权: ${model.skips})\n`;
    });

    const nextUpdate = new Date(nextUpdateTime);
    const footerText = `第 ${page + 1} / ${totalPages} 页 | 周期性评分将于 ${nextUpdate.toLocaleTimeString('zh-CN')} 更新`;

    return new EmbedBuilder()
      .setColor(0xFFD700)
      .setTitle(title)
      .setDescription(safeTruncateEmbed(description))
      .setFooter({ text: footerText })
      .setTimestamp();
  };

  const generateButtons = (page) => {
    return new ActionRowBuilder()
      .addComponents(
        new ButtonBuilder()
          .setCustomId('leaderboard_prev')
          .setLabel('⬅️ 上一页')
          .setStyle(ButtonStyle.Primary)
          .setDisabled(page === 0),
        new ButtonBuilder()
          .setCustomId('leaderboard_next')
          .setLabel('下一页 ➡️')
          .setStyle(ButtonStyle.Primary)
          .setDisabled(page === totalPages - 1)
      );
  };

  const embed = generateEmbed(currentPage);
  const row = generateButtons(currentPage);

  const message = await interaction.editReply({
    embeds: [embed],
    components: totalPages > 1 ? [row] : [],
  });

  if (totalPages <= 1) return;

  const collector = message.createMessageComponentCollector({
    filter: i => i.user.id === interaction.user.id && (i.customId === 'leaderboard_prev' || i.customId === 'leaderboard_next'),
    time: 5 * 60 * 1000, // 5 分钟
  });

  collector.on('collect', async i => {
    if (i.customId === 'leaderboard_prev') {
      currentPage--;
    } else if (i.customId === 'leaderboard_next') {
      currentPage++;
    }

    const newEmbed = generateEmbed(currentPage);
    const newRow = generateButtons(currentPage);

    await i.update({ embeds: [newEmbed], components: [newRow] });
  });

  collector.on('end', () => {
    const disabledRow = new ActionRowBuilder()
      .addComponents(
        ButtonBuilder.from(row.components[0]).setDisabled(true),
        ButtonBuilder.from(row.components[1]).setDisabled(true)
      );
    interaction.editReply({ components: [disabledRow] }).catch(console.error);
  });
}

async function handleCommand(interaction) {
  console.log(`[Command] Received command: ${interaction.commandName} from user ${interaction.user.id} in channel ${interaction.channelId}`);
  if (interaction.commandName === 'battle' || interaction.commandName === 'battlelow') {
    // 用户/角色白名单检查
    if (!isMemberAllowed(interaction)) {
      console.log(`[Auth] User ${interaction.user.id} failed member check.`);
      const tips = (ALLOWED_USER_IDS.size || ALLOWED_ROLE_IDS.size)
        ? `此命令仅限以下用户/角色使用：${allowedUserRoleMentions()}`
        : '此命令暂不可用。';
      if (!interaction.deferred && !interaction.replied) {
        await interaction.reply({ content: `<@${interaction.user.id}> ${tips}`, flags: 'Ephemeral' });
      } else {
        await interaction.followUp({ content: `<@${interaction.user.id}> ${tips}`, flags: 'Ephemeral' });
      }
      return;
    }

    // 频道白名单检查
    if (!isChannelAllowed(interaction.channelId)) {
      console.log(`[Auth] Channel ${interaction.channelId} failed channel check.`);
      const tips = ALLOWED_CHANNEL_IDS.size
        ? `此命令仅限在以下频道使用：${allowedMentionList()}`
        : '此命令暂不可用。';
      if (!interaction.deferred && !interaction.replied) {
        await interaction.reply({ content: `<@${interaction.user.id}> ${tips}`, flags: 'Ephemeral' });
      } else {
        await interaction.followUp({ content: `<@${interaction.user.id}> ${tips}`, flags: 'Ephemeral' });
      }
      return;
    }
    try {
      // 步骤1：立即回复一个等待消息
      await interaction.reply({
        content: `<@${interaction.user.id}>\n**创建对战中：** 这通常需要一些时间，机器人会在创建成功后通知你。`,
        flags: 'Ephemeral'
      });

      const battleType = interaction.commandName === 'battle' ? 'high_tier' : 'low_tier';
      const payload = {
        battle_type: battleType,
        discord_id: interaction.user.id,
      };
      console.log(`[API] Sending POST request to ${API_URL}/battle with payload:`, JSON.stringify(payload, null, 2));
      const response = await axios.post(`${API_URL}/battle`, payload);
      const battle = response.data;
      console.log(`[API] Successfully created battle ${battle.battle_id} for user ${interaction.user.id}`);
      
      // 存储完整对战信息用于后续交互
      activeBattles.set(battle.battle_id, {
        ...battle,
        authorId: interaction.user.id,
        createdAt: new Date(), // 增加创建时间戳
      });

      // 步骤2：准备私信内容
      const embed = new EmbedBuilder()
        .setColor(0x0099FF)
        .setTitle('⚔️ 新的对战！')
        .addFields({ name: '对战 ID', value: `${battle.battle_id}` })
        .setFooter({ text: `状态: 等待投票` });

      // --- 使用 Description 字段智能展示 ---
      const themeText = battle.prompt_theme ? `**主题：** ${battle.prompt_theme}\n\n` : '';
      const quotedPrompt = battle.prompt.split('\n').map(line => `> ${line}`).join('\n');
      const baseText = `${themeText}用户提示词：\n${quotedPrompt}\n\n`;
      let templateA = `**模型 A 的回答**\n\`\`\`\n%content%\n\`\`\`\n`;
      let templateB = `**模型 B 的回答**\n\`\`\`\n%content%\n\`\`\``;
      
      const formattingLength = (baseText + templateA + templateB).replace(/%content%/g, '').length;
      const availableLength = 4096 - formattingLength;
      const minQuota = 1000; // 最小固定配额
      
      let responseA_display = battle.response_a;
      let responseB_display = battle.response_b;
      let truncated = false;
      let is_A_truncated = false;
      let is_B_truncated = false;

      if ((responseA_display.length + responseB_display.length) > availableLength) {
        truncated = true;
        let remainingLength = availableLength;
        
        // 处理A的配额
        if (responseA_display.length < minQuota) {
          // A 小于最小配额，完整显示A
          remainingLength -= responseA_display.length;
        } else {
          // A 大于最小配额，尝试分配一半可用空间
          const allocatedToA = Math.floor(availableLength / 2);
          if (responseA_display.length > allocatedToA) {
            const maxA_Length = allocatedToA > 3 ? allocatedToA - 3 : 0;
            responseA_display = responseA_display.substring(0, maxA_Length) + '...';
            is_A_truncated = true;
          }
          remainingLength -= responseA_display.length;
        }

        // 处理B的配额
        if (responseB_display.length > remainingLength) {
           // 确保为 '...' 留出空间
           const maxB_Length = remainingLength > 3 ? remainingLength - 3 : 0;
           responseB_display = responseB_display.substring(0, maxB_Length) + '...';
           is_B_truncated = true;
        }
      }

      if (is_A_truncated) templateA = `**模型 A 的回答 (部分)**\n\`\`\`\n%content%\n\`\`\`\n`;
      if (is_B_truncated) templateB = `**模型 B 的回答 (部分)**\n\`\`\`\n%content%\n\`\`\``;

      const finalDescription = baseText +
                               templateA.replace('%content%', responseA_display) +
                               templateB.replace('%content%', responseB_display);

      let finalDescriptionText = finalDescription;
      if (finalDescriptionText.length > 4096) {
        finalDescriptionText = finalDescriptionText.substring(0, 4093) + '...';
        // 检查末尾是否是未闭合的代码块
        const codeBlockMatch = finalDescriptionText.match(/```/g);
        if (codeBlockMatch && codeBlockMatch.length % 2 !== 0) {
          // 如果是奇数个，说明有未闭合的，我们把它补上
          finalDescriptionText = finalDescriptionText.substring(0, 4089) + '...\n```';
        }
      }
      embed.setDescription(safeTruncateEmbed(finalDescriptionText));

      if (truncated) {
        let hint = '';
        if (is_A_truncated && is_B_truncated) {
          hint = '模型 A 和 模型 B 的回答都过长';
        } else if (is_A_truncated) {
          hint = '模型 A 的回答过长';
        } else {
          hint = '模型 B 的回答过长';
        }
        embed.addFields({ name: '提示', value: `${hint}，请点击下方按钮查看完整内容。` });
      }

      embed.addFields({ name: '❗ 注意', value: '创建的对战若30分钟内无人投票将被自动销毁。成功投票的对战可被永久保存，并通过ID随时查询，可通过下方按钮查看全文。' });

      // 步骤3：准备按钮
      const viewButtons = new ActionRowBuilder()
        .addComponents(
          new ButtonBuilder()
            .setCustomId(`view_full:${battle.battle_id}:model_a`)
            .setLabel('查看模型A全文')
            .setStyle(ButtonStyle.Secondary),
          new ButtonBuilder()
            .setCustomId(`view_full:${battle.battle_id}:model_b`)
            .setLabel('查看模型B全文')
            .setStyle(ButtonStyle.Secondary)
        );

      const voteButtons = new ActionRowBuilder()
        .addComponents(
          new ButtonBuilder()
            .setCustomId(`vote:${battle.battle_id}:model_a`)
            .setLabel('👍 投给模型 A')
            .setStyle(ButtonStyle.Primary),
          new ButtonBuilder()
            .setCustomId(`vote:${battle.battle_id}:model_b`)
            .setLabel('👍 投给模型 B')
            .setStyle(ButtonStyle.Primary),
          new ButtonBuilder()
            .setCustomId(`vote:${battle.battle_id}:tie`)
            .setLabel('🤝 平局')
            .setStyle(ButtonStyle.Secondary),
          new ButtonBuilder()
            .setCustomId(`vote:${battle.battle_id}:skip`)
            .setLabel('弃权')
            .setStyle(ButtonStyle.Secondary)
        );
      
      // 步骤4：使用 followUp 发送包含对战结果的新私信
      await interaction.followUp({
        content: `<@${interaction.user.id}>`, // 在 content 中提及用户以触发通知
        embeds: [embed],
        components: [viewButtons, voteButtons],
        flags: 'Ephemeral'
      });

      // (可选) 如果你想删除第一条等待消息，可以取消下面的注释
      // await interaction.deleteReply();

    } catch (error) {
      console.error('创建对战时出错:', error.response ? JSON.stringify(error.response.data, null, 2) : error.message);
      
      // 检查是否是速率限制错误
      if (error.response && error.response.status === 429 && typeof error.response.data.detail === 'object') {
        const detail = error.response.data.detail;
        let baseMessage = detail.message; // 优先使用API提供的消息
        const availableAt = detail.available_at;
        const now = Date.now() / 1000;
        const waitSeconds = availableAt ? Math.ceil(availableAt - now) : 0;

        // 如果没有基础消息，则根据等待时间生成一个
        if (!baseMessage) {
            baseMessage = '创建对战过于频繁，请稍后重试。';
        }

        let finalMessage = baseMessage;
        
        // 如果有可用的等待时间，附加到消息后面
        if (waitSeconds > 0) {
            // 如果基础消息已经包含 "请稍后再试"，则替换它
            if (finalMessage.includes('，请稍后再试')) {
                finalMessage = finalMessage.replace('，请稍后再试', '');
            }
            
            // 根据时长选择合适的单位
            if (waitSeconds > 60) {
                const waitMinutes = Math.ceil(waitSeconds / 60);
                finalMessage += `，请在约 ${waitMinutes} 分钟后重试。`;
            } else {
                finalMessage += `，请在 ${waitSeconds} 秒后重试。`;
            }
        }

        // 将两条消息合并为一条，直接编辑原始消息
        const finalMessageWithMention = `<@${interaction.user.id}> ${finalMessage}`;
        await interaction.editReply({ content: finalMessageWithMention, components: [] });
        return;
      }

      // 处理其他类型的错误
      const detail = error?.response?.data?.detail || error?.response?.data?.message || error?.message || '未知错误';
      // 移除拼接的句号，让后端决定是否包含标点
      const errorMessage = `创建对战失败：${String(detail)}。请稍后再试。`.replace('。。', '。');
      const errorMessageWithMention = `<@${interaction.user.id}> ${errorMessage}`;

      // 编辑初始的 "创建中..." 消息来显示错误
      await interaction.editReply({ content: errorMessageWithMention, components: [] });
    }
  } else if (['leaderboard', 'leaderboardhigh', 'leaderboardlow'].includes(interaction.commandName)) {
    // 频道白名单检查
    if (!isChannelAllowed(interaction.channelId)) {
      const tips = ALLOWED_CHANNEL_IDS.size
        ? `此命令仅限在以下频道使用：${allowedMentionList()}`
        : '此命令暂不可用。';
      if (!interaction.deferred && !interaction.replied) {
        await interaction.reply({ content: `<@${interaction.user.id}> ${tips}`, flags: 'Ephemeral' });
      } else {
        await interaction.followUp({ content: `<@${interaction.user.id}> ${tips}`, flags: 'Ephemeral' });
      }
      return;
    }
    try {
      await interaction.deferReply({ flags: 'Ephemeral' });
      const url = `${API_URL}/leaderboard`;
      console.log(`[API] Sending GET request to ${url}`);
      const response = await axios.get(url);
      let { leaderboard, next_update_time } = response.data;

      let title = '🏆 模型总排行榜';
      if (interaction.commandName === 'leaderboardhigh') {
        title = '🏆 模型高端局排行榜';
        leaderboard = leaderboard.filter(m => m.tier === 'high');
      } else if (interaction.commandName === 'leaderboardlow') {
        title = '🏆 模型低端局排行榜';
        leaderboard = leaderboard.filter(m => m.tier === 'low');
      }

      if (!leaderboard || leaderboard.length === 0) {
        await interaction.editReply({ content: '该分段排行榜当前为空。' });
        return;
      }

      // 按实时评分降序排序
      leaderboard.sort((a, b) => b.rating_realtime - a.rating_realtime);

      await sendPaginatedLeaderboard(interaction, leaderboard, title, next_update_time);

    } catch (error) {
      console.error('获取排行榜时出错:', error);
      const errorMsg = `<@${interaction.user.id}> 获取排行榜失败，请稍后再试。`;
      if (!interaction.replied && !interaction.deferred) {
        await interaction.reply({ content: errorMsg, flags: 'Ephemeral' });
      } else {
        await interaction.editReply({ content: errorMsg });
      }
    }
  } else if (interaction.commandName === 'battleinfo') {
    // 频道白名单检查
    if (!isChannelAllowed(interaction.channelId)) {
      const tips = ALLOWED_CHANNEL_IDS.size
        ? `此命令仅限在以下频道使用：${allowedMentionList()}`
        : '此命令暂不可用。';
      if (!interaction.deferred && !interaction.replied) {
        await interaction.reply({ content: `<@${interaction.user.id}> ${tips}`, flags: 'Ephemeral' });
      } else {
        await interaction.followUp({ content: `<@${interaction.user.id}> ${tips}`, flags: 'Ephemeral' });
      }
      return;
    }

    try {
      // 需求变更：所有命令响应仅发起人可见
      await interaction.deferReply({ flags: 'Ephemeral' });
      const battleId = interaction.options.getString('battle_id', true);

      const url = `${API_URL}/battle/${battleId}`;
      console.log(`[API] Sending GET request to ${url}`);
      const response = await axios.get(url);
      const data = response.data;

      const statusRaw = data.status;
      const statusDisplay =
        (!statusRaw || statusRaw === 'pending_vote') ? '等待投票'
        : (statusRaw === 'completed' ? '已完成' : statusRaw);

      // 将获取到的对战信息存入缓存，以便“查看全文”按钮能够使用
      activeBattles.set(battleId, {
        ...data,
        authorId: interaction.user.id, // 记录本次交互的用户
        createdAt: new Date(),
      });
      // 5分钟后自动清理缓存
      setTimeout(() => {
        activeBattles.delete(battleId);
      }, 5 * 60 * 1000);

      const embed = new EmbedBuilder()
        .setColor(statusRaw === 'completed' ? 0x57F287 : 0x0099FF)
        .setTitle('⚔️ 对战详情')
        .addFields({ name: '对战 ID', value: `${data.battle_id}` })
        .setFooter({ text: `状态: ${statusDisplay}` });

      // --- 复用 /battle 命令的智能截断和展示逻辑 ---
      const themeText = data.prompt_theme ? `**主题：** ${data.prompt_theme}\n\n` : '';
      const quotedPrompt = data.prompt.split('\n').map(line => `> ${line}`).join('\n');
      const baseText = `${themeText}**提示词:**\n${quotedPrompt}\n\n`;
      let templateA = `**模型 A 的回答**\n\`\`\`\n%content%\n\`\`\`\n`;
      let templateB = `**模型 B 的回答**\n\`\`\`\n%content%\n\`\`\``;

      const formattingLength = (baseText + templateA + templateB).replace(/%content%/g, '').length;
      const availableLength = 4096 - formattingLength;
      const minQuota = 1000;

      let responseA_display = data.response_a || 'N/A';
      let responseB_display = data.response_b || 'N/A';
      let truncated = false;
      let is_A_truncated = false;
      let is_B_truncated = false;

      if ((responseA_display.length + responseB_display.length) > availableLength) {
        truncated = true;
        let remainingLength = availableLength;

        if (responseA_display.length < minQuota) {
          remainingLength -= responseA_display.length;
        } else {
          const allocatedToA = Math.floor(availableLength / 2);
          if (responseA_display.length > allocatedToA) {
            const maxA_Length = allocatedToA > 3 ? allocatedToA - 3 : 0;
            responseA_display = responseA_display.substring(0, maxA_Length) + '...';
            is_A_truncated = true;
          }
          remainingLength -= responseA_display.length;
        }

        if (responseB_display.length > remainingLength) {
          const maxB_Length = remainingLength > 3 ? remainingLength - 3 : 0;
          responseB_display = responseB_display.substring(0, maxB_Length) + '...';
          is_B_truncated = true;
        }
      }

      if (is_A_truncated) templateA = `**模型 A 的回答 (部分)**\n\`\`\`\n%content%\n\`\`\`\n`;
      if (is_B_truncated) templateB = `**模型 B 的回答 (部分)**\n\`\`\`\n%content%\n\`\`\``;

      const finalDescription = baseText +
                               templateA.replace('%content%', responseA_display) +
                               templateB.replace('%content%', responseB_display);

      let finalDescriptionText = finalDescription;
      if (finalDescriptionText.length > 4096) {
        finalDescriptionText = finalDescriptionText.substring(0, 4093) + '...';
        const codeBlockMatch = finalDescriptionText.match(/```/g);
        if (codeBlockMatch && codeBlockMatch.length % 2 !== 0) {
          finalDescriptionText = finalDescriptionText.substring(0, 4089) + '...\n```';
        }
      }
      embed.setDescription(safeTruncateEmbed(finalDescriptionText));

      if (truncated) {
        let hint = '';
        if (is_A_truncated && is_B_truncated) {
          hint = '模型 A 和 模型 B 的回答都过长';
        } else if (is_A_truncated) {
          hint = '模型 A 的回答过长';
        } else if (is_B_truncated) {
          hint = '模型 B 的回答过长';
        }
        if (hint) {
          embed.addFields({ name: '提示', value: `${hint}，请点击下方按钮查看完整内容。` });
        }
      }
      
      const viewButtons = new ActionRowBuilder()
        .addComponents(
          new ButtonBuilder()
            .setCustomId(`view_full:${battleId}:model_a`)
            .setLabel('查看模型A全文')
            .setStyle(ButtonStyle.Secondary),
          new ButtonBuilder()
            .setCustomId(`view_full:${battleId}:model_b`)
            .setLabel('查看模型B全文')
            .setStyle(ButtonStyle.Secondary)
        );

      if (statusRaw === 'completed') {
        let winnerText = 'N/A';
        if (data.winner === 'model_a') {
          winnerText = formatModelName(data.model_a);
        } else if (data.winner === 'model_b') {
          winnerText = formatModelName(data.model_b);
        } else if (data.winner === 'Tie') {
          winnerText = '平局';
        } else if (data.winner === 'Skipped') {
          winnerText = '跳过';
        } else if (data.winner) {
          winnerText = formatModelName(data.winner);
        }

        embed.addFields(
          { name: '模型 A 名称', value: formatModelName(data.model_a), inline: true },
          { name: '模型 B 名称', value: formatModelName(data.model_b), inline: true },
          { name: '获胜者', value: winnerText, inline: false }
        );
      }

      await interaction.editReply({ embeds: [embed], components: [viewButtons] });
    } catch (error) {
      console.error('获取对战详情时出错:', error);
      if(error.response) {
        console.error('API 错误响应数据:', JSON.stringify(error.response.data, null, 2));
      }
      const code = error?.response?.status;
      const detail = error?.response?.data?.detail || error?.message || '未知错误';
      const msg = code === 404 ? '未找到该对战，请确认对战 ID 是否正确。' : `获取对战详情失败：${detail}`;
      const errorMsg = `<@${interaction.user.id}> ${msg}`;
      if (!interaction.replied && !interaction.deferred) {
        await interaction.reply({ content: errorMsg, flags: 'Ephemeral' });
      } else {
        await interaction.editReply({ content: errorMsg });
      }
    }

  } else if (interaction.commandName === 'health') {
    // 频道白名单检查
    if (!isChannelAllowed(interaction.channelId)) {
      const tips = ALLOWED_CHANNEL_IDS.size
        ? `此命令仅限在以下频道使用：${allowedMentionList()}`
        : '此命令暂不可用。';
      if (!interaction.deferred && !interaction.replied) {
        await interaction.reply({ content: `<@${interaction.user.id}> ${tips}`, flags: 'Ephemeral' });
      } else {
        await interaction.followUp({ content: `<@${interaction.user.id}> ${tips}`, flags: 'Ephemeral' });
      }
      return;
    }

    try {
      // 需求变更：所有命令响应仅发起人可见
      await interaction.deferReply({ flags: 'Ephemeral' });
      const url = `${API_URL}/health`;
      console.log(`[API] Sending GET request to ${url}`);
      const response = await axios.get(url, { timeout: 30000 }); // 30秒超时
      const data = response.data;

      const ok = data.status === 'ok';
      const embed = new EmbedBuilder()
        .setColor(ok ? 0x57F287 : 0xED4245)
        .setTitle('🩺 系统健康检查')
        .addFields(
          { name: '状态', value: String(data.status || 'unknown'), inline: true },
          { name: '模型数量', value: String(data.models_count ?? 'N/A'), inline: true },
          { name: '固定提示词数量', value: String(data.fixed_prompts_count ?? 'N/A'), inline: true },
          { name: '已记录用户数', value: String(data.recorded_users_count ?? 'N/A'), inline: true },
          { name: '已完成的对战数', value: String(data.completed_battles_count ?? 'N/A'), inline: true }
        )
        .setTimestamp();

      await interaction.editReply({ embeds: [embed] });
    } catch (error) {
      console.error('获取健康检查时出错:', error.response ? error.response.data : error.message);
      let detail = error?.response?.data?.detail || error?.message || '未知错误';
      if (error.code === 'ECONNABORTED') {
        detail = '请求超时（超过30秒无响应），后端服务可能无响应或负载过高。';
      }
      const errorMsg = `<@${interaction.user.id}> 获取健康检查失败：${detail}`;
      if (!interaction.replied && !interaction.deferred) {
        await interaction.reply({ content: errorMsg, flags: 'Ephemeral' });
      } else {
        await interaction.editReply({ content: errorMsg });
      }
    }
  } else if (interaction.commandName === 'battleback') {
    // 频道白名单检查
    if (!isChannelAllowed(interaction.channelId)) {
      const tips = ALLOWED_CHANNEL_IDS.size
        ? `此命令仅限在以下频道使用：${allowedMentionList()}`
        : '此命令暂不可用。';
      await interaction.reply({ content: `<@${interaction.user.id}> ${tips}`, flags: 'Ephemeral' });
      return;
    }

    try {
      await interaction.reply({ content: '正在查找你上一场对战...', flags: 'Ephemeral' });

      const response = await axios.post(`${API_URL}/battleback`, {
        discord_id: interaction.user.id,
      });
      const data = response.data;

      // 情况1: 对战正在生成中
      if (data.message && data.message.includes('创建对战中')) {
        await interaction.editReply({ content: data.message });
        return;
      }

      // 情况2: 找到了等待投票或已完成的对战
      if (data.battle_id) {
        const battle = data;
        // --- 复用 battle 和 battleinfo 的显示逻辑 ---
        activeBattles.set(battle.battle_id, {
          ...battle,
          authorId: interaction.user.id,
          createdAt: new Date(),
        });

        const statusRaw = battle.status || 'pending_vote';
        const statusDisplay = statusRaw === 'completed' ? '已完成' : '等待投票';

        const embed = new EmbedBuilder()
          .setColor(statusRaw === 'completed' ? 0x57F287 : 0x0099FF)
          .setTitle('⚔️ 召回对战成功！')
          .addFields({ name: '对战 ID', value: `${battle.battle_id}` })
          .setFooter({ text: `状态: ${statusDisplay}` });

        const themeText = battle.prompt_theme ? `**主题：** ${battle.prompt_theme}\n\n` : '';
        const quotedPrompt = battle.prompt.split('\n').map(line => `> ${line}`).join('\n');
        const baseText = `${themeText}**提示词:**\n${quotedPrompt}\n\n`;
        let templateA = `**模型 A 的回答**\n\`\`\`\n%content%\n\`\`\`\n`;
        let templateB = `**模型 B 的回答**\n\`\`\`\n%content%\n\`\`\``;

        const formattingLength = (baseText + templateA + templateB).replace(/%content%/g, '').length;
        const availableLength = 4096 - formattingLength;
        const minQuota = 1000;

        let responseA_display = battle.response_a || 'N/A';
        let responseB_display = battle.response_b || 'N/A';
        let truncated = false;
        let is_A_truncated = false;
        let is_B_truncated = false;

        if ((responseA_display.length + responseB_display.length) > availableLength) {
          truncated = true;
          let remainingLength = availableLength;
          if (responseA_display.length < minQuota) {
            remainingLength -= responseA_display.length;
          } else {
            const allocatedToA = Math.floor(availableLength / 2);
            if (responseA_display.length > allocatedToA) {
              const maxA_Length = allocatedToA > 3 ? allocatedToA - 3 : 0;
              responseA_display = responseA_display.substring(0, maxA_Length) + '...';
              is_A_truncated = true;
            }
            remainingLength -= responseA_display.length;
          }
          if (responseB_display.length > remainingLength) {
            const maxB_Length = remainingLength > 3 ? remainingLength - 3 : 0;
            responseB_display = responseB_display.substring(0, maxB_Length) + '...';
            is_B_truncated = true;
          }
        }

        if (is_A_truncated) templateA = `**模型 A 的回答 (部分)**\n\`\`\`\n%content%\n\`\`\`\n`;
        if (is_B_truncated) templateB = `**模型 B 的回答 (部分)**\n\`\`\`\n%content%\n\`\`\``;

        const finalDescription = baseText +
                                 templateA.replace('%content%', responseA_display) +
                                 templateB.replace('%content%', responseB_display);

        let finalDescriptionText = finalDescription;
        if (finalDescriptionText.length > 4096) {
          finalDescriptionText = finalDescriptionText.substring(0, 4093) + '...';
          const codeBlockMatch = finalDescriptionText.match(/```/g);
          if (codeBlockMatch && codeBlockMatch.length % 2 !== 0) {
            finalDescriptionText = finalDescriptionText.substring(0, 4089) + '...\n```';
          }
        }
        embed.setDescription(safeTruncateEmbed(finalDescriptionText));
        
        const components = [];
        const viewButtons = new ActionRowBuilder()
          .addComponents(
            new ButtonBuilder().setCustomId(`view_full:${battle.battle_id}:model_a`).setLabel('查看模型A全文').setStyle(ButtonStyle.Secondary),
            new ButtonBuilder().setCustomId(`view_full:${battle.battle_id}:model_b`).setLabel('查看模型B全文').setStyle(ButtonStyle.Secondary)
          );
        components.push(viewButtons);

        if (statusRaw === 'pending_vote') {
          embed.addFields({ name: '❗ 注意', value: '创建的对战若30分钟内无人投票将被自动销毁。' });
          const voteButtons = new ActionRowBuilder()
            .addComponents(
              new ButtonBuilder().setCustomId(`vote:${battle.battle_id}:model_a`).setLabel('👍 投给模型 A').setStyle(ButtonStyle.Primary),
              new ButtonBuilder().setCustomId(`vote:${battle.battle_id}:model_b`).setLabel('👍 投给模型 B').setStyle(ButtonStyle.Primary),
              new ButtonBuilder().setCustomId(`vote:${battle.battle_id}:tie`).setLabel('🤝 平局').setStyle(ButtonStyle.Secondary),
              new ButtonBuilder().setCustomId(`vote:${battle.battle_id}:skip`).setLabel('弃权').setStyle(ButtonStyle.Secondary)
            );
          components.push(voteButtons);
        } else if (statusRaw === 'completed') {
            let winnerText = 'N/A';
            if (battle.winner === 'model_a') {
              winnerText = formatModelName(battle.model_a);
            } else if (battle.winner === 'model_b') {
              winnerText = formatModelName(battle.model_b);
            } else if (battle.winner === 'Tie') {
              winnerText = '平局';
            } else if (battle.winner === 'Skipped') {
              winnerText = '跳过';
            } else if (battle.winner) {
              winnerText = formatModelName(battle.winner);
            }
            embed.addFields(
              { name: '模型 A 名称', value: formatModelName(battle.model_a), inline: true },
              { name: '模型 B 名称', value: formatModelName(battle.model_b), inline: true },
              { name: '获胜者', value: winnerText, inline: false }
            );
        }

        await interaction.editReply({ content: `<@${interaction.user.id}>`, embeds: [embed], components: components });
      } else {
        // 其他情况，通常是 "未找到记录"
        const detail = data.detail || '无法召回对战，可能没有正在进行的对战。';
        await interaction.editReply({ content: `<@${interaction.user.id}> ${detail}` });
      }
    } catch (error) {
      console.error('召回对战时出错:', error.response ? JSON.stringify(error.response.data, null, 2) : error.message);
      const detail = error?.response?.data?.detail || '召回对战失败，请稍后再试。';
      await interaction.editReply({ content: `<@${interaction.user.id}> ${detail}` });
    }
  } else if (interaction.commandName === 'battleunstuck') {
    if (!isChannelAllowed(interaction.channelId)) {
      const tips = ALLOWED_CHANNEL_IDS.size
        ? `此命令仅限在以下频道使用：${allowedMentionList()}`
        : '此命令暂不可用。';
      await interaction.reply({ content: `<@${interaction.user.id}> ${tips}`, flags: 'Ephemeral' });
      return;
    }

    try {
      await interaction.reply({ content: '正在尝试清除卡住的对战...', flags: 'Ephemeral' });

      const response = await axios.post(`${API_URL}/battleunstuck`, {
        discord_id: interaction.user.id,
      });

      const message = response.data.message || '操作已完成，但未收到明确消息。';
      await interaction.editReply({ content: `<@${interaction.user.id}> ${message}` });

    } catch (error) {
      console.error('清除卡住的对战时出错:', error.response ? JSON.stringify(error.response.data, null, 2) : error.message);
      const detail = error?.response?.data?.detail || '操作失败，请稍后再试。';
      await interaction.editReply({ content: `<@${interaction.user.id}> ${detail}` });
    }
  }
}

async function handleButton(interaction) {
  if (interaction.customId.startsWith('leaderboard_')) return;
  const [action, battleId, choice] = interaction.customId.split(':');

  if (action === 'view_full') {
    await handleViewFullButton(interaction, battleId, choice);
  } else if (action === 'vote') {
    await handleVoteButton(interaction, battleId, choice);
  }
}

async function handleViewFullButton(interaction, battleId, modelChoice) {
  await interaction.deferReply({ flags: 'Ephemeral' });

  const battleInfo = activeBattles.get(battleId);
  if (!battleInfo) {
    await interaction.editReply({ content: '抱歉，这场对战的信息已过期。' });
    return;
  }

  const content = modelChoice === 'model_a' ? battleInfo.response_a : battleInfo.response_b;
  const modelName = modelChoice === 'model_a' ? '模型 A' : '模型 B';

  try {
    // 修正 API 端点，移除末尾的斜杠
    const response = await axios.post('https://pasteme.cn/api/v3/paste', {
      lang: 'plain',
      content: content,
      self_destruct: true,
      expire_count: 1,
      expire_second: 300
    }, {
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (response.data && response.data.key) {
      const pasteUrl = `https://pasteme.cn/api/v3/paste/${response.data.key}`;
      // 在链接两边加上尖括号，防止 Discord 爬虫预取
      await interaction.editReply({ content: `<@${interaction.user.id}> 以下是 **${modelName}** 的完整内容链接（链接300秒后或查看一次后失效）：\n<${pasteUrl}>` });
    } else {
      // 如果 API 成功但没有返回 key，也作为错误处理
      console.error('pasteme.cn API 响应异常:', response.data);
      throw new Error('API did not return a key.');
    }
  } catch (error) {
    // 增加更详细的错误日志
    if (error.response) {
      // 请求已发出，但服务器用状态码响应
      console.error('pasteme.cn API Error Response:', {
        data: error.response.data,
        status: error.response.status,
        headers: error.response.headers,
      });
    } else if (error.request) {
      // 请求已发出，但没有收到响应
      console.error('pasteme.cn API No Response:', error.request);
    } else {
      // 设置请求时发生错误
      console.error('pasteme.cn Axios Setup Error:', error.message);
    }
    
    try {
      await interaction.editReply({ content: '生成临时链接失败，请稍后再试或联系管理员。' });
    } catch (editError) {
      // 如果 editReply 也失败了（例如交互已过期），尝试 followUp
      console.error('Failed to editReply, attempting followUp:', editError);
      await interaction.followUp({ content: '生成临时链接失败，请稍后再试或联系管理员。', flags: 'Ephemeral' });
    }
  }
}

async function handleVoteButton(interaction, battleId, choice) {
  // 无感优化：一次性确认并原地编辑为“处理中”
  try {
    await interaction.deferUpdate();
  } catch (preEditErr) {
    console.error('投票预处理失败:', preEditErr);
    // 如果 deferUpdate 失败，后续的 webhook 编辑可能会出问题，但我们仍然尝试
  }
  
  const battleInfo = activeBattles.get(battleId);
  // 优化：即使缓存不存在，也应该继续尝试API调用。但如果缓存存在，我们可以预先检查发起者。
  if (battleInfo && interaction.user.id !== battleInfo.authorId) {
    // 这里不能编辑消息，因为交互不属于该用户。所以我们什么都不做，或者可以发一条新的ephemeral消息
    await interaction.followUp({ content: '抱歉，只有发起这场对战的用户才能投票。', flags: 'Ephemeral' });
    return;
  }

  try {
    const payload = {
      vote_choice: choice,
      discord_id: interaction.user.id
    };
    
    const response = await axios.post(`${API_URL}/vote/${battleId}`, payload);
    const voteResult = response.data;

    if (voteResult.status === 'success') {
      // 投票成功后，启动一个5分钟的定时器来删除该对战信息
      setTimeout(() => {
        activeBattles.delete(battleId);
        console.log(`[Cache Cleanup] Battle ${battleId} has been automatically deleted after 5 minutes.`);
      }, 5 * 60 * 1000); // 5 minutes in milliseconds

      // 获取原始 embed 并修改它
      const originalEmbed = interaction.message.embeds[0];
      let winnerText = 'N/A';
      if (voteResult.winner === 'model_a') {
        winnerText = formatModelName(voteResult.model_a_name);
      } else if (voteResult.winner === 'model_b') {
        winnerText = formatModelName(voteResult.model_b_name);
      } else if (voteResult.winner === 'Tie') {
        winnerText = '平局';
      } else if (voteResult.winner === 'Skipped') {
        winnerText = '跳过';
      } else if (voteResult.winner) {
        winnerText = formatModelName(voteResult.winner);
      }

      // 创建一个全新的 Embed，而不是基于旧的修改，以避免潜在的渲染问题
      const updatedEmbed = new EmbedBuilder()
        .setColor(0x57F287)
        .setTitle('⚔️ 对战已完成！')
        .setDescription(safeTruncateEmbed(originalEmbed?.description ?? '')) // 保留原始的 prompt 和回答部分
        .addFields(
          { name: '对战 ID', value: battleId },
          { name: '获胜者', value: `**${winnerText}**`, inline: false },
          { name: '模型 A 名称', value: formatModelName(voteResult.model_a_name), inline: true },
          { name: '模型 B 名称', value: formatModelName(voteResult.model_b_name), inline: true },
          { name: '❗ 注意', value: '此条消息会在5分钟销毁，请及时通过下方按钮查看或保存，也可通过其他指令重新查看本对战的完整内容。' }
        )
        .setFooter({ text: `状态: 已完成` });

      // 保留查看按钮，禁用投票按钮
      const originalComponents = interaction.message.components;
      const updatedComponents = [];

      originalComponents.forEach(row => {
        const newRow = new ActionRowBuilder();
        row.components.forEach(comp => {
          const newComp = ButtonBuilder.from(comp);
          if (comp.customId.startsWith('vote:')) {
            newComp.setDisabled(true);
          }
          newRow.addComponents(newComp);
        });
        updatedComponents.push(newRow);
      });
      
      await interaction.editReply({ embeds: [updatedEmbed], components: updatedComponents });

    } else {
      // 业务错误
      await interaction.editReply({ content: `投票失败：${voteResult.message || '未知原因'}` });
    }

  } catch (error) {
    // 增加详细日志
    console.error('投票时出错:', error.response ? JSON.stringify(error.response.data, null, 2) : error.message);
    
    // 如果 error.response 不存在，通常是网络问题（例如后端服务未启动）
    if (!error.response) {
      await interaction.followUp({
        content: '投票服务当前不可用，请稍后再试或联系管理员。',
        flags: 'Ephemeral'
      });
      return;
    }

    const status = error.response.status;
    const detail = error.response.data?.detail || error.response.data?.message || '未知错误';

    if (status === 404 && String(detail).includes('超时被自动销毁')) {
      // 对战已超时，发送一个临时的 follow-up 消息
      await interaction.followUp({
        content: '这个对决已经超时（超过30分钟未投票），被自动关闭了。',
        flags: 'Ephemeral'
      });
    } else {
      // 其他API错误，使用 followUp 发送临时消息，避免修改原始投票界面
      await interaction.followUp({ content: `<@${interaction.user.id}> 投票失败：${String(detail)}`, flags: 'Ephemeral' });
    }
  }
}

client.login(process.env.TOKEN);