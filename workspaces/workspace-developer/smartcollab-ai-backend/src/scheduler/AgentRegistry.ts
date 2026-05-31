import { v4 as uuidv4 } from 'uuid';
import { Agent, AgentStatus, AgentRole, CreateAgentOptions } from '../types';
import logger from '../utils/logger';

export class AgentRegistry {
  private agents: Map<string, Agent> = new Map();

  constructor() {
    this.seedMockAgents();
  }

  private seedMockAgents() {
    const mocks: Agent[] = [
      { id: 'agent-code-1', name: 'Code Agent', role: 'coding', status: 'online', description: '代码生成与审查', apiEndpoint: 'https://api.example.com/code/v1', avgResponseTime: 2.3, successRate: 98.5, projects: ['proj-1', 'proj-4'], createdAt: new Date() },
      { id: 'agent-review-1', name: 'Review Agent', role: 'review', status: 'online', description: '代码审查与建议', apiEndpoint: 'https://api.example.com/review/v1', avgResponseTime: 5.1, successRate: 96.2, projects: ['proj-4'], createdAt: new Date() },
      { id: 'agent-deploy-1', name: 'Deploy Agent', role: 'deploy', status: 'offline', description: '自动部署与发布', apiEndpoint: 'https://api.example.com/deploy/v1', avgResponseTime: 8.7, successRate: 92.1, projects: ['proj-1'], createdAt: new Date() },
      { id: 'agent-test-1', name: 'Test Agent', role: 'testing', status: 'online', description: '自动化测试执行', apiEndpoint: 'https://api.example.com/test/v1', avgResponseTime: 12.4, successRate: 94.7, projects: ['proj-1', 'proj-3'], createdAt: new Date() },
      { id: 'agent-research-1', name: 'Research Agent', role: 'research', status: 'busy', description: '信息检索与分析', apiEndpoint: 'https://api.example.com/research/v1', avgResponseTime: 15.2, successRate: 93.8, projects: ['proj-2'], createdAt: new Date() },
    ];
    for (const agent of mocks) {
      this.agents.set(agent.id, agent);
    }
  }

  registerAgent(options: CreateAgentOptions): Agent {
    const agent: Agent = {
      id: `agent_${uuidv4().slice(0, 8)}`,
      name: options.name,
      role: options.role,
      status: 'offline',
      description: options.description,
      apiEndpoint: options.apiEndpoint,
      avgResponseTime: 0,
      successRate: 100,
      projects: [],
      createdAt: new Date(),
    };
    this.agents.set(agent.id, agent);
    logger.info(`Agent registered: ${agent.id} - ${agent.name}`);
    return agent;
  }

  getAgent(id: string): Agent | undefined {
    return this.agents.get(id);
  }

  listAgents(filter?: { status?: AgentStatus; role?: AgentRole }): Agent[] {
    let results = Array.from(this.agents.values());
    if (filter?.status) results = results.filter((a) => a.status === filter.status);
    if (filter?.role) results = results.filter((a) => a.role === filter.role);
    return results;
  }

  updateAgent(id: string, updates: Partial<Agent>): Agent | null {
    const agent = this.agents.get(id);
    if (!agent) return null;
    Object.assign(agent, updates);
    return agent;
  }

  deleteAgent(id: string): boolean {
    return this.agents.delete(id);
  }

  getStats() {
    const all = Array.from(this.agents.values());
    return {
      total: all.length,
      online: all.filter((a) => a.status === 'online').length,
      offline: all.filter((a) => a.status === 'offline').length,
      busy: all.filter((a) => a.status === 'busy').length,
      avgSuccessRate: all.length > 0 ? all.reduce((s, a) => s + a.successRate, 0) / all.length : 0,
    };
  }
}