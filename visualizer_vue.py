"""
Vue-based Visualizer for Expression Evaluation Tree
Creates an interactive tree with expand/collapse and property visibility controls
"""

from graph_builder2 import ExpressionGraph2, Node, Edge
from typing import Dict, List
import json


class VueTreeVisualizer:
    """Creates Vue-based interactive tree visualization."""

    def __init__(self, graph: ExpressionGraph2):
        self.graph = graph

    def _build_tree_data(self) -> Dict:
        """Build hierarchical tree structure from graph."""
        root_node = self.graph.nodes[self.graph.root_id]
        return self._node_to_tree(root_node)

    def _node_to_tree(self, node: Node) -> Dict:
        """Convert a node and its children to tree structure."""
        children_edges = [e for e in self.graph.edges if e.from_node_id == node.id]

        node_data = {
            "id": node.id,
            "expression": node.expression,
            "isFinal": node.is_final,
            "result": node.result if node.is_final else None,
            "children": []
        }

        for edge in children_edges:
            child_node = self.graph.nodes[edge.to_node_id]
            child_tree = self._node_to_tree(child_node)
            child_tree["edgeLabel"] = edge.description
            child_tree["edgeType"] = edge.action_type
            node_data["children"].append(child_tree)

        return node_data

    def generate_html(self, output_file: str = "tree_vue.html"):
        """Generate Vue-based HTML visualization."""
        tree_data = self._build_tree_data()

        # Get summary stats
        total_nodes = len(self.graph.nodes)
        total_edges = len(self.graph.edges)
        final_results = self.graph.get_final_results()
        dist_edges = sum(1 for e in self.graph.edges if e.action_type == 'distribute')
        drop_edges = sum(1 for e in self.graph.edges if e.action_type == 'drop_brackets')
        eval_edges = sum(1 for e in self.graph.edges if e.action_type == 'evaluate')

        html_content = self._generate_html_template(
            tree_data=tree_data,
            expression=self.graph.expression,
            total_nodes=total_nodes,
            total_edges=total_edges,
            final_results=final_results,
            dist_edges=dist_edges,
            drop_edges=drop_edges,
            eval_edges=eval_edges,
            truncated=getattr(self.graph, 'truncated', False)
        )

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"Vue visualization saved to: {output_file}")
        return output_file

    def _generate_html_template(self, tree_data: Dict, expression: str,
                                 total_nodes: int, total_edges: int,
                                 final_results: List[float], dist_edges: int,
                                 drop_edges: int, eval_edges: int,
                                 truncated: bool) -> str:
        """Generate the full HTML with embedded Vue app."""

        tree_json = json.dumps(tree_data, indent=2)
        results_str = ', '.join(map(str, final_results))
        truncated_badge = '<span class="badge warning">TRUNCATED</span>' if truncated else ''

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Expression Tree: {expression}</title>
    <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f5f7fa;
            color: #333;
            line-height: 1.5;
        }}

        #app {{
            max-width: 100%;
            padding: 20px;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px 30px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }}

        .header h1 {{
            font-size: 1.5rem;
            margin-bottom: 10px;
        }}

        .header .expression {{
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 1.8rem;
            background: rgba(255,255,255,0.2);
            padding: 8px 16px;
            border-radius: 8px;
            display: inline-block;
        }}

        .stats {{
            display: flex;
            gap: 20px;
            margin-top: 15px;
            flex-wrap: wrap;
        }}

        .stat {{
            background: rgba(255,255,255,0.15);
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 0.9rem;
        }}

        .stat strong {{
            color: #ffd700;
        }}

        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .badge.warning {{
            background: #ff9800;
            color: white;
        }}

        .controls {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            position: sticky;
            top: 10px;
            z-index: 100;
        }}

        .controls h3 {{
            margin-bottom: 15px;
            color: #555;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .control-group {{
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            align-items: center;
        }}

        .control-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .control-item label {{
            font-size: 0.9rem;
            color: #666;
            cursor: pointer;
            user-select: none;
        }}

        .control-item input[type="checkbox"] {{
            width: 18px;
            height: 18px;
            cursor: pointer;
            accent-color: #667eea;
        }}

        .btn {{
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.2s;
        }}

        .btn-primary {{
            background: #667eea;
            color: white;
        }}

        .btn-primary:hover {{
            background: #5a6fd6;
        }}

        .btn-secondary {{
            background: #e0e0e0;
            color: #333;
        }}

        .btn-secondary:hover {{
            background: #d0d0d0;
        }}

        .tree-container {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            overflow: auto;
            max-height: calc(100vh - 280px);
            min-height: 400px;
        }}

        .tree-horizontal {{
            display: flex;
            flex-direction: row;
            align-items: flex-start;
            padding: 20px;
            min-width: max-content;
        }}

        /* Horizontal tree layout */
        .tree-node {{
            display: flex;
            flex-direction: row;
            align-items: center;
            position: relative;
        }}

        .node-wrapper {{
            display: flex;
            flex-direction: column;
            align-items: flex-start;
        }}

        .node-content {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            background: #f8f9fa;
            border-radius: 8px;
            border: 2px solid #e0e0e0;
            margin: 4px 0;
            transition: all 0.2s;
            white-space: nowrap;
        }}

        .node-content:hover {{
            border-color: #667eea;
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.2);
        }}

        .node-content.final {{
            background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
            border-color: #28a745;
        }}

        .node-content.collapsed {{
            opacity: 0.7;
        }}

        .expand-btn {{
            width: 22px;
            height: 22px;
            border: none;
            border-radius: 4px;
            background: #667eea;
            color: white;
            font-size: 14px;
            font-weight: bold;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            transition: all 0.2s;
        }}

        .expand-btn:hover {{
            background: #5a6fd6;
            transform: scale(1.1);
        }}

        .expand-btn.collapsed {{
            background: #6c757d;
        }}

        .node-expression {{
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 0.9rem;
        }}

        .node-id {{
            font-size: 0.65rem;
            color: #999;
            background: #eee;
            padding: 2px 5px;
            border-radius: 3px;
        }}

        .node-result {{
            font-weight: 600;
            color: #28a745;
            background: rgba(40, 167, 69, 0.1);
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.85rem;
        }}

        .children-container {{
            display: flex;
            flex-direction: column;
            margin-left: 20px;
            position: relative;
        }}

        .children-container::before {{
            content: '';
            position: absolute;
            left: -10px;
            top: 0;
            bottom: 0;
            width: 2px;
            background: linear-gradient(180deg, #e0e0e0 0%, #e0e0e0 100%);
        }}

        .child-row {{
            display: flex;
            flex-direction: row;
            align-items: center;
            position: relative;
            margin: 2px 0;
        }}

        .child-row::before {{
            content: '';
            position: absolute;
            left: -10px;
            top: 50%;
            width: 10px;
            height: 2px;
            background: #e0e0e0;
        }}

        .edge-label {{
            font-size: 0.75rem;
            padding: 3px 8px;
            border-radius: 4px;
            margin-right: 8px;
            white-space: nowrap;
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .edge-label.distribute {{
            background: #f3e5f5;
            color: #7b1fa2;
            border: 1px solid #ce93d8;
        }}

        .edge-label.evaluate {{
            background: #e3f2fd;
            color: #1565c0;
            border: 1px solid #90caf9;
        }}

        .edge-label.wrong_distribute {{
            background: #ffebee;
            color: #c62828;
            border: 1px solid #ef9a9a;
        }}

        .edge-label.drop_brackets {{
            background: #fff3e0;
            color: #e65100;
            border: 1px solid #ffcc80;
        }}

        .children-container.hidden {{
            display: none;
        }}

        .legend {{
            display: flex;
            gap: 20px;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #eee;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.85rem;
        }}

        .legend-color {{
            width: 16px;
            height: 16px;
            border-radius: 4px;
        }}

        .legend-color.distribute {{
            background: #f3e5f5;
            border: 2px solid #7b1fa2;
        }}

        .legend-color.evaluate {{
            background: #e3f2fd;
            border: 2px solid #1565c0;
        }}

        .legend-color.wrong_distribute {{
            background: #ffebee;
            border: 2px solid #c62828;
        }}

        .legend-color.drop_brackets {{
            background: #fff3e0;
            border: 2px solid #e65100;
        }}

        .legend-color.final {{
            background: #d4edda;
            border: 2px solid #28a745;
        }}

        .search-box {{
            padding: 8px 12px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            font-size: 0.9rem;
            width: 200px;
            transition: border-color 0.2s;
        }}

        .search-box:focus {{
            outline: none;
            border-color: #667eea;
        }}

        .highlight {{
            background: #fff3cd !important;
            border-color: #ffc107 !important;
        }}

        .depth-indicator {{
            font-size: 0.65rem;
            color: #999;
            background: #f0f0f0;
            padding: 1px 5px;
            border-radius: 3px;
            margin-left: 4px;
        }}

        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 1.2rem;
            }}

            .header .expression {{
                font-size: 1.2rem;
            }}

            .stats {{
                flex-direction: column;
                gap: 10px;
            }}

            .control-group {{
                flex-direction: column;
                align-items: flex-start;
            }}
        }}
    </style>
</head>
<body>
    <div id="app">
        <div class="header">
            <h1>Expression Evaluation Tree {truncated_badge}</h1>
            <div class="expression">{expression}</div>
            <div class="stats">
                <div class="stat">Nodes: <strong>{{{{ totalNodes }}}}</strong></div>
                <div class="stat">Edges: <strong>{{{{ totalEdges }}}}</strong></div>
                <div class="stat">Distribute: <strong>{{{{ distEdges }}}}</strong></div>
                <div class="stat">Drop: <strong>{{{{ dropEdges }}}}</strong></div>
                <div class="stat">Evaluate: <strong>{{{{ evalEdges }}}}</strong></div>
                <div class="stat">Results: <strong>{results_str}</strong></div>
            </div>
        </div>

        <div class="controls">
            <h3>Display Options</h3>
            <div class="control-group">
                <div class="control-item">
                    <input type="checkbox" id="showEdgeLabels" v-model="showEdgeLabels">
                    <label for="showEdgeLabels">Edge Labels</label>
                </div>
                <div class="control-item">
                    <input type="checkbox" id="showNodeIds" v-model="showNodeIds">
                    <label for="showNodeIds">Node IDs</label>
                </div>
                <div class="control-item">
                    <input type="checkbox" id="showResults" v-model="showResults">
                    <label for="showResults">Results</label>
                </div>
                <div class="control-item">
                    <input type="checkbox" id="showDistribute" v-model="showDistribute">
                    <label for="showDistribute">Distribute</label>
                </div>
                <div class="control-item">
                    <input type="checkbox" id="showDropBrackets" v-model="showDropBrackets">
                    <label for="showDropBrackets" style="color: #e65100;">Drop Brackets</label>
                </div>
                <div class="control-item">
                    <input type="checkbox" id="showEvaluate" v-model="showEvaluate">
                    <label for="showEvaluate">Evaluate</label>
                </div>
                <div class="control-item">
                    <input type="checkbox" id="showDepth" v-model="showDepth">
                    <label for="showDepth">Depth</label>
                </div>
                <div style="flex-grow: 1;"></div>
                <input type="text" class="search-box" v-model="searchQuery" placeholder="Search expressions...">
                <button class="btn btn-primary" @click="expandAll">Expand All</button>
                <button class="btn btn-secondary" @click="collapseAll">Collapse All</button>
            </div>
        </div>

        <div class="tree-container">
            <div class="tree-horizontal">
                <tree-node
                    :node="treeData"
                    :show-edge-labels="showEdgeLabels"
                    :show-node-ids="showNodeIds"
                    :show-results="showResults"
                    :show-distribute="showDistribute"
                    :show-drop-brackets="showDropBrackets"
                    :show-evaluate="showEvaluate"
                    :show-depth="showDepth"
                    :search-query="searchQuery"
                    :collapsed-nodes="collapsedNodes"
                    :depth="0"
                    @toggle="toggleNode"
                ></tree-node>
            </div>

            <div class="legend">
                <div class="legend-item">
                    <div class="legend-color distribute"></div>
                    <span>Distribute</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color drop_brackets"></div>
                    <span>Drop Brackets</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color evaluate"></div>
                    <span>Evaluate</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color final"></div>
                    <span>Final Result</span>
                </div>
            </div>
        </div>
    </div>

    <script>
        const {{ createApp }} = Vue;

        const treeData = {tree_json};

        // Helper function to get all node IDs (used for initial collapse state)
        function getAllNodeIdsHelper(node) {{
            let ids = [node.id];
            for (const child of node.children || []) {{
                ids = ids.concat(getAllNodeIdsHelper(child));
            }}
            return ids;
        }}

        const TreeNode = {{
            name: 'TreeNode',
            props: {{
                node: Object,
                showEdgeLabels: Boolean,
                showNodeIds: Boolean,
                showResults: Boolean,
                showDistribute: Boolean,
                showDropBrackets: Boolean,
                showEvaluate: Boolean,
                showDepth: Boolean,
                searchQuery: String,
                collapsedNodes: Set,
                depth: Number
            }},
            emits: ['toggle'],
            computed: {{
                isCollapsed() {{
                    return this.collapsedNodes.has(this.node.id);
                }},
                hasVisibleChildren() {{
                    return this.filteredChildren.length > 0;
                }},
                filteredChildren() {{
                    return this.node.children.filter(child => {{
                        if (child.edgeType === 'distribute' && !this.showDistribute) return false;
                        if (child.edgeType === 'drop_brackets' && !this.showDropBrackets) return false;
                        if (child.edgeType === 'evaluate' && !this.showEvaluate) return false;
                        return true;
                    }});
                }},
                matchesSearch() {{
                    if (!this.searchQuery) return false;
                    return this.node.expression.toLowerCase().includes(this.searchQuery.toLowerCase());
                }}
            }},
            methods: {{
                toggle() {{
                    this.$emit('toggle', this.node.id);
                }},
                truncateLabel(label) {{
                    if (label.length > 25) {{
                        return label.substring(0, 22) + '...';
                    }}
                    return label;
                }},
                edgePrefix(edgeType) {{
                    const prefixes = {{
                        'distribute': '[D]',
                        'wrong_distribute': '[WD]',
                        'drop_brackets': '[DROP]',
                        'evaluate': '[E]'
                    }};
                    return prefixes[edgeType] || '[?]';
                }}
            }},
            template: `
                <div class="tree-node">
                    <div class="node-wrapper">
                        <div :class="['node-content', {{ 'final': node.isFinal, 'collapsed': isCollapsed, 'highlight': matchesSearch }}]">
                            <button
                                v-if="hasVisibleChildren"
                                :class="['expand-btn', {{ 'collapsed': isCollapsed }}]"
                                @click="toggle"
                                :title="isCollapsed ? 'Expand' : 'Collapse'"
                            >
                                {{{{ isCollapsed ? '▶' : '◀' }}}}
                            </button>

                            <span class="node-expression">{{{{ node.expression }}}}</span>

                            <span v-if="showDepth" class="depth-indicator">d{{{{ depth }}}}</span>

                            <span v-if="showNodeIds" class="node-id">{{{{ node.id }}}}</span>

                            <span v-if="node.isFinal && showResults" class="node-result">
                                = {{{{ node.result }}}}
                            </span>
                        </div>
                    </div>

                    <div class="children-container" v-if="hasVisibleChildren && !isCollapsed">
                        <div v-for="child in filteredChildren" :key="child.id" class="child-row">
                            <span
                                v-if="showEdgeLabels && child.edgeLabel"
                                :class="['edge-label', child.edgeType]"
                                :title="child.edgeLabel"
                            >
                                {{{{ edgePrefix(child.edgeType) }}}} {{{{ truncateLabel(child.edgeLabel) }}}}
                            </span>
                            <tree-node
                                :node="child"
                                :show-edge-labels="showEdgeLabels"
                                :show-node-ids="showNodeIds"
                                :show-results="showResults"
                                :show-distribute="showDistribute"
                                :show-drop-brackets="showDropBrackets"
                                :show-evaluate="showEvaluate"
                                :show-depth="showDepth"
                                :search-query="searchQuery"
                                :collapsed-nodes="collapsedNodes"
                                :depth="depth + 1"
                                @toggle="$emit('toggle', $event)"
                            ></tree-node>
                        </div>
                    </div>
                </div>
            `
        }};

        createApp({{
            components: {{
                TreeNode
            }},
            data() {{
                // Start with all nodes collapsed except root (lazy rendering)
                const allIds = getAllNodeIdsHelper(treeData);
                const rootId = treeData.id;
                const initialCollapsed = new Set(allIds.filter(id => id !== rootId));

                return {{
                    treeData: treeData,
                    showEdgeLabels: true,
                    showNodeIds: false,
                    showResults: true,
                    showDistribute: true,
                    showDropBrackets: true,
                    showEvaluate: true,
                    showDepth: false,
                    searchQuery: '',
                    collapsedNodes: initialCollapsed,
                    totalNodes: {total_nodes},
                    totalEdges: {total_edges},
                    distEdges: {dist_edges},
                    dropEdges: {drop_edges},
                    evalEdges: {eval_edges}
                }};
            }},
            methods: {{
                toggleNode(nodeId) {{
                    if (this.collapsedNodes.has(nodeId)) {{
                        this.collapsedNodes.delete(nodeId);
                    }} else {{
                        this.collapsedNodes.add(nodeId);
                    }}
                    // Force reactivity
                    this.collapsedNodes = new Set(this.collapsedNodes);
                }},
                expandAll() {{
                    this.collapsedNodes = new Set();
                }},
                collapseAll() {{
                    const allIds = getAllNodeIdsHelper(this.treeData);
                    this.collapsedNodes = new Set(allIds);
                }},
                getAllNodeIds(node) {{
                    let ids = [node.id];
                    for (const child of node.children || []) {{
                        ids = ids.concat(this.getAllNodeIds(child));
                    }}
                    return ids;
                }}
            }}
        }}).mount('#app');
    </script>
</body>
</html>
'''


if __name__ == "__main__":
    print("Creating Vue visualization for: (2+3)*5")
    graph = ExpressionGraph2("(2+3)*5")
    visualizer = VueTreeVisualizer(graph)
    visualizer.generate_html("test_vue_tree.html")

    print("\nCreating Vue visualization for: (2+3)*5*3")
    graph2 = ExpressionGraph2("(2+3)*5*3")
    visualizer2 = VueTreeVisualizer(graph2)
    visualizer2.generate_html("test_vue_tree2.html")
