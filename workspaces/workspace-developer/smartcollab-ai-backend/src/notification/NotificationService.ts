import { v4 as uuidv4 } from 'uuid';
import { Notification, NotificationType, NotificationConfig } from '../types';
import logger from '../utils/logger';

/**
 * 通知系统 - 支持 Telegram、状态变更、错误告警
 */
export class NotificationService {
  private notifications: Notification[] = [];
  private config: NotificationConfig;
  private telegramClient?: TelegramClient;

  constructor(config: NotificationConfig) {
    this.config = config;
    
    if (config.telegramBotToken && config.telegramChatId) {
      this.telegramClient = new TelegramClient(config.telegramBotToken, config.telegramChatId);
    }
  }

  /**
   * 发送通知
   */
  async sendNotification(
    type: NotificationType,
    title: string,
    message: string,
    taskId?: string,
    data?: Record<string, unknown>
  ): Promise<Notification> {
    const notification: Notification = {
      id: `notif_${uuidv4().slice(0, 8)}`,
      type,
      title,
      message,
      taskId,
      data,
      createdAt: new Date(),
      read: false,
    };

    this.notifications.push(notification);
    
    // 发送 Telegram 通知
    if (this.telegramClient && this.config.telegramBotToken) {
      try {
        await this.telegramClient.sendMessage(this.formatTelegramMessage(notification));
        logger.info(`Telegram notification sent: ${notification.id}`);
      } catch (error) {
        logger.error(`Failed to send Telegram notification: ${error}`);
      }
    }

    logger.info(`Notification created: ${notification.id} - ${type}`);
    
    return notification;
  }

  /**
   * 任务开始通知
   */
  async notifyTaskStart(taskId: string, taskName: string): Promise<Notification> {
    return this.sendNotification(
      'task_start',
      '任务开始',
      `任务 "${taskName}" 已开始执行`,
      taskId
    );
  }

  /**
   * 任务完成通知
   */
  async notifyTaskComplete(taskId: string, taskName: string, success: boolean): Promise<Notification> {
    return this.sendNotification(
      success ? 'task_complete' : 'task_failed',
      success ? '任务完成' : '任务失败',
      success 
        ? `任务 "${taskName}" 已成功完成`
        : `任务 "${taskName}" 执行失败`,
      taskId
    );
  }

  /**
   * 任务超时通知
   */
  async notifyTaskTimeout(taskId: string, taskName: string): Promise<Notification> {
    return this.sendNotification(
      'task_timeout',
      '任务超时',
      `任务 "${taskName}" 执行超时`,
      taskId
    );
  }

  /**
   * 状态变更通知
   */
  async notifyStatusChange(
    taskId: string,
    taskName: string,
    oldStatus: string,
    newStatus: string
  ): Promise<Notification> {
    return this.sendNotification(
      'status_change',
      '状态变更',
      `任务 "${taskName}" 状态从 ${oldStatus} 变更为 ${newStatus}`,
      taskId
    );
  }

  /**
   * 错误告警
   */
  async notifyError(
    title: string,
    message: string,
    data?: Record<string, unknown>
  ): Promise<Notification> {
    return this.sendNotification(
      'error_alert',
      '错误告警',
      message,
      undefined,
      { ...data, title }
    );
  }

  /**
   * 获取通知列表
   */
  getNotifications(options?: { limit?: number; unreadOnly?: boolean }): Notification[] {
    let results = [...this.notifications];
    
    if (options?.unreadOnly) {
      results = results.filter(n => !n.read);
    }
    
    // 按时间倒序
    results.sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime());
    
    if (options?.limit) {
      results = results.slice(0, options.limit);
    }
    
    return results;
  }

  /**
   * 标记通知已读
   */
  markAsRead(notificationId: string): boolean {
    const notification = this.notifications.find(n => n.id === notificationId);
    if (!notification) return false;
    
    notification.read = true;
    return true;
  }

  /**
   * 格式化 Telegram 消息
   */
  private formatTelegramMessage(notification: Notification): string {
    const emojiMap: Record<NotificationType, string> = {
      task_start: '🚀',
      task_complete: '✅',
      task_failed: '❌',
      task_timeout: '⏰',
      status_change: '📊',
      error_alert: '🔴',
    };

    const emoji = emojiMap[notification.type] || '📢';
    let message = `${emoji} *${notification.title}*\n\n${notification.message}`;
    
    if (notification.taskId) {
      message += `\n\n任务ID: \`${notification.taskId}\``;
    }
    
    return message;
  }
}

/**
 * Telegram 客户端（简化实现）
 */
class TelegramClient {
  private botToken: string;
  private chatId: string;
  private baseUrl = 'https://api.telegram.org/bot';

  constructor(botToken: string, chatId: string) {
    this.botToken = botToken;
    this.chatId = chatId;
  }

  /**
   * 发送消息
   */
  async sendMessage(text: string): Promise<boolean> {
    // 简化实现：实际应调用 Telegram API
    // const url = `${this.baseUrl}${this.botToken}/sendMessage`;
    // const response = await fetch(url, {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify({
    //     chat_id: this.chatId,
    //     text,
    //     parse_mode: 'Markdown',
    //   }),
    // });
    // return response.ok;
    
    logger.debug(`[Telegram Mock] Sending message to ${this.chatId}: ${text.slice(0, 50)}...`);
    return true;
  }
}

export default NotificationService;
