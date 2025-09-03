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

// 用于存储用户会话信息
const userSessions = new Map();
// 用于存储会话ID与用户ID的映射
const sessionToUser = new Map();

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
      let sessionId;
      
      // 尝试获取用户最新的会话ID
      try {
        const latestSessionResponse = await axios.post(`${API_URL}/sessions/latest`, {
          discord_id: interaction.user.id
        });
        
        if (latestSessionResponse.data && latestSessionResponse.data.session_id) {
          // 如果有现有会话且轮次小于5，继续使用该会话
          if (latestSessionResponse.data.turn_count < 5) {
            sessionId = latestSessionResponse.data.session_id;
            console.log(`[Session] 继续使用现有会话 ${sessionId}，当前轮次：${latestSessionResponse.data.turn_count}`);
          } else {
            // 轮次已达上限，创建新会话
            sessionId = crypto.randomUUID();
            console.log(`[Session] 现有会话已达到最大轮次，创建新会话 ${sessionId}`);
          }
        } else {
          // 没有现有会话，创建新会话
          sessionId = crypto.randomUUID();
          console.log(`[Session] 未找到现有会话，创建新会话 ${sessionId}`);
        }
      } catch (error) {
        // 获取会话失败，创建新会话
        sessionId = crypto.randomUUID();
        console.log(`[Session] 获取最新会话失败，创建新会话 ${sessionId}：`, error.message);
      }
      
      // 初始化用户会话信息，记录对话轮次和会话状态
      userSessions.set(interaction.user.id, {
        sessionId: sessionId,
        battleType: battleType,
        conversationCount: 0,
        maxConversations: 5, // 最多对话5次后必须重置
        status: 'initializing', // 状态：initializing, character_selection, ongoing, completed
        authorId: interaction.user.id,
        characterMessages: [],
        currentMessage: null,
        messageHistory: [],
        createdAt: new Date()
      });
      
      // 同时记录会话ID到用户ID的映射，方便后续查找
      sessionToUser.set(sessionId, interaction.user.id);

      // 准备初始请求参数，input设为null以触发角色消息生成
      const payload = {
        session_id: sessionId,
        battle_type: battleType,
        discord_id: interaction.user.id,
        input: null  // 关键点：input为null，表示初次对战
      };
      
      console.log(`[API] Sending POST request to ${API_URL}/battle with payload:`, JSON.stringify(payload, null, 2));
      const response = await axios.post(`${API_URL}/battle`, payload);
      const battle = response.data;
      console.log(`[API] Successfully initiated session ${sessionId} for user ${interaction.user.id}`);
      console.log('[API] Backend Response:', JSON.stringify(battle, null, 2));
      
      // 检查是否获取到了character_messages
      if (!battle.character_messages || battle.character_messages.length === 0) {
        await interaction.followUp({
          content: `<@${interaction.user.id}> 未能获取到初始角色消息，请稍后重试。`,
          flags: 'Ephemeral'
        });
        return;
      }
      
      // 更新用户会话状态
      const userSession = userSessions.get(interaction.user.id);
      userSession.status = 'character_selection';
      userSession.characterMessages = battle.character_messages;
      userSessions.set(interaction.user.id, userSession);
      
      // 创建显示角色消息的Embed
      const embed = new EmbedBuilder()
        .setColor(0x0099FF)
        .setTitle('⚔️ 选择初始场景')
        .setDescription('请选择以下场景之一及其对应选项作为对话的开始：')
        .setFooter({ text: `会话ID: ${sessionId} | 状态: 选择初始行动` });

      const components = [];
      
      // 添加每个角色消息到Embed中，并创建对应的按钮
      battle.character_messages.forEach((msg, characterIndex) => {
        const sceneLabel = String.fromCharCode(65 + characterIndex); // A, B, C...
        const optionsDescription = (msg.options && msg.options.length > 0)
          ? msg.options.map((opt, i) => `> **${sceneLabel}${i + 1}:** ${opt}`).join('\n\n')
          : '> 此场景没有预设选项。';

        embed.addFields({
          name: `场景 ${sceneLabel}`,
          value: `${safeTruncateEmbed(msg.text)}\n\n${optionsDescription}`
        });

        if (msg.options && msg.options.length > 0) {
          const row = new ActionRowBuilder();
          msg.options.forEach((_, optionIndex) => {
            const buttonLabel = `${sceneLabel}${optionIndex + 1}`;
            row.addComponents(
              new ButtonBuilder()
                .setCustomId(`select_initial_option:${sessionId}:${characterIndex}:${optionIndex}`)
                .setLabel(buttonLabel)
                .setStyle(ButtonStyle.Primary)
            );
          });
          components.push(row);
        } else {
            const row = new ActionRowBuilder();
            row.addComponents(
                new ButtonBuilder()
                    .setCustomId(`select_character:${sessionId}:${characterIndex}`)
                    .setLabel(`选择场景 ${sceneLabel} (查看后续选项)`)
                    .setStyle(ButtonStyle.Secondary)
            );
            components.push(row);
        }
      });
      
      // 发送包含角色选择的消息
      await interaction.followUp({
        content: `<@${interaction.user.id}>`,
        embeds: [embed],
        components: components,
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
  
  const parts = interaction.customId.split(':');
  const action = parts[0];

  if (action === 'select_initial_option') {
    const sessionId = parts[1];
    const characterIndex = parts[2];
    const optionIndex = parts[3];
    await handleInitialOptionSelectionButton(interaction, sessionId, characterIndex, optionIndex);
    return;
  }

  const sessionOrBattleId = parts[1];
  const choice = parts[2];

  if (action === 'view_full') {
    await handleViewFullButton(interaction, sessionOrBattleId, choice);
  } else if (action === 'vote') {
    await handleVoteButton(interaction, sessionOrBattleId, choice);
  } else if (action === 'select_character') {
    await handleCharacterSelectionButton(interaction, sessionOrBattleId, choice);
  } else if (action === 'select_option') {
    await handleOptionSelectionButton(interaction, sessionOrBattleId, choice);
  } else if (action === 'reveal_models') {
    await handleRevealModelsButton(interaction, sessionOrBattleId, choice);
  // 移除不再需要的confirm_selection处理
  } else if (action === 'continue_battle') {
    await handleContinueBattleButton(interaction, sessionOrBattleId, choice);
  }
}

// 处理角色选择按钮
async function handleCharacterSelectionButton(interaction, sessionId, characterIndex) {
  await interaction.deferUpdate();
  
  // 获取用户ID
  const userId = sessionToUser.get(sessionId);
  if (!userId || userId !== interaction.user.id) {
    await interaction.followUp({
      content: '只有发起会话的用户才能选择角色消息。',
      flags: 'Ephemeral'
    });
    return;
  }
  
  // 获取会话信息
  const userSession = userSessions.get(userId);
  if (!userSession || userSession.sessionId !== sessionId || userSession.status !== 'character_selection') {
    await interaction.followUp({
      content: '会话状态已改变，无法选择角色消息。',
      flags: 'Ephemeral'
    });
    return;
  }
  
  try {
    // 获取选中的角色消息和选项
    const selectedCharacterMessage = userSession.characterMessages[characterIndex];
    
    // 向API发送角色选择请求
    const payload = {
      session_id: sessionId,
      character_messages_id: parseInt(characterIndex)
    };
    
    console.log(`[API] Sending POST request to ${API_URL}/character_selection with payload:`, JSON.stringify(payload, null, 2));
    const response = await axios.post(`${API_URL}/character_selection`, payload);
    
    // 更新会话状态
    userSession.status = 'ongoing';
    userSession.currentMessage = { text: selectedCharacterMessage.text };
    userSession.messageHistory.push({ text: selectedCharacterMessage.text });
    userSessions.set(userId, userSession);
    
    // 创建显示选项的Embed
    const embed = new EmbedBuilder()
      .setColor(0x0099FF)
      .setTitle('⚔️ 你选择了以下场景')
      .setDescription(safeTruncateEmbed(selectedCharacterMessage.text))
      .setFooter({ text: `会话ID: ${sessionId} | 状态: 选择回复选项` });
    
    // 创建选项按钮
    const optionButtons = new ActionRowBuilder();
    
    // 使用消息中已包含的选项
    selectedCharacterMessage.options.forEach((option, index) => {
      optionButtons.addComponents(
        new ButtonBuilder()
          .setCustomId(`select_option:${sessionId}:${index}`)
          .setLabel(`选项 ${index + 1}`)
          .setStyle(ButtonStyle.Primary)
      );
    });
    
    // 更新原消息
    await interaction.editReply({
      content: `<@${userId}> 请选择下面的选项继续:`,
      embeds: [embed],
      components: [optionButtons]
    });
    
    // 添加选项描述
    const optionsEmbed = new EmbedBuilder()
      .setColor(0x0099FF)
      .setTitle('可选的回复选项')
      .setDescription('');
    
    // 为每个选项添加描述
    selectedCharacterMessage.options.forEach((option, index) => {
      optionsEmbed.addFields({
        name: `选项 ${index + 1}`,
        value: safeTruncateEmbed(option)
      });
    });
    
    // 发送选项描述
    await interaction.followUp({
      embeds: [optionsEmbed],
      flags: 'Ephemeral'
    });
    
  } catch (error) {
    console.error('处理角色选择时出错:', error.response ? JSON.stringify(error.response.data, null, 2) : error.message);
    await interaction.followUp({
      content: `处理角色选择失败: ${error.response?.data?.detail || error.message}`,
      flags: 'Ephemeral'
    });
  }
}

// 新增：处理初始场景和选项一步到位的按钮
async function handleInitialOptionSelectionButton(interaction, sessionId, characterIndex, optionIndex) {
  // 1. 获取用户会话和选择内容
  const userId = sessionToUser.get(sessionId);
  if (!userId || userId !== interaction.user.id) {
    await interaction.reply({ content: '这不属于你的会话。', ephemeral: true });
    return;
  }
  const userSession = userSessions.get(userId);
  if (!userSession || userSession.sessionId !== sessionId || userSession.status !== 'character_selection') {
    await interaction.reply({ content: '会话已过期或状态不正确。', ephemeral: true });
    return;
  }

  const selectedScene = userSession.characterMessages[characterIndex];
  const selectedOptionText = selectedScene.options[optionIndex];
  const sceneLabel = String.fromCharCode(65 + parseInt(characterIndex));
  const optionLabel = `${sceneLabel}${parseInt(optionIndex) + 1}`;

  // 2. 立即修改原始消息，显示用户的选择并禁用按钮
  const confirmationEmbed = new EmbedBuilder()
    .setColor(0x57F287) // Green color for confirmation
    .setTitle('✅ 初始场景已选择')
    .setDescription(safeTruncateEmbed(selectedScene.text))
    .addFields({ name: '你选择了', value: `> **${optionLabel}:** ${selectedOptionText}` })
    .setFooter({ text: `会话ID: ${sessionId} | 状态: 已确认` });

  await interaction.update({
    embeds: [confirmationEmbed],
    components: []
  });

  // 3. 发送一个新的"处理中"消息
  const loadingMessage = await interaction.followUp({
    content: `<@${userId}> 你的选择已确认，正在生成模型的回复...`,
    ephemeral: true
  });

  try {
    // 4. 在后台调用API
    const characterSelectionPayload = {
      session_id: sessionId,
      character_messages_id: parseInt(characterIndex)
    };
    console.log(`[API] Sending POST to /character_selection:`, JSON.stringify(characterSelectionPayload, null, 2));
    const charSelectionResponse = await axios.post(`${API_URL}/character_selection`, characterSelectionPayload);
    console.log(`[API] Response from /character_selection:`, JSON.stringify(charSelectionResponse.data, null, 2));

    userSession.status = 'ongoing';
    userSession.messageHistory.push({ text: selectedScene.text });
    userSession.messageHistory.push({ text: selectedOptionText });
    userSessions.set(userId, userSession);

    const battlePayload = {
      session_id: sessionId,
      battle_type: userSession.battleType,
      discord_id: userId,
      input: selectedOptionText
    };
    
    console.log(`[API] Sending POST to /battle:`, JSON.stringify(battlePayload, null, 2));
    const battleResponse = await axios.post(`${API_URL}/battle`, battlePayload);
    const battleResult = battleResponse.data;
    console.log(`[API] Response from /battle:`, JSON.stringify(battleResult, null, 2));

    // 5. 更新"处理中"消息为最终结果
    userSession.conversationCount += 1;
    userSessions.set(userId, userSession);

    const optionsAText = battleResult.response_a.options
      ? '\n\n**选项:**\n' + battleResult.response_a.options.map((opt, i) => `> **A${i + 1}:** ${opt}`).join('\n')
      : '';
    const modelAEmbed = new EmbedBuilder()
      .setColor(0x0099FF)
      .setTitle('模型 A 的回复')
      .setDescription(safeTruncateEmbed(battleResult.response_a.text + optionsAText))
      .setFooter({ text: `会话ID: ${sessionId} | 对话轮次: ${userSession.conversationCount}/${userSession.maxConversations}` });

    const optionsBText = battleResult.response_b.options
      ? '\n\n**选项:**\n' + battleResult.response_b.options.map((opt, i) => `> **B${i + 1}:** ${opt}`).join('\n')
      : '';
    const modelBEmbed = new EmbedBuilder()
      .setColor(0x00FF99)
      .setTitle('模型 B 的回复')
      .setDescription(safeTruncateEmbed(battleResult.response_b.text + optionsBText))
      .setFooter({ text: `会话ID: ${sessionId} | 对话轮次: ${userSession.conversationCount}/${userSession.maxConversations}` });

    const optionsARow = new ActionRowBuilder();
    if (battleResult.response_a.options) {
      battleResult.response_a.options.forEach((_, index) => {
        optionsARow.addComponents(
          new ButtonBuilder().setCustomId(`select_option:${sessionId}:A${index}`).setLabel(`A${index + 1}`).setStyle(ButtonStyle.Primary)
        );
      });
    }

    const optionsBRow = new ActionRowBuilder();
    if (battleResult.response_b.options) {
      battleResult.response_b.options.forEach((_, index) => {
        optionsBRow.addComponents(
          new ButtonBuilder().setCustomId(`select_option:${sessionId}:B${index}`).setLabel(`B${index + 1}`).setStyle(ButtonStyle.Success)
        );
      });
    }

    const viewModelsRow = new ActionRowBuilder()
      .addComponents(
        new ButtonBuilder().setCustomId(`reveal_models:${sessionId}:true`).setLabel('查看模型名称').setStyle(ButtonStyle.Secondary),
        new ButtonBuilder().setCustomId(`continue_battle:${sessionId}:new`).setLabel('结束并开始新对话').setStyle(ButtonStyle.Secondary)
      );

    const finalComponents = [];
    if (optionsARow.components.length > 0) finalComponents.push(optionsARow);
    if (optionsBRow.components.length > 0) finalComponents.push(optionsBRow);
    finalComponents.push(viewModelsRow);

    await loadingMessage.edit({
      content: `<@${userId}> 两个模型已生成回复，请选择下面的选项继续对话:`,
      embeds: [modelAEmbed, modelBEmbed],
      components: finalComponents,
      ephemeral: true
    });

  } catch (error) {
    console.error('处理初始选项选择时出错:', error.response ? JSON.stringify(error.response.data, null, 2) : error.message);
    // 即使出错，也尝试用 followUp 发送错误信息，因为 loadingMessage 可能已失效
    await interaction.followUp({
      content: `处理初始选项失败: ${error.response?.data?.detail || error.message}`,
      ephemeral: true
    });
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

// 处理选项选择按钮
async function handleOptionSelectionButton(interaction, sessionId, optionIndex) {
  await interaction.deferUpdate();
  
  // 获取用户ID
  const userId = sessionToUser.get(sessionId);
  if (!userId || userId !== interaction.user.id) {
    await interaction.followUp({
      content: '只有发起会话的用户才能选择回复选项。',
      flags: 'Ephemeral'
    });
    return;
  }
  
  // 获取会话信息
  const userSession = userSessions.get(userId);
  if (!userSession || userSession.sessionId !== sessionId || userSession.status !== 'ongoing') {
    await interaction.followUp({
      content: '会话状态已改变，无法选择回复选项。',
      flags: 'Ephemeral'
    });
    return;
  }
  
  try {
    // 获取选择的选项内容
    let selectedOption = '';
    const modelType = optionIndex.toString().startsWith('A') || optionIndex.toString().startsWith('B')
      ? optionIndex.toString().charAt(0)
      : null;
      
    if (modelType) {
      // 对话进行中，选择A或B模型的选项
      const optionIdx = parseInt(optionIndex.substring(1));
      const optionsEmbed = interaction.message.embeds.length > 2
        ? interaction.message.embeds[modelType === 'A' ? 2 : 3]
        : await interaction.fetchReply().then(msg =>
            msg.embeds.find(e => e.title?.includes(modelType === 'A' ? '模型 A 的回复选项' : '模型 B 的回复选项'))
          );
      
      if (optionsEmbed && optionsEmbed.fields && optionsEmbed.fields.length > optionIdx) {
        selectedOption = optionsEmbed.fields[optionIdx].value;
      }
    } else {
      // 初始选择，获取角色消息的选项
      const characterMessage = userSession.characterMessages[parseInt(optionIndex)];
      selectedOption = characterMessage.options[0]; // 直接使用第一个选项
    }
    
    if (!selectedOption) {
      console.error('无法获取选项内容');
      await interaction.followUp({
        content: '无法获取选项内容，请尝试重新选择。',
        flags: 'Ephemeral'
      });
      return;
    }
    
    // 向API发送battle请求，继续对话
    const payload = {
      session_id: sessionId,
      battle_type: userSession.battleType,
      discord_id: userId,
      input: selectedOption
    };
    
    console.log(`[API] Sending POST request to ${API_URL}/battle with payload:`, JSON.stringify(payload, null, 2));
    await interaction.editReply({
      content: `<@${userId}> 正在处理你的选择...`,
      embeds: [],
      components: []
    });
    
    const response = await axios.post(`${API_URL}/battle`, payload);
    const battle = response.data;
    console.log(`[API] Response from /battle:`, JSON.stringify(battle, null, 2));
    
    // 更新会话状态和对话轮次
    userSession.conversationCount += 1;
    userSession.messageHistory.push({ text: selectedOption });
    userSessions.set(userId, userSession);
    
    // 检查是否需要投票
    if (modelType) {
      // 如果是选择了特定模型的选项，发送投票
      const voteChoice = modelType === 'A' ? 'model_a' : 'model_b';
      try {
        // 获取当前battleId
        const battleId = battle.battle_id;
        
        // 发送投票
        await axios.post(`${API_URL}/vote/${battleId}`, {
          vote_choice: voteChoice,
          discord_id: userId
        });
        
        console.log(`[API] 为模型 ${voteChoice} 投票成功`);
      } catch (voteError) {
        console.error('投票失败:', voteError.message);
      }
    }
    
    // 创建显示模型回复的Embed
    const modelAEmbed = new EmbedBuilder()
      .setColor(0x0099FF)
      .setTitle('模型 A 的回复')
      .setDescription(safeTruncateEmbed(battle.response_a.text))
      .setFooter({ text: `会话ID: ${sessionId} | 对话轮次: ${userSession.conversationCount}/${userSession.maxConversations}` });
    
    const modelBEmbed = new EmbedBuilder()
      .setColor(0x00FF99)
      .setTitle('模型 B 的回复')
      .setDescription(safeTruncateEmbed(battle.response_b.text))
      .setFooter({ text: `会话ID: ${sessionId} | 对话轮次: ${userSession.conversationCount}/${userSession.maxConversations}` });
    
    // 创建选项按钮 - 模型A的选项
    const optionsARow = new ActionRowBuilder();
    battle.response_a.options.forEach((option, index) => {
      optionsARow.addComponents(
        new ButtonBuilder()
          .setCustomId(`select_option:${sessionId}:A${index}`)
          .setLabel(`A${index + 1}`)
          .setStyle(ButtonStyle.Primary)
      );
    });
    
    // 创建选项按钮 - 模型B的选项
    const optionsBRow = new ActionRowBuilder();
    battle.response_b.options.forEach((option, index) => {
      optionsBRow.addComponents(
        new ButtonBuilder()
          .setCustomId(`select_option:${sessionId}:B${index}`)
          .setLabel(`B${index + 1}`)
          .setStyle(ButtonStyle.Success)
      );
    });
    
    // 添加查看模型名称按钮
    const viewModelsRow = new ActionRowBuilder()
      .addComponents(
        new ButtonBuilder()
          .setCustomId(`reveal_models:${sessionId}:true`)
          .setLabel('查看模型名称')
          .setStyle(ButtonStyle.Secondary),
        new ButtonBuilder()
          .setCustomId(`reveal_models:${sessionId}:false`)
          .setLabel('不查看，继续对话')
          .setStyle(ButtonStyle.Secondary)
      );
    
    // 发送模型回复和选项
    await interaction.editReply({
      content: `<@${userId}> 两个模型已生成回复，请选择下一步操作:`,
      embeds: [modelAEmbed, modelBEmbed],
      components: [optionsARow, optionsBRow, viewModelsRow]
    });
    
    // 添加选项描述
    const optionsAEmbed = new EmbedBuilder()
      .setColor(0x0099FF)
      .setTitle('模型 A 的回复选项')
      .setDescription('');
    
    battle.response_a.options.forEach((option, index) => {
      optionsAEmbed.addFields({
        name: `A${index + 1}`,
        value: safeTruncateEmbed(option)
      });
    });
    
    const optionsBEmbed = new EmbedBuilder()
      .setColor(0x00FF99)
      .setTitle('模型 B 的回复选项')
      .setDescription('');
    
    battle.response_b.options.forEach((option, index) => {
      optionsBEmbed.addFields({
        name: `B${index + 1}`,
        value: safeTruncateEmbed(option)
      });
    });
    
    // 发送选项描述
    await interaction.followUp({
      embeds: [optionsAEmbed, optionsBEmbed],
      flags: 'Ephemeral'
    });
  } catch (error) {
    console.error('处理选项选择时出错:', error.response ? JSON.stringify(error.response.data, null, 2) : error.message);
    await interaction.followUp({
      content: `处理选项选择失败: ${error.response?.data?.detail || error.message}`,
      flags: 'Ephemeral'
    });
  }
}

// 处理查看模型名称按钮
async function handleRevealModelsButton(interaction, sessionId, choice) {
  await interaction.deferUpdate();
  
  // 获取用户ID
  const userId = sessionToUser.get(sessionId);
  if (!userId || userId !== interaction.user.id) {
    await interaction.followUp({
      content: '只有发起会话的用户才能查看模型名称。',
      flags: 'Ephemeral'
    });
    return;
  }
  
  // 获取会话信息
  const userSession = userSessions.get(userId);
  if (!userSession || userSession.sessionId !== sessionId || userSession.status !== 'ongoing') {
    await interaction.followUp({
      content: '会话状态已改变，无法执行此操作。',
      flags: 'Ephemeral'
    });
    return;
  }
  
  try {
    // 检查是否需要查看模型名称
    const revealModels = choice === 'true';
    
    // 如果是查看模型名称，则调用API
    if (revealModels) {
      // 获取当前battleId，这里假设可以从用户会话中获取
      const battleId = interaction.message.components[0].components[0].customId.split(':')[1];
      
      // 调用揭示模型API
      console.log(`[API] Sending POST request to ${API_URL}/reveal/${battleId}`);
      const response = await axios.post(`${API_URL}/reveal/${battleId}`);
      
      // 创建显示模型名称的Embed
      const modelsEmbed = new EmbedBuilder()
        .setColor(0xFFD700)
        .setTitle('🔍 模型名称揭晓')
        .setDescription('以下是参与本次对话的模型信息：')
        .addFields(
          { name: '模型 A', value: formatModelName(response.data.model_a_name), inline: true },
          { name: '模型 B', value: formatModelName(response.data.model_b_name), inline: true }
        )
        .setFooter({ text: `会话ID: ${sessionId} | 下次对话将重新分配模型` });
      
      // 更新会话状态，标记为已查看模型
      userSession.revealed = true;
      userSessions.set(userId, userSession);
      
      // 发送模型信息
      await interaction.editReply({
        content: `<@${userId}> 模型名称已揭晓：`,
        embeds: [modelsEmbed],
        components: []
      });
      
      // 添加继续对话按钮
      const continueButton = new ActionRowBuilder()
        .addComponents(
          new ButtonBuilder()
            .setCustomId(`continue_battle:${sessionId}:new`)
            .setLabel('开始新的对话')
            .setStyle(ButtonStyle.Primary)
        );
      
      await interaction.followUp({
        content: '请点击下方按钮继续对话：',
        components: [continueButton],
        flags: 'Ephemeral'
      });
    } else {
      // 如果不查看模型名称，检查是否达到最大对话轮次
      if (userSession.conversationCount >= userSession.maxConversations) {
        // 强制查看模型名称并重置会话
        await interaction.editReply({
          content: `<@${userId}> 已达到最大对话轮次(${userSession.maxConversations}次)，必须查看模型名称后才能继续。`,
          embeds: [],
          components: []
        });
        
        // 再次调用handleRevealModelsButton，但强制查看模型名称
        await handleRevealModelsButton(interaction, sessionId, 'true');
      } else {
        // 如果未达到最大轮次，可以继续对话
        await interaction.editReply({
          content: `<@${userId}> 你选择继续对话而不查看模型名称。请从上方选择一个选项继续。`,
          components: interaction.message.components.slice(0, 2) // 只保留选项按钮，移除查看模型名称按钮
        });
      }
    }
  } catch (error) {
    console.error('处理查看模型名称时出错:', error.response ? JSON.stringify(error.response.data, null, 2) : error.message);
    await interaction.followUp({
      content: `处理查看模型名称失败: ${error.response?.data?.detail || error.message}`,
      flags: 'Ephemeral'
    });
  }
}

// 处理继续对话按钮
async function handleContinueBattleButton(interaction, sessionId, choice) {
  await interaction.deferUpdate();
  
  // 获取用户ID
  const userId = sessionToUser.get(sessionId);
  if (!userId || userId !== interaction.user.id) {
    await interaction.followUp({
      content: '只有发起会话的用户才能继续对话。',
      flags: 'Ephemeral'
    });
    return;
  }
  
  // 获取会话信息
  const userSession = userSessions.get(userId);
  if (!userSession || userSession.sessionId !== sessionId) {
    await interaction.followUp({
      content: '会话状态已改变，无法继续对话。',
      flags: 'Ephemeral'
    });
    return;
  }
  
  try {
    // 如果达到最大对话轮次或已查看模型名称，需要创建新会话
    if (userSession.conversationCount >= userSession.maxConversations || userSession.revealed) {
      // 生成新的会话ID
      const newSessionId = crypto.randomUUID();
      
      // 重置用户会话信息
      userSessions.set(userId, {
        sessionId: newSessionId,
        battleType: userSession.battleType,
        conversationCount: 0,
        maxConversations: 5,
        status: 'initializing',
        authorId: userId,
        characterMessages: [],
        currentMessage: null,
        messageHistory: [],
        createdAt: new Date()
      });
      
      // 更新会话ID到用户ID的映射
      sessionToUser.set(newSessionId, userId);
      
      // 准备初始请求参数
      const payload = {
        session_id: newSessionId,
        battle_type: userSession.battleType,
        discord_id: userId,
        input: null
      };
      
      console.log(`[API] Sending POST request to ${API_URL}/battle with payload:`, JSON.stringify(payload, null, 2));
      await interaction.editReply({
        content: `<@${userId}> 正在创建新的对话会话...`,
        embeds: [],
        components: []
      });
      
      const response = await axios.post(`${API_URL}/battle`, payload);
      const battle = response.data;
      
      // 检查是否获取到了character_messages
      if (!battle.character_messages || battle.character_messages.length === 0) {
        await interaction.followUp({
          content: `<@${userId}> 未能获取到初始角色消息，请稍后重试。`,
          flags: 'Ephemeral'
        });
        return;
      }
      
      // 更新用户会话状态
      const newUserSession = userSessions.get(userId);
      newUserSession.status = 'character_selection';
      newUserSession.characterMessages = battle.character_messages;
      userSessions.set(userId, newUserSession);
      
      // 创建显示角色消息的Embed
      const embed = new EmbedBuilder()
        .setColor(0x0099FF)
        .setTitle('⚔️ 选择初始场景')
        .setDescription('请选择以下场景之一作为对话的开始：')
        .setFooter({ text: `会话ID: ${newSessionId} | 状态: 选择角色消息` });
      
      // 添加每个角色消息到Embed中
      battle.character_messages.forEach((msg, index) => {
        embed.addFields({
          name: `场景 ${index + 1}`,
          value: safeTruncateEmbed(msg.text)
        });
      });
      
      // 创建角色选择按钮
      const characterButtons = new ActionRowBuilder()
        .addComponents(
          battle.character_messages.map((_, index) =>
            new ButtonBuilder()
              .setCustomId(`select_character:${newSessionId}:${index}`)
              .setLabel(`选择场景 ${index + 1}`)
              .setStyle(ButtonStyle.Primary)
          )
        );
      
      // 发送包含角色选择的消息
      await interaction.editReply({
        content: `<@${userId}> 新的对话会话已创建：`,
        embeds: [embed],
        components: [characterButtons]
      });
    } else {
      // 如果没有达到最大对话轮次且未查看模型名称，继续当前会话
      await interaction.editReply({
        content: `<@${userId}> 你可以继续当前对话。请从上方选择一个选项继续。`,
        components: interaction.message.components.slice(0, 2) // 只保留选项按钮
      });
    }
  } catch (error) {
    console.error('处理继续对话时出错:', error.response ? JSON.stringify(error.response.data, null, 2) : error.message);
    await interaction.followUp({
      content: `处理继续对话失败: ${error.response?.data?.detail || error.message}`,
      flags: 'Ephemeral'
    });
  }
}

client.login(process.env.TOKEN);