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

async function handleCommand(interaction) {
  if (interaction.commandName === 'battle') {
    // 用户/角色白名单检查
    if (!isMemberAllowed(interaction)) {
      const tips = (ALLOWED_USER_IDS.size || ALLOWED_ROLE_IDS.size)
        ? `此命令仅限以下用户/角色使用：${allowedUserRoleMentions()}`
        : '此命令暂不可用。';
      if (!interaction.deferred && !interaction.replied) {
        await interaction.reply({ content: tips, ephemeral: true });
      } else {
        await interaction.followUp({ content: tips, ephemeral: true });
      }
      return;
    }

    // 频道白名单检查
    if (!isChannelAllowed(interaction.channelId)) {
      const tips = ALLOWED_CHANNEL_IDS.size
        ? `此命令仅限在以下频道使用：${allowedMentionList()}`
        : '此命令暂不可用。';
      if (!interaction.deferred && !interaction.replied) {
        await interaction.reply({ content: tips, ephemeral: true });
      } else {
        await interaction.followUp({ content: tips, ephemeral: true });
      }
      return;
    }
    try {
      // 需求变更：所有命令响应仅发起人可见
      await interaction.deferReply({ ephemeral: true });

      const response = await axios.post(`${API_URL}/battle`, {
        battle_type: 'fixed',
      });

      const battle = response.data;
      // 存储对战信息和发起者的ID
      activeBattles.set(battle.battle_id, {
        ...battle,
        authorId: interaction.user.id
      });

      const statusRaw = battle.status;
      const statusDisplay = (!statusRaw || statusRaw === 'pending_vote') ? '等待投票' : statusRaw;

      const embed = new EmbedBuilder()
        .setColor(0x0099FF)
        .setTitle('⚔️ 新的对战！')
        .setDescription(`**提示词:**\n> ${battle.prompt}`)
        .addFields(
          { name: '模型 A 的回答', value: `\`\`\`${battle.response_a}\`\`\``, inline: false },
          { name: '模型 B 的回答', value: `\`\`\`${battle.response_b}\`\`\``, inline: false }
        )
        .setFooter({ text: `对战 ID: ${battle.battle_id}\n状态: ${statusDisplay}` });

      const row = new ActionRowBuilder()
        .addComponents(
          new ButtonBuilder()
            .setCustomId(`vote:${battle.battle_id}:model_a`)
            .setLabel('投给模型 A')
            .setStyle(ButtonStyle.Primary),
          new ButtonBuilder()
            .setCustomId(`vote:${battle.battle_id}:model_b`)
            .setLabel('投给模型 B')
            .setStyle(ButtonStyle.Primary),
          new ButtonBuilder()
            .setCustomId(`vote:${battle.battle_id}:tie`)
            .setLabel('平局')
            .setStyle(ButtonStyle.Secondary)
        );

      // 需求变更：所有命令响应仅发起人可见
      await interaction.editReply({ embeds: [embed], components: [row] });

    } catch (error) {
      console.error('创建对战时出错:', error);
      if (!interaction.replied && !interaction.deferred) {
        await interaction.reply({ content: '创建对战失败，请稍后再试。', ephemeral: true });
      } else {
        await interaction.editReply({ content: '创建对战失败，请稍后再试。' });
      }
    }
  } else if (interaction.commandName === 'leaderboard') {
    // 频道白名单检查
    if (!isChannelAllowed(interaction.channelId)) {
      const tips = ALLOWED_CHANNEL_IDS.size
        ? `此命令仅限在以下频道使用：${allowedMentionList()}`
        : '此命令暂不可用。';
      if (!interaction.deferred && !interaction.replied) {
        await interaction.reply({ content: tips, ephemeral: true });
      } else {
        await interaction.followUp({ content: tips, ephemeral: true });
      }
      return;
    }
    try {
        // 需求变更：所有命令响应仅发起人可见
        await interaction.deferReply({ ephemeral: true });
        const response = await axios.get(`${API_URL}/leaderboard`);
        const { leaderboard } = response.data;

        if (!leaderboard || leaderboard.length === 0) {
            await interaction.editReply({ content: '排行榜当前为空。' });
            return;
        }

        const embed = new EmbedBuilder()
            .setColor(0xFFD700)
            .setTitle('🏆 模型排行榜')
            .setTimestamp();

        let description = '';
        leaderboard.forEach(model => {
            description += `**${model.rank}. ${model.model_name}**\n`;
            description += `> **评分:** ${model.rating}\n`;
            description += `> **胜率:** ${model.win_rate_percentage.toFixed(2)}%\n`;
            description += `> **对战数:** ${model.battles} (胜: ${model.wins}, 平: ${model.ties})\n\n`;
        });

        embed.setDescription(description);

        // 需求变更：所有命令响应仅发起人可见
        await interaction.editReply({ embeds: [embed] });

    } catch (error) {
        console.error('获取排行榜时出错:', error);
        if (!interaction.replied && !interaction.deferred) {
            await interaction.reply({ content: '获取排行榜失败，请稍后再试。', ephemeral: true });
        } else {
            await interaction.editReply({ content: '获取排行榜失败，请稍后再试。' });
        }
    }
  }
}

