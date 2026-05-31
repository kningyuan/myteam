import { Task, DeadlineWarning } from '../types';
import logger from '../utils/logger';

export class DeadlineWarningService {
  private warnings: DeadlineWarning[] = [];
  private warningThresholds = [7, 3, 1, 0];

  checkTasks(tasks: Task[]): DeadlineWarning[] {
    const now = new Date();
    this.warnings = [];

    for (const task of tasks) {
      if (!task.deadline || task.status === 'completed' || task.status === 'failed') continue;

      const deadline = new Date(task.deadline);
      const diffMs = deadline.getTime() - now.getTime();
      const daysRemaining = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

      let severity: DeadlineWarning['severity'];
      if (daysRemaining < 0) severity = 'overdue';
      else if (daysRemaining <= 1) severity = 'critical';
      else if (daysRemaining <= 3) severity = 'warning';
      else if (daysRemaining <= 7) severity = 'info';
      else continue;

      this.warnings.push({
        taskId: task.id,
        taskName: task.name,
        deadline,
        daysRemaining,
        severity,
      });
    }

    this.warnings.sort((a, b) => {
      const order = { overdue: 0, critical: 1, warning: 2, info: 3 };
      return order[a.severity] - order[b.severity];
    });

    return this.warnings;
  }

  getWarnings(): DeadlineWarning[] {
    return this.warnings;
  }

  getWarningCount(): number {
    return this.warnings.length;
  }
}
