import { v4 as uuidv4 } from 'uuid';
import { Workflow, WorkflowNode, WorkflowEdge, CreateWorkflowOptions, WorkflowStatus, NodeStatus, ExecutionRecord, ExecutionStatus } from '../types';
import logger from '../utils/logger';

export class WorkflowEngine {
  private workflows: Map<string, Workflow> = new Map();
  private executions: Map<string, ExecutionRecord> = new Map();

  createWorkflow(options: CreateWorkflowOptions): Workflow {
    const workflow: Workflow = {
      id: `wf_${uuidv4().slice(0, 8)}`,
      projectId: options.projectId,
      name: options.name,
      description: options.description,
      status: 'draft',
      nodes: options.nodes || [],
      edges: options.edges || [],
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    this.workflows.set(workflow.id, workflow);
    logger.info(`Workflow created: ${workflow.id} - ${workflow.name}`);
    return workflow;
  }

  getWorkflow(id: string): Workflow | undefined {
    return this.workflows.get(id);
  }

  listWorkflows(projectId?: string): Workflow[] {
    const all = Array.from(this.workflows.values());
    return projectId ? all.filter((w) => w.projectId === projectId) : all;
  }

  updateWorkflow(id: string, updates: Partial<Workflow>): Workflow | null {
    const wf = this.workflows.get(id);
    if (!wf) return null;
    Object.assign(wf, updates, { updatedAt: new Date() });
    this.workflows.set(id, wf);
    return wf;
  }

  deleteWorkflow(id: string): boolean {
    return this.workflows.delete(id);
  }

  addNode(workflowId: string, node: Omit<WorkflowNode, 'id' | 'status'>): Workflow | null {
    const wf = this.workflows.get(workflowId);
    if (!wf) return null;
    const newNode: WorkflowNode = { ...node, id: `node_${uuidv4().slice(0, 6)}`, status: 'idle' };
    wf.nodes.push(newNode);
    wf.updatedAt = new Date();
    return wf;
  }

  updateNodeStatus(workflowId: string, nodeId: string, status: NodeStatus): Workflow | null {
    const wf = this.workflows.get(workflowId);
    if (!wf) return null;
    const node = wf.nodes.find((n) => n.id === nodeId);
    if (!node) return null;
    node.status = status;
    wf.updatedAt = new Date();
    return wf;
  }

  // 拓扑排序 - 确定节点执行顺序
  topologicalSort(workflowId: string): string[] | null {
    const wf = this.workflows.get(workflowId);
    if (!wf) return null;

    const adj = new Map<string, string[]>();
    const inDegree = new Map<string, number>();

    for (const node of wf.nodes) {
      adj.set(node.id, []);
      inDegree.set(node.id, 0);
    }
    for (const edge of wf.edges) {
      adj.get(edge.source)?.push(edge.target);
      inDegree.set(edge.target, (inDegree.get(edge.target) || 0) + 1);
    }

    const queue: string[] = [];
    for (const [nodeId, deg] of inDegree) {
      if (deg === 0) queue.push(nodeId);
    }

    const result: string[] = [];
    while (queue.length > 0) {
      const node = queue.shift()!;
      result.push(node);
      for (const neighbor of adj.get(node) || []) {
        const newDeg = (inDegree.get(neighbor) || 0) - 1;
        inDegree.set(neighbor, newDeg);
        if (newDeg === 0) queue.push(neighbor);
      }
    }

    if (result.length !== wf.nodes.length) {
      logger.warn(`Workflow ${workflowId} has a cycle - topological sort incomplete`);
      return null;
    }
    return result;
  }

  // 发布工作流
  publishWorkflow(workflowId: string): Workflow | null {
    const wf = this.workflows.get(workflowId);
    if (!wf) return null;
    if (wf.nodes.length === 0) {
      logger.warn(`Cannot publish workflow ${workflowId}: no nodes`);
      return null;
    }
    const order = this.topologicalSort(workflowId);
    if (!order) return null;

    wf.status = 'published';
    wf.updatedAt = new Date();
    return wf;
  }

  // 创建工作流执行记录
  startExecution(workflowId: string, projectName: string): ExecutionRecord | null {
    const wf = this.workflows.get(workflowId);
    if (!wf || wf.status !== 'published') return null;

    const nodeStatuses: Record<string, NodeStatus> = {};
    for (const node of wf.nodes) {
      nodeStatuses[node.id] = 'idle';
    }

    const exec: ExecutionRecord = {
      id: `exec_${uuidv4().slice(0, 8)}`,
      workflowId,
      workflowName: wf.name,
      projectName,
      status: 'running',
      progress: 0,
      startedAt: new Date(),
      nodeStatuses,
    };

    wf.status = 'running';
    this.executions.set(exec.id, exec);
    logger.info(`Execution started: ${exec.id} for workflow ${workflowId}`);
    return exec;
  }

  updateExecutionProgress(execId: string, nodeId: string, status: NodeStatus): ExecutionRecord | null {
    const exec = this.executions.get(execId);
    if (!exec) return null;

    exec.nodeStatuses[nodeId] = status;
    const total = Object.keys(exec.nodeStatuses).length;
    const completed = Object.values(exec.nodeStatuses).filter(
      (s) => s === 'completed' || s === 'failed' || s === 'skipped'
    ).length;
    exec.progress = total > 0 ? Math.round((completed / total) * 100) : 0;

    const allDone = Object.values(exec.nodeStatuses).every(
      (s) => s === 'completed' || s === 'failed' || s === 'skipped'
    );
    if (allDone) {
      exec.status = exec.progress === 100 ? 'completed' : 'failed';
      exec.completedAt = new Date();
      const ms = exec.completedAt.getTime() - exec.startedAt.getTime();
      exec.duration = ms < 60000 ? `${Math.round(ms / 1000)}s` : `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
    }

    return exec;
  }

  getExecution(id: string): ExecutionRecord | undefined {
    return this.executions.get(id);
  }

  listExecutions(status?: ExecutionStatus): ExecutionRecord[] {
    const all = Array.from(this.executions.values());
    return status ? all.filter((e) => e.status === status) : all;
  }

  getStats() {
    const all = Array.from(this.executions.values());
    return {
      running: all.filter((e) => e.status === 'running').length,
      completed: all.filter((e) => e.status === 'completed').length,
      failed: all.filter((e) => e.status === 'failed').length,
      total: all.length,
    };
  }
}