async function handleButton(interaction) {
  // 使用 : 作为分隔符，避免与 model_a 中的 _ 冲突
  const [action, battleId, choice] = interaction.customId.split(':');

  if (action !== 'vote') return;

  // 频道白名单检查（按钮）
  if (!isChannelAllowed(interaction.channelId)) {
    const tips = ALLOWED_CHANNEL_IDS.size
      ? `此投票仅限在以下频道进行：${allowedMentionList()}`
      : '此投票暂不可用。';
    if (!interaction.deferred && !interaction.replied) {
      await interaction.reply({ content: tips, ephemeral: true });
    } else {
      await interaction.followUp({ content: tips, ephemeral: true });
    }
    return;
  }

  // 无感优化：一次性确认并原地编辑为“处理中”（更快、更丝滑）
  try {
    const originalEmbed = interaction.message.embeds[0];
    const processingEmbed = new EmbedBuilder(originalEmbed?.toJSON?.() ?? {})
      .setColor(0x5865F2) // blurple
      .setFooter({ text: `对战 ID: ${battleId}\n状态: 处理中...` });

    const processingRows = interaction.message.components.map(row => {
      const newRow = new ActionRowBuilder();
      row.components.forEach(comp => newRow.addComponents(ButtonBuilder.from(comp).setDisabled(true)));
      return newRow;
    });

    // interaction.update 会同时 ack 交互并原地编辑消息，比 deferUpdate+edit 更快
    await interaction.update({
      embeds: [processingEmbed],
      components: processingRows
    });
  } catch (preEditErr) {
    console.error('预处理编辑失败:', preEditErr);
  }

  const battleInfo = activeBattles.get(battleId);
  if (!battleInfo) {
    // 原地编辑原始临时消息为失败状态（不发送新消息）
    const originalEmbed = interaction.message.embeds[0];
    const updatedEmbed = new EmbedBuilder(originalEmbed?.toJSON?.() ?? {})
      .setColor(0xED4245)
      .setFooter({ text: `对战 ID: ${battleId}\n状态: 投票失败` })
      .addFields({ name: '投票失败', value: '找不到这场对战的信息，它可能已经过期或已完成。', inline: false });

    await interaction.webhook.editMessage(interaction.message.id, { embeds: [updatedEmbed] });
    return;
  }

  // 检查点击者是否为发起者
  if (interaction.user.id !== battleInfo.authorId) {
    // 原地编辑原始临时消息为失败状态（不发送新消息）
    const originalEmbed = interaction.message.embeds[0];
    const updatedEmbed = new EmbedBuilder(originalEmbed?.toJSON?.() ?? {})
      .setColor(0xED4245)
      .setFooter({ text: `对战 ID: ${battleId}\n状态: 投票失败` })
      .addFields({ name: '投票失败', value: '抱歉，只有发起这场对战的用户才能投票。', inline: false });

    await interaction.webhook.editMessage(interaction.message.id, { embeds: [updatedEmbed] });
    return;
  }

  try {
    const payload = {
      vote_choice: choice,
      discord_id: interaction.user.id
    };

    console.log(`向 /vote/${battleId} 发送请求体:`, JSON.stringify(payload, null, 2));
    const response = await axios.post(`${API_URL}/vote/${battleId}`, payload);
    const voteResult = response.data;

    if (voteResult.status === 'success') {
      // 成功后直接“编辑原始临时消息”
      activeBattles.delete(battleId);

      const originalEmbed = interaction.message.embeds[0];
      const updatedEmbed = new EmbedBuilder(originalEmbed.toJSON())
        .setColor(0x57F287)
        .setTitle('⚔️ 已完成的对战！')
        .setFooter({ text: `对战 ID: ${battleId}\n状态: 已完成 | 获胜者: ${voteResult.winner}` })
        .spliceFields(
          0,
          2,
          {
            name: `模型 A (${voteResult.model_a_name}) 的回答`,
            value: battleInfo.response_a ? `\`\`\`${battleInfo.response_a}\`\`\`` : (originalEmbed.fields?.[0]?.value ?? 'N/A'),
            inline: false
          },
          {
            name: `模型 B (${voteResult.model_b_name}) 的回答`,
            value: battleInfo.response_b ? `\`\`\`${battleInfo.response_b}\`\`\`` : (originalEmbed.fields?.[1]?.value ?? 'N/A'),
            inline: false
          }
        );

      // 将所有按钮禁用
      const disabledRows = interaction.message.components.map(row => {
        const newRow = new ActionRowBuilder();
        row.components.forEach(comp => newRow.addComponents(ButtonBuilder.from(comp).setDisabled(true)));
        return newRow;
      });

      await interaction.webhook.editMessage(interaction.message.id, { embeds: [updatedEmbed], components: disabledRows });

    } else {
      // 业务错误：编辑原始临时消息以显示失败原因（不发送新消息）
      const originalEmbed = interaction.message.embeds[0];
      const updatedEmbed = new EmbedBuilder(originalEmbed.toJSON())
        .setColor(0xED4245)
        .setFooter({ text: `对战 ID: ${battleId}\n状态: 投票失败` })
        .addFields({ name: '投票失败', value: voteResult.message || '未知原因', inline: false });

      await interaction.webhook.editMessage(interaction.message.id, { embeds: [updatedEmbed] });
    }

  } catch (error) {
    console.error(`为对战 ${battleId} 投票时出错:`, error.response ? error.response.data : error.message);
    const detail = error?.response?.data?.detail || error?.response?.data?.message || error?.message || '未知错误';

    // 编辑原始临时消息，显示错误信息
    const originalEmbed = interaction.message.embeds[0];
    const updatedEmbed = new EmbedBuilder(originalEmbed.toJSON())
      .setColor(0xED4245)
      .setFooter({ text: `对战 ID: ${battleId}\n状态: 投票失败` })
      .addFields({ name: '投票失败', value: String(detail), inline: false });

    await interaction.webhook.editMessage(interaction.message.id, { embeds: [updatedEmbed] });
  }
}

client.login(process.env.TOKEN);