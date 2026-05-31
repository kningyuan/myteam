import React, { useCallback, useState } from 'react';
import { ReactFlow, Background, Controls, MiniMap, useNodesState, useEdgesState, addEdge, type Connection, type Node, type Edge, Handle, Position } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useAppStore } from '../store/appStore';
import { Play, Save, Download, ZoomIn, ZoomOut, Hand, MousePointer2, Plus, Settings, X, Bot, ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface CustomNodeData {
  label: string;
  agent: string;
  status: string;
}

const statusColors: Record<string, string> = {
  idle: '#334155',
  running: '#F59E0B',
  completed: '#10B981',
  failed: '#EF4444',
  skipped: '#6B7280',
};

function CustomNode({ data, selected }: { data: CustomNodeData; selected: boolean }) {
  const status = data.status as string || 'idle';
  return (
    <div className={`relative bg-[var(--color-bg-secondary)] border-2 rounded-xl px-4 py-3 min-w-[160px] shadow-lg transition-all ${selected ? 'border-indigo-500 shadow-indigo-500/20' : 'border-[var(--color-border)]'}`}>
      <div className="absolute top-0 left-0 right-0 h-1 rounded-t-xl" style={{ background: statusColors[status] }} />
      <div className="flex items-center gap-2 mt-1">
        <Bot className="w-4 h-4 text-indigo-400" />
        <span className="text-sm font-semibold text-[var(--color-text-primary)]">{data.label as string}</span>
      </div>
      <div className="text-xs text-[var(--color-text-tertiary)] mt-1">Agent: {data.agent as string}</div>
      <Handle type="target" position={Position.Left} className="!bg-[var(--color-border)] !w-3 !h-3 !border-2 !border-[var(--color-bg)]" />
      <Handle type="source" position={Position.Right} className="!bg-[var(--color-border)] !w-3 !h-3 !border-2 !border-[var(--color-bg)]" />
    </div>
  );
}

const nodeTypes = { custom: CustomNode };

const initialNodes: Node[] = [
  { id: '1', type: 'custom', position: { x: 50, y: 100 }, data: { label: '代码审查', agent: 'Code Agent', status: 'completed' } },
  { id: '2', type: 'custom', position: { x: 300, y: 50 }, data: { label: '代码审查', agent: 'Review Agent', status: 'running' } },
  { id: '3', type: 'custom', position: { x: 300, y: 200 }, data: { label: '自动化测试', agent: 'Test Agent', status: 'idle' } },
  { id: '4', type: 'custom', position: { x: 550, y: 125 }, data: { label: '部署发布', agent: 'Deploy Agent', status: 'idle' } },
];

const initialEdges: Edge[] = [
  { id: 'e1-2', source: '1', target: '2', animated: true, style: { stroke: '#6366F1', strokeWidth: 2 }, label: '通过' },
  { id: 'e1-3', source: '1', target: '3', animated: true, style: { stroke: '#6366F1', strokeWidth: 2, strokeDasharray: '6 4' }, label: '需测试' },
  { id: 'e2-4', source: '2', target: '4', style: { stroke: '#475569', strokeWidth: 2 }, label: '审查通过' },
  { id: 'e3-4', source: '3', target: '4', style: { stroke: '#475569', strokeWidth: 2 }, label: '测试通过' },
];

export default function WorkflowEditor() {
  const navigate = useNavigate();
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [tool, setTool] = useState<'pointer' | 'hand'>('pointer');

  const onConnect = useCallback((params: Connection) => setEdges((eds) => addEdge(params, eds)), [setEdges]);

  const onNodeClick = (_: React.MouseEvent, node: Node) => setSelectedNode(node);

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/')} className="p-2 rounded-lg text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-lg font-semibold text-[var(--color-text-primary)]">代码审查工作流</h1>
            <p className="text-xs text-[var(--color-text-tertiary)]">4 节点 · 4 连接 · 最后编辑 2 分钟前</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button className="h-8 px-3 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] transition-colors flex items-center gap-1.5">
            <Save className="w-4 h-4" /> 保存草稿
          </button>
          <button className="h-8 px-3 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-1.5">
            <Play className="w-4 h-4" /> 发布
          </button>
        </div>
      </div>

      <div className="flex-1 flex gap-4 min-h-0">
        {/* Tool panel */}
        <div className="w-12 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-xl flex flex-col items-center py-3 gap-2 flex-shrink-0">
          <button onClick={() => setTool('pointer')} className={`p-2 rounded-lg transition-colors ${tool === 'pointer' ? 'bg-indigo-500/10 text-indigo-400' : 'text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]'}`}>
            <MousePointer2 className="w-4 h-4" />
          </button>
          <button onClick={() => setTool('hand')} className={`p-2 rounded-lg transition-colors ${tool === 'hand' ? 'bg-indigo-500/10 text-indigo-400' : 'text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]'}`}>
            <Hand className="w-4 h-4" />
          </button>
          <div className="w-6 border-t border-[var(--color-border)] my-1" />
          <button className="p-2 rounded-lg text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-tertiary)] transition-colors">
            <Plus className="w-4 h-4" />
          </button>
          <button className="p-2 rounded-lg text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-tertiary)] transition-colors">
            <ZoomIn className="w-4 h-4" />
          </button>
          <button className="p-2 rounded-lg text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-tertiary)] transition-colors">
            <ZoomOut className="w-4 h-4" />
          </button>
          <div className="w-6 border-t border-[var(--color-border)] my-1" />
          <button className="p-2 rounded-lg text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-tertiary)] transition-colors">
            <Download className="w-4 h-4" />
          </button>
        </div>

        {/* Canvas */}
        <div className="flex-1 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-xl overflow-hidden">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onPaneClick={() => setSelectedNode(null)}
            nodeTypes={nodeTypes}
            fitView
            panOnDrag={tool === 'hand'}
            zoomOnScroll
            selectionOnDrag={tool === 'pointer'}
          >
            <Background color="#334155" gap={20} size={1} />
            <Controls className="!bg-[var(--color-bg-secondary)] !border-[var(--color-border)] !rounded-lg [&_button]:!text-[var(--color-text-secondary)] [&_button]:!border-[var(--color-border)] [&_button]:!hover:bg-[var(--color-bg-tertiary)]" />
            <MiniMap
              className="!border-[var(--color-border)] !rounded-lg"
              nodeColor={() => '#334155'}
              maskColor="rgba(15,23,42,0.8)"
              style={{ background: '#1E293B' }}
            />
          </ReactFlow>
        </div>

        {/* Config panel */}
        {selectedNode && (
          <div className="w-72 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-xl p-4 flex-shrink-0">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-sm text-[var(--color-text-primary)]">节点配置</h3>
              <button onClick={() => setSelectedNode(null)} className="text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1">名称</label>
                <input defaultValue={selectedNode.data.label as string}
                  className="w-full h-8 px-3 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1">Agent</label>
                <select defaultValue={selectedNode.data.agent as string}
                  className="w-full h-8 px-3 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-indigo-500">
                  <option>Code Agent</option>
                  <option>Review Agent</option>
                  <option>Test Agent</option>
                  <option>Deploy Agent</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1">提示词</label>
                <textarea rows={4} placeholder="输入 Agent 的指令..."
                  className="w-full px-3 py-2 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-tertiary)] focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none" />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1">超时</label>
                <select className="w-full h-8 px-3 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-indigo-500">
                  <option>30 秒</option>
                  <option>1 分钟</option>
                  <option>5 分钟</option>
                  <option>15 分钟</option>
                </select>
              </div>
              <button className="w-full h-8 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-medium rounded-lg transition-colors">
                保存配置
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Status bar */}
      <div className="flex items-center gap-4 mt-3 px-3 py-2 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg text-xs text-[var(--color-text-tertiary)] flex-shrink-0">
        <span>4 节点</span>
        <span>4 连接</span>
        <span>自动布局</span>
        <span className="ml-auto">缩放: 100%</span>
        <span>网格对齐</span>
      </div>
    </div>
  );
}