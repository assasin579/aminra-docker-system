"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useUserAuth } from "@/components/UserAuthContext";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Panel,
  useNodesState,
  useEdgesState,
  addEdge,
  type Node,
  type Edge,
  type Connection,
  type NodeTypes,
  Handle,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import Modal from "@/components/Modal";

// ── Types ────────────────────────────────────────────────────────────────────

interface ProcessTemplate {
  id: string;
  name: string;
  description: string | null;
  flowchart: { nodes: FlowNode[]; edges: FlowEdge[] };
  version: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface FlowNode {
  id: string;
  type: "main" | "sub";
  order?: number;
  label: string;
  description?: string;
  standard?: string;
  responsible?: string;
  duration?: string;
  equipment?: string;
  conditions?: string;
  checklist?: string[];
  notes?: string;
  x: number;
  y: number;
  parent?: string;
  children?: string[];
}

interface FlowEdge {
  from: string;
  to: string;
  type: "sequential" | "parallel";
}

// ── Custom Node ──────────────────────────────────────────────────────────────

function StepNode({
  data,
  selected,
}: {
  data: { label: string; nodeType: string; order?: number };
  selected: boolean;
}) {
  const isMain = data.nodeType === "main";
  return (
    <div
      className="rounded-xl px-4 py-3 min-w-[160px] transition-shadow"
      style={{
        background: isMain ? "#FFFFFF" : "#FFFFFF",
        border: `2px solid ${selected ? "#0A1F44" : isMain ? "#E2E8F0" : "#F5F1E8"}`,
        boxShadow: selected
          ? "0 0 0 3px rgba(10,31,68,0.15)"
          : "0 1px 4px rgba(0,0,0,0.06)",
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        style={{ background: "#0A1F44", width: 8, height: 8 }}
      />
      <div className="flex items-center gap-2">
        {data.order != null && (
          <span
            className="w-6 h-6 rounded-full grid place-items-center text-xs font-bold text-white flex-shrink-0"
            style={{ background: isMain ? "#0A1F44" : "#9CA3AF" }}
          >
            {data.order}
          </span>
        )}
        <div>
          <span className="text-xs font-bold" style={{ color: "#0A1F44" }}>
            {data.label}
          </span>
          <div className="text-xs mt-0.5" style={{ color: "#9CA3AF" }}>
            {isMain ? "Bước chính" : "Bước phụ"}
          </div>
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: "#0A1F44", width: 8, height: 8 }}
      />
    </div>
  );
}

const nodeTypes: NodeTypes = { stepNode: StepNode };

// ── Helpers ──────────────────────────────────────────────────────────────────

function flowToReact(
  nodes: FlowNode[],
  edges: FlowEdge[],
): { rfNodes: Node[]; rfEdges: Edge[] } {
  const rfNodes: Node[] = nodes.map((n, i) => ({
    id: n.id,
    type: "stepNode",
    position: { x: n.x || 100, y: n.y || i * 120 },
    data: { label: n.label, nodeType: n.type, order: n.order ?? i + 1, ...n },
  }));
  const rfEdges: Edge[] = edges.map((e, i) => ({
    id: `e-${i}`,
    source: e.from,
    target: e.to,
    type: "smoothstep",
    animated: e.type === "parallel",
    style: {
      stroke: e.type === "parallel" ? "#B45309" : "#0A1F44",
      strokeWidth: 2,
    },
    label: e.type === "parallel" ? "song song" : undefined,
  }));
  return { rfNodes, rfEdges };
}

function reactToFlow(
  rfNodes: Node[],
  rfEdges: Edge[],
): { nodes: FlowNode[]; edges: FlowEdge[] } {
  const nodes: FlowNode[] = rfNodes.map((n, i) => ({
    id: n.id,
    type: n.data?.nodeType || "main",
    order: n.data?.order ?? i + 1,
    label: n.data?.label || "Bước mới",
    description: n.data?.description || "",
    standard: n.data?.standard || "",
    responsible: n.data?.responsible || "",
    duration: n.data?.duration || "",
    equipment: n.data?.equipment || "",
    conditions: n.data?.conditions || "",
    checklist: n.data?.checklist || [],
    notes: n.data?.notes || "",
    x: Math.round(n.position.x),
    y: Math.round(n.position.y),
    children: n.data?.children || [],
    parent: n.data?.parent || undefined,
  }));
  const edges: FlowEdge[] = rfEdges.map((e) => ({
    from: e.source,
    to: e.target,
    type: e.animated ? "parallel" : "sequential",
  }));
  return { nodes, edges };
}

// ── Main ─────────────────────────────────────────────────────────────────────

export default function ProcessPage() {
  const router = useRouter();
  const { user, token, isAuthenticated, loading: authLoading } = useUserAuth();
  const headers = useMemo(
    () => ({ Authorization: `Bearer ${token}` }),
    [token],
  );

  // Process list
  const [processes, setProcesses] = useState<ProcessTemplate[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [activeId, setActiveId] = useState<string | null>(null);

  // Editor
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [processName, setProcessName] = useState("");
  const [processDesc, setProcessDesc] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Create dialog
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");

  useEffect(() => {
    if (!authLoading && (!isAuthenticated || user?.role !== "business"))
      router.replace("/business/login");
  }, [authLoading, isAuthenticated, user, router]);

  // ── Fetch processes ────────────────────────────────────────────────────────

  const fetchProcesses = useCallback(async () => {
    if (!token) return;
    setListLoading(true);
    try {
      const res = await fetch("/api/api/supply-chain/processes", { headers });
      if (res.ok) {
        const d = await res.json();
        setProcesses(d.processes || []);
      }
    } finally {
      setListLoading(false);
    }
  }, [token, headers]);

  useEffect(() => {
    if (isAuthenticated) fetchProcesses();
  }, [isAuthenticated, fetchProcesses]);

  // ── Load process into editor ───────────────────────────────────────────────

  const loadProcess = (p: ProcessTemplate) => {
    setActiveId(p.id);
    setProcessName(p.name);
    setProcessDesc(p.description || "");
    const { rfNodes, rfEdges } = flowToReact(
      p.flowchart.nodes || [],
      p.flowchart.edges || [],
    );
    setNodes(rfNodes);
    setEdges(rfEdges);
    setSelectedNode(null);
    setSaved(false);
  };

  // ── Create process ─────────────────────────────────────────────────────────

  const createProcess = async () => {
    if (!newName.trim()) return;
    const res = await fetch("/api/api/supply-chain/processes", {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ name: newName }),
    });
    if (res.ok) {
      const d = await res.json();
      setShowCreate(false);
      setNewName("");
      await fetchProcesses();
      // Auto-load the new one
      const newP = {
        id: d.id,
        name: newName,
        description: null,
        flowchart: { nodes: [], edges: [] },
        version: 1,
        is_active: true,
        created_at: "",
        updated_at: "",
      };
      loadProcess(newP);
    }
  };

  // ── Save ───────────────────────────────────────────────────────────────────

  const saveProcess = async () => {
    if (!activeId) return;
    setSaving(true);
    const { nodes: flowNodes, edges: flowEdges } = reactToFlow(nodes, edges);
    try {
      await fetch(`/api/api/supply-chain/processes/${activeId}`, {
        method: "PUT",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          name: processName,
          description: processDesc,
          flowchart: { nodes: flowNodes, edges: flowEdges },
        }),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      fetchProcesses();
    } finally {
      setSaving(false);
    }
  };

  // ── Delete ─────────────────────────────────────────────────────────────────

  const deleteProcess = async (id: string) => {
    if (!confirm("Xác nhận xoá quy trình này?")) return;
    await fetch(`/api/api/supply-chain/processes/${id}`, {
      method: "DELETE",
      headers,
    });
    if (activeId === id) {
      setActiveId(null);
      setNodes([]);
      setEdges([]);
    }
    fetchProcesses();
  };

  // ── Export DOCX ────────────────────────────────────────────────────────────

  const exportDocx = async () => {
    if (!activeId) return;
    // Save first
    await saveProcess();
    const res = await fetch(
      `/api/api/supply-chain/processes/${activeId}/export-docx`,
      { method: "POST", headers },
    );
    if (!res.ok) {
      alert("Xuất file thất bại");
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const cd = res.headers.get("Content-Disposition") || "";
    a.href = url;
    a.download = cd.match(/filename="([^"]+)"/)?.[1] || "quy_trinh.docx";
    a.click();
    URL.revokeObjectURL(url);
  };

  // ── Add node ───────────────────────────────────────────────────────────────

  const addNode = (type: "main" | "sub") => {
    const id = `n_${Date.now()}`;
    const newNode: Node = {
      id,
      type: "stepNode",
      position: { x: 250, y: (nodes.length + 1) * 120 },
      data: {
        label: type === "main" ? "Bước mới" : "Bước phụ",
        nodeType: type,
        order: nodes.length + 1,
      },
    };
    setNodes((nds) => [...nds, newNode]);
  };

  // ── Connect ────────────────────────────────────────────────────────────────

  const onConnect = useCallback(
    (conn: Connection) => {
      setEdges((eds) =>
        addEdge(
          {
            ...conn,
            type: "smoothstep",
            style: { stroke: "#0A1F44", strokeWidth: 2 },
          },
          eds,
        ),
      );
    },
    [setEdges],
  );

  // ── Node click → select ────────────────────────────────────────────────────

  const onNodeClick = (_: any, node: Node) => setSelectedNode(node);

  // ── Update selected node data ──────────────────────────────────────────────

  const updateNodeData = (field: string, value: any) => {
    if (!selectedNode) return;
    setNodes((nds) =>
      nds.map((n) =>
        n.id === selectedNode.id
          ? { ...n, data: { ...n.data, [field]: value } }
          : n,
      ),
    );
    setSelectedNode((prev) =>
      prev ? { ...prev, data: { ...prev.data, [field]: value } } : null,
    );
  };

  // ── Delete selected ────────────────────────────────────────────────────────

  const deleteSelected = () => {
    if (!selectedNode) return;
    setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id));
    setEdges((eds) =>
      eds.filter(
        (e) => e.source !== selectedNode.id && e.target !== selectedNode.id,
      ),
    );
    setSelectedNode(null);
  };

  // ── Guards ─────────────────────────────────────────────────────────────────

  if (authLoading || !user)
    return (
      <div className="grid place-items-center min-h-[60vh]">
        <div className="w-8 h-8 border-2 border-[#0A1F44] border-t-transparent rounded-full animate-spin" />
      </div>
    );

  const inputStyle = {
    background: "#FFFFFF",
    border: "1px solid #E2E8F0",
    color: "#0A1F44",
  };

  return (
    <div
      data-page
      className="flex flex-col flex-1 lg:min-h-0 w-full overflow-hidden"
    >
      {/* Header */}
      <div
        className="rounded-2xl p-5 mb-4 animate-section"
        style={{ background: "#F5F1E8", border: "1px solid #E2E8F0" }}
      >
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-xl grid place-items-center"
              style={{ background: "#F5F3FF", border: "1px solid #DDD6FE" }}
            >
              <svg
                className="w-5 h-5"
                style={{ color: "#7C3AED" }}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="1.8"
                  d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2"
                />
              </svg>
            </div>
            <div>
              <h1 className="text-lg font-bold" style={{ color: "#0A1F44" }}>
                Quy trình sản xuất
              </h1>
              <p className="text-xs" style={{ color: "#6B7280" }}>
                {processes.length} quy trình{" "}
                {activeId && `· Đang sửa: ${processName}`}
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            {activeId && (
              <>
                <button
                  onClick={exportDocx}
                  className="px-4 py-2.5 rounded-xl text-sm font-semibold transition-all btn-lift"
                  style={{
                    background: "#FFFBEB",
                    color: "#B45309",
                    border: "1px solid #FDE68A",
                  }}
                >
                  Xuất DOCX
                </button>
                <button
                  onClick={saveProcess}
                  disabled={saving}
                  className="px-4 py-2.5 rounded-xl text-sm font-semibold text-white btn-lift disabled:opacity-50"
                  style={{ background: saving ? "#E2E8F0" : "#0A1F44" }}
                >
                  {saving ? "Đang lưu..." : saved ? "Đã lưu" : "Lưu quy trình"}
                </button>
              </>
            )}
            <button
              onClick={() => setShowCreate(true)}
              className="px-5 py-2.5 rounded-xl text-sm font-semibold text-white btn-lift"
              style={{ background: "#0A1F44" }}
            >
              + Tạo mới
            </button>
          </div>
        </div>
      </div>

      {/* Main layout: sidebar list + editor */}
      <div className="flex-1 flex gap-4 min-h-0 overflow-hidden">
        {/* Left: Process list */}
        <div className="w-56 flex-shrink-0 overflow-y-auto space-y-1.5 pr-1">
          {listLoading ? (
            <div className="py-8 flex items-center justify-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
              <div
                className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot"
                style={{ animationDelay: "0.15s" }}
              />
              <div
                className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot"
                style={{ animationDelay: "0.3s" }}
              />
            </div>
          ) : processes.length === 0 ? (
            <div
              className="py-8 text-center text-xs animate-scale-in"
              style={{ color: "#6B7280" }}
            >
              Chưa có quy trình
            </div>
          ) : (
            processes.map((p, idx) => (
              <div
                key={p.id}
                className={`rounded-lg p-3 cursor-pointer transition-all animate-list-item stagger-${Math.min(idx + 1, 12)}`}
                style={{
                  background: activeId === p.id ? "#0A1F44" : "#FFFFFF",
                  color: activeId === p.id ? "#FFFFFF" : "#0A1F44",
                  border: `1px solid ${activeId === p.id ? "#0A1F44" : "#E2E8F0"}`,
                }}
                onClick={() => loadProcess(p)}
              >
                <p className="text-sm font-medium truncate">{p.name}</p>
                <div className="flex items-center justify-between mt-1">
                  <span
                    className="text-xs"
                    style={{
                      color:
                        activeId === p.id ? "rgba(255,255,255,0.7)" : "#9CA3AF",
                    }}
                  >
                    v{p.version} · {p.flowchart.nodes?.length || 0} bước
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteProcess(p.id);
                    }}
                    className="text-xs opacity-0 group-hover:opacity-100 hover:text-red-400"
                    style={{
                      color:
                        activeId === p.id ? "rgba(255,255,255,0.5)" : "#9CA3AF",
                    }}
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Center: Flowchart canvas */}
        <div
          className="flex-1 rounded-xl overflow-hidden"
          style={{ border: "1px solid #E2E8F0", background: "#FFFFFF" }}
        >
          {!activeId ? (
            <div className="h-full grid place-items-center">
              <div className="text-center animate-scale-in">
                <svg
                  className="w-16 h-16 mx-auto mb-3 animate-empty-icon"
                  style={{ color: "#E2E8F0" }}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="1"
                    d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2"
                  />
                </svg>
                <p className="text-sm font-medium" style={{ color: "#374151" }}>
                  Chọn quy trình hoặc tạo mới
                </p>
                <p className="text-xs mt-1" style={{ color: "#9CA3AF" }}>
                  Kéo thả các bước và nối chúng lại
                </p>
              </div>
            </div>
          ) : (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={onNodeClick}
              nodeTypes={nodeTypes}
              fitView
              style={{ width: "100%", height: "100%" }}
            >
              <Background color="#E2E8F0" gap={20} />
              <Controls position="bottom-left" />
              <MiniMap
                nodeColor={() => "#0A1F44"}
                style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
              />
              <Panel position="top-left">
                <div className="flex gap-2">
                  <button
                    onClick={() => addNode("main")}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium text-white shadow btn-lift"
                    style={{ background: "#0A1F44" }}
                  >
                    + Bước chính
                  </button>
                  <button
                    onClick={() => addNode("sub")}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium shadow"
                    style={{
                      background: "#FFFFFF",
                      color: "#6B7280",
                      border: "1px solid #E2E8F0",
                    }}
                  >
                    + Bước phụ
                  </button>
                  {selectedNode && (
                    <button
                      onClick={deleteSelected}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium shadow"
                      style={{
                        background: "#FEF2F2",
                        color: "#DC2626",
                        border: "1px solid #FECACA",
                      }}
                    >
                      Xoá node
                    </button>
                  )}
                </div>
              </Panel>
            </ReactFlow>
          )}
        </div>

        {/* Right: Properties panel */}
        {selectedNode && activeId && (
          <div
            className="w-72 flex-shrink-0 overflow-y-auto rounded-xl p-4 space-y-3"
            style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
          >
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold" style={{ color: "#0A1F44" }}>
                Chi tiết bước
              </h3>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-xs"
                style={{ color: "#9CA3AF" }}
              >
                ✕
              </button>
            </div>
            {[
              { key: "label", label: "Tên bước", type: "text" },
              { key: "description", label: "Mô tả chi tiết", type: "textarea" },
              { key: "standard", label: "Tiêu chuẩn áp dụng", type: "text" },
              { key: "responsible", label: "Người phụ trách", type: "text" },
              { key: "duration", label: "Thời gian dự kiến", type: "text" },
              { key: "equipment", label: "Thiết bị sử dụng", type: "text" },
              {
                key: "conditions",
                label: "Nhiệt độ / Điều kiện",
                type: "text",
              },
              { key: "notes", label: "Ghi chú", type: "textarea" },
            ].map((f) => (
              <div key={f.key}>
                <label
                  className="block text-xs font-medium mb-1"
                  style={{ color: "#6B7280" }}
                >
                  {f.label}
                </label>
                {f.type === "textarea" ? (
                  <textarea
                    value={selectedNode.data?.[f.key] || ""}
                    onChange={(e) => updateNodeData(f.key, e.target.value)}
                    rows={2}
                    className="w-full px-3 py-2 rounded-lg text-xs outline-none resize-none"
                    style={inputStyle}
                  />
                ) : (
                  <input
                    value={selectedNode.data?.[f.key] || ""}
                    onChange={(e) => updateNodeData(f.key, e.target.value)}
                    className="w-full px-3 py-2 rounded-lg text-xs outline-none"
                    style={inputStyle}
                  />
                )}
              </div>
            ))}
            {/* Checklist */}
            <div>
              <label
                className="block text-xs font-medium mb-1"
                style={{ color: "#6B7280" }}
              >
                Checklist Halal
              </label>
              {(selectedNode.data?.checklist || []).map(
                (item: string, i: number) => (
                  <div key={i} className="flex items-center gap-1 mb-1">
                    <span className="text-xs" style={{ color: "#9CA3AF" }}>
                      ☐
                    </span>
                    <input
                      value={item}
                      onChange={(e) => {
                        const list = [...(selectedNode.data?.checklist || [])];
                        list[i] = e.target.value;
                        updateNodeData("checklist", list);
                      }}
                      className="flex-1 px-2 py-1 rounded text-xs outline-none"
                      style={inputStyle}
                    />
                    <button
                      onClick={() => {
                        const list = (
                          selectedNode.data?.checklist || []
                        ).filter((_: any, j: number) => j !== i);
                        updateNodeData("checklist", list);
                      }}
                      className="text-xs"
                      style={{ color: "#DC2626" }}
                    >
                      ✕
                    </button>
                  </div>
                ),
              )}
              <button
                onClick={() =>
                  updateNodeData("checklist", [
                    ...(selectedNode.data?.checklist || []),
                    "",
                  ])
                }
                className="text-xs mt-1"
                style={{ color: "#0A1F44" }}
              >
                + Thêm item
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Create dialog */}
      {showCreate && (
        <Modal onClose={() => setShowCreate(false)}>
          <div
            className="w-full max-w-sm rounded-2xl p-6 animate-modal-content"
            style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3
              className="text-base font-bold mb-4"
              style={{ color: "#0A1F44" }}
            >
              Tạo quy trình mới
            </h3>
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Tên quy trình"
              className="w-full px-4 py-2.5 rounded-lg text-sm outline-none mb-4"
              style={inputStyle}
              autoFocus
            />
            <button
              onClick={createProcess}
              disabled={!newName.trim()}
              className="w-full py-2.5 rounded-xl text-sm font-semibold text-white"
              style={{
                background: !newName.trim() ? "#E2E8F0" : "#0A1F44",
                color: !newName.trim() ? "#9CA3AF" : "#fff",
              }}
            >
              Tạo
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
