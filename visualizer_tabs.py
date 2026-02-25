"""
Two-Tab Visualizer for Expression Evaluation

Tab 1: Full expression tree with all possible paths (distribute, evaluate, drop_brackets)
Tab 2: Learner view - select policies and see how different learners solve the expression
"""

from graph_builder2 import ExpressionGraph2, Node, Edge
from learner_integration import (
    extract_actions_from_tokens, LearnerGraphWalker,
    compare_learners_on_expression, get_state_analysis
)
from learner import (
    LEARNER_PROFILES, list_learner_profiles, create_learner,
    get_learner_builder_options
)
from policies import PRECEDENCE_MAPS, POLICY_CATEGORIES, get_policy
from tokenizer import tokenize
from typing import Dict, List
import json


class TabbedVisualizer:
    """Creates Vue-based interactive visualization with two tabs."""

    def __init__(self, expression: str, max_nodes: int = 500):
        self.expression = expression
        self.graph = ExpressionGraph2(expression, max_nodes=max_nodes)
        self.tokens = tokenize(expression)

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

    def _build_learner_data(self) -> Dict:
        """Build data for the learner tab."""
        # Get all available actions for the initial state
        all_actions = extract_actions_from_tokens(self.tokens)

        # Get builder options
        builder_options = get_learner_builder_options()

        # Pre-compute walkthroughs for all preset learners
        walkthroughs = {}
        for name in list_learner_profiles():
            try:
                learner = create_learner(name)
                walker = LearnerGraphWalker(self.expression, learner)
                steps = walker.walk_deterministic()
                walkthroughs[name] = {
                    'steps': self._serialize_steps(steps),
                    'final_result': steps[-1].get('result') if steps else None,
                    'precedence': learner.precedence_name,
                    'policies': learner.policy_names,
                    'description': learner.description
                }
            except Exception as e:
                walkthroughs[name] = {'error': str(e)}

        return {
            'expression': self.expression,
            'tokens': self.tokens,
            'initial_actions': [
                {
                    'type': a.action_type,
                    'operator': a.operator,
                    'operator_index': a.operator_index,
                    'description': a.description
                }
                for a in all_actions
            ],
            'precedence_maps': {
                name: {
                    'values': pmap,
                    'description': builder_options['precedence_maps'][name]['description']
                }
                for name, pmap in PRECEDENCE_MAPS.items()
            },
            'policy_categories': POLICY_CATEGORIES,
            'preset_profiles': LEARNER_PROFILES,
            'walkthroughs': walkthroughs
        }

    def _serialize_steps(self, steps: List[Dict]) -> List[Dict]:
        """Serialize step data for JSON."""
        serialized = []
        for step in steps:
            s = {
                'state': step['state'],
                'tokens': step['tokens'],
            }
            if step.get('is_final'):
                s['is_final'] = True
                s['result'] = step['result']
            else:
                s['all_actions'] = [
                    {
                        'type': a.action_type,
                        'operator': a.operator,
                        'operator_index': a.operator_index,
                        'description': a.description
                    }
                    for a in step.get('all_actions', [])
                ]
                s['valid_actions'] = [
                    {
                        'type': a.action_type,
                        'operator': a.operator,
                        'operator_index': a.operator_index,
                        'description': a.description
                    }
                    for a in step.get('valid_actions', [])
                ]
                if step.get('chosen_action'):
                    s['chosen_action'] = {
                        'type': step['chosen_action'].action_type,
                        'operator': step['chosen_action'].operator,
                        'operator_index': step['chosen_action'].operator_index,
                        'description': step['chosen_action'].description
                    }
            serialized.append(s)
        return serialized

    def generate_html(self, output_file: str = "expression_tabs.html"):
        """Generate the tabbed HTML visualization."""
        tree_data = self._build_tree_data()
        learner_data = self._build_learner_data()

        # Stats
        total_nodes = len(self.graph.nodes)
        total_edges = len(self.graph.edges)
        final_results = self.graph.get_final_results()
        dist_edges = sum(1 for e in self.graph.edges if e.action_type == 'distribute')
        drop_edges = sum(1 for e in self.graph.edges if e.action_type == 'drop_brackets')
        eval_edges = sum(1 for e in self.graph.edges if e.action_type == 'evaluate')

        html_content = self._generate_html_template(
            tree_data=tree_data,
            learner_data=learner_data,
            expression=self.expression,
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

        print(f"Tabbed visualization saved to: {output_file}")
        return output_file

    def _generate_html_template(self, tree_data: Dict, learner_data: Dict,
                                 expression: str, total_nodes: int, total_edges: int,
                                 final_results: List[float], dist_edges: int,
                                 drop_edges: int, eval_edges: int,
                                 truncated: bool) -> str:
        """Generate the full HTML with embedded Vue app."""

        tree_json = json.dumps(tree_data, indent=2)
        learner_json = json.dumps(learner_data, indent=2)
        results_str = ', '.join(map(str, final_results))
        truncated_badge = '<span class="badge warning">TRUNCATED</span>' if truncated else ''

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Expression: {expression}</title>
    <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
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

        /* Tab styles */
        .tabs {{
            display: flex;
            gap: 0;
            margin-bottom: 0;
        }}

        .tab-btn {{
            padding: 12px 24px;
            border: none;
            background: #e0e0e0;
            color: #666;
            font-size: 1rem;
            font-weight: 500;
            cursor: pointer;
            border-radius: 8px 8px 0 0;
            transition: all 0.2s;
        }}

        .tab-btn:hover {{
            background: #d0d0d0;
        }}

        .tab-btn.active {{
            background: white;
            color: #667eea;
            box-shadow: 0 -2px 8px rgba(0,0,0,0.1);
        }}

        .tab-content {{
            background: white;
            border-radius: 0 12px 12px 12px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            min-height: 500px;
        }}

        /* Controls */
        .controls {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}

        .controls h3 {{
            margin-bottom: 12px;
            color: #555;
            font-size: 0.85rem;
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

        /* Tree styles (Tab 1) */
        .tree-container {{
            overflow: auto;
            max-height: calc(100vh - 350px);
            min-height: 400px;
        }}

        .tree-horizontal {{
            display: flex;
            flex-direction: row;
            align-items: flex-start;
            padding: 20px;
            min-width: max-content;
        }}

        .tree-node {{
            display: flex;
            flex-direction: row;
            align-items: center;
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
            background: #e0e0e0;
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

        .edge-label.drop_brackets {{
            background: #fff3e0;
            color: #e65100;
            border: 1px solid #ffcc80;
        }}

        .children-container.hidden {{
            display: none;
        }}

        /* Learner Tab styles (Tab 2) */
        .learner-container {{
            display: grid;
            grid-template-columns: 300px 1fr;
            gap: 20px;
        }}

        .learner-sidebar {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
        }}

        .learner-sidebar h3 {{
            margin-bottom: 15px;
            color: #333;
            font-size: 1rem;
        }}

        .learner-sidebar h4 {{
            margin: 20px 0 10px 0;
            color: #555;
            font-size: 0.85rem;
            text-transform: uppercase;
        }}

        .preset-list {{
            list-style: none;
            padding: 0;
            margin-bottom: 20px;
        }}

        .preset-item {{
            padding: 10px 12px;
            margin: 4px 0;
            background: white;
            border-radius: 6px;
            cursor: pointer;
            border: 2px solid transparent;
            transition: all 0.2s;
        }}

        .preset-item:hover {{
            border-color: #667eea;
        }}

        .preset-item.active {{
            border-color: #667eea;
            background: #f0f4ff;
        }}

        .preset-item .name {{
            font-weight: 500;
            color: #333;
        }}

        .preset-item .desc {{
            font-size: 0.8rem;
            color: #666;
            margin-top: 4px;
        }}

        .policy-group {{
            margin-bottom: 15px;
        }}

        .policy-group-title {{
            font-size: 0.8rem;
            font-weight: 600;
            color: #667eea;
            margin-bottom: 8px;
        }}

        .policy-item {{
            display: flex;
            align-items: flex-start;
            gap: 8px;
            padding: 6px 0;
        }}

        .policy-item input {{
            margin-top: 3px;
        }}

        .policy-item label {{
            font-size: 0.85rem;
            color: #333;
        }}

        .policy-item .policy-desc {{
            font-size: 0.75rem;
            color: #888;
        }}

        select {{
            width: 100%;
            padding: 8px 12px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            font-size: 0.9rem;
            background: white;
            cursor: pointer;
        }}

        select:focus {{
            outline: none;
            border-color: #667eea;
        }}

        /* Walkthrough styles */
        .walkthrough {{
            background: white;
        }}

        .walkthrough-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }}

        .learner-info {{
            background: #f0f4ff;
            padding: 12px 16px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}

        .learner-info .learner-name {{
            font-weight: 600;
            color: #333;
            font-size: 1.1rem;
        }}

        .learner-info .learner-prec {{
            font-size: 0.85rem;
            color: #666;
            margin-top: 4px;
        }}

        .final-result {{
            font-size: 1.5rem;
            font-weight: 600;
            color: #28a745;
            background: #d4edda;
            padding: 10px 20px;
            border-radius: 8px;
        }}

        .step {{
            margin-bottom: 20px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            overflow: hidden;
        }}

        .step-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            background: #f8f9fa;
            border-bottom: 1px solid #e0e0e0;
        }}

        .step-number {{
            font-weight: 600;
            color: #667eea;
        }}

        .step-state {{
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 1.1rem;
            background: white;
            padding: 4px 12px;
            border-radius: 4px;
        }}

        .step-body {{
            padding: 16px;
        }}

        .actions-table {{
            width: 100%;
            border-collapse: collapse;
        }}

        .actions-table th {{
            text-align: left;
            padding: 8px 12px;
            background: #f8f9fa;
            font-size: 0.8rem;
            text-transform: uppercase;
            color: #666;
        }}

        .actions-table td {{
            padding: 10px 12px;
            border-bottom: 1px solid #f0f0f0;
        }}

        .action-valid {{
            color: #28a745;
            font-weight: 500;
        }}

        .action-invalid {{
            color: #dc3545;
            opacity: 0.6;
        }}

        .action-chosen {{
            background: #d4edda;
        }}

        .validity-badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }}

        .validity-badge.valid {{
            background: #d4edda;
            color: #28a745;
        }}

        .validity-badge.invalid {{
            background: #f8d7da;
            color: #dc3545;
        }}

        .chosen-badge {{
            background: #667eea;
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            margin-left: 8px;
        }}

        .step.final {{
            border-color: #28a745;
        }}

        .step.final .step-header {{
            background: #d4edda;
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

        .legend-color.distribute {{ background: #f3e5f5; border: 2px solid #7b1fa2; }}
        .legend-color.evaluate {{ background: #e3f2fd; border: 2px solid #1565c0; }}
        .legend-color.drop_brackets {{ background: #fff3e0; border: 2px solid #e65100; }}
        .legend-color.final {{ background: #d4edda; border: 2px solid #28a745; }}

        @media (max-width: 900px) {{
            .learner-container {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div id="app">
        <div class="header">
            <h1>Expression Evaluation Explorer {truncated_badge}</h1>
            <div class="expression">{expression}</div>
            <div class="stats">
                <div class="stat">Nodes: <strong>{total_nodes}</strong></div>
                <div class="stat">Edges: <strong>{total_edges}</strong></div>
                <div class="stat">Distribute: <strong>{dist_edges}</strong></div>
                <div class="stat">Drop: <strong>{drop_edges}</strong></div>
                <div class="stat">Evaluate: <strong>{eval_edges}</strong></div>
                <div class="stat">Results: <strong>{results_str}</strong></div>
            </div>
        </div>

        <!-- Tabs -->
        <div class="tabs">
            <button :class="['tab-btn', {{ active: activeTab === 'graph' }}]" @click="activeTab = 'graph'">
                Full Graph
            </button>
            <button :class="['tab-btn', {{ active: activeTab === 'learner' }}]" @click="activeTab = 'learner'">
                Learner View
            </button>
        </div>

        <!-- Tab Content -->
        <div class="tab-content">
            <!-- Tab 1: Full Graph -->
            <div v-if="activeTab === 'graph'">
                <div class="controls">
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
                        <div style="flex-grow: 1;"></div>
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
                            :collapsed-nodes="collapsedNodes"
                            :depth="0"
                            @toggle="toggleNode"
                        ></tree-node>
                    </div>
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

            <!-- Tab 2: Learner View -->
            <div v-if="activeTab === 'learner'" class="learner-container">
                <div class="learner-sidebar">
                    <h3>Select Learner</h3>

                    <h4>Preset Profiles</h4>
                    <ul class="preset-list">
                        <li v-for="(profile, name) in learnerData.preset_profiles"
                            :key="name"
                            :class="['preset-item', {{ active: selectedLearner === name }}]"
                            @click="selectLearner(name)">
                            <div class="name">{{{{ name.replace(/_/g, ' ') }}}}</div>
                            <div class="desc">{{{{ profile.description }}}}</div>
                        </li>
                    </ul>

                    <h4>Precedence</h4>
                    <select v-model="customPrecedence" @change="updateCustomLearner">
                        <option v-for="(info, name) in learnerData.precedence_maps" :key="name" :value="name">
                            {{{{ name }}}} - {{{{ info.description }}}}
                        </option>
                    </select>

                    <h4>Policies</h4>
                    <div v-for="(catInfo, catName) in learnerData.policy_categories" :key="catName" class="policy-group">
                        <div class="policy-group-title">{{{{ catInfo.name }}}} <span v-if="catInfo.exclusive">(pick one)</span></div>
                        <div v-for="policyName in catInfo.policies" :key="policyName" class="policy-item">
                            <input
                                :type="catInfo.exclusive ? 'radio' : 'checkbox'"
                                :name="catName"
                                :id="policyName"
                                :value="policyName"
                                v-model="customPolicies[catName]"
                                @change="updateCustomLearner">
                            <label :for="policyName">{{{{ policyName.replace(/_/g, ' ') }}}}</label>
                        </div>
                    </div>
                </div>

                <div class="walkthrough">
                    <div class="walkthrough-header">
                        <div class="learner-info">
                            <div class="learner-name">{{{{ selectedLearner.replace(/_/g, ' ') }}}}</div>
                            <div class="learner-prec">
                                Precedence: {{{{ currentWalkthrough?.precedence || 'N/A' }}}}
                                | Policies: {{{{ (currentWalkthrough?.policies || []).join(', ') }}}}
                            </div>
                        </div>
                        <div v-if="currentWalkthrough?.final_result !== null" class="final-result">
                            = {{{{ currentWalkthrough?.final_result }}}}
                        </div>
                    </div>

                    <div v-if="currentWalkthrough && currentWalkthrough.steps">
                        <div v-for="(step, index) in currentWalkthrough.steps"
                             :key="index"
                             :class="['step', {{ final: step.is_final }}]">
                            <div class="step-header">
                                <span class="step-number">Step {{{{ index + 1 }}}}</span>
                                <span class="step-state">{{{{ step.state }}}}</span>
                            </div>
                            <div class="step-body">
                                <div v-if="step.is_final">
                                    <strong style="color: #28a745;">Final Result: {{{{ step.result }}}}</strong>
                                </div>
                                <table v-else class="actions-table">
                                    <thead>
                                        <tr>
                                            <th>Action</th>
                                            <th>Type</th>
                                            <th>Valid?</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr v-for="action in step.all_actions"
                                            :key="action.operator_index + action.type"
                                            :class="{{
                                                'action-chosen': isChosenAction(step, action),
                                                'action-valid': isValidAction(step, action),
                                                'action-invalid': !isValidAction(step, action)
                                            }}">
                                            <td>
                                                {{{{ action.description }}}}
                                                <span v-if="isChosenAction(step, action)" class="chosen-badge">CHOSEN</span>
                                            </td>
                                            <td>
                                                <span :class="['edge-label', action.type]">{{{{ action.type }}}}</span>
                                            </td>
                                            <td>
                                                <span :class="['validity-badge', isValidAction(step, action) ? 'valid' : 'invalid']">
                                                    {{{{ isValidAction(step, action) ? 'YES' : 'NO' }}}}
                                                </span>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                    <div v-else>
                        <p>Select a learner profile to see their solution path.</p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const {{ createApp }} = Vue;

        const treeData = {tree_json};
        const learnerData = {learner_json};

        function getAllNodeIds(node) {{
            let ids = [node.id];
            for (const child of node.children || []) {{
                ids = ids.concat(getAllNodeIds(child));
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
                collapsedNodes: Set,
                depth: Number
            }},
            emits: ['toggle'],
            computed: {{
                isCollapsed() {{ return this.collapsedNodes.has(this.node.id); }},
                hasVisibleChildren() {{ return this.filteredChildren.length > 0; }},
                filteredChildren() {{
                    return this.node.children.filter(child => {{
                        if (child.edgeType === 'distribute' && !this.showDistribute) return false;
                        if (child.edgeType === 'drop_brackets' && !this.showDropBrackets) return false;
                        if (child.edgeType === 'evaluate' && !this.showEvaluate) return false;
                        return true;
                    }});
                }}
            }},
            methods: {{
                toggle() {{ this.$emit('toggle', this.node.id); }},
                truncateLabel(label) {{
                    return label.length > 25 ? label.substring(0, 22) + '...' : label;
                }},
                edgePrefix(edgeType) {{
                    const prefixes = {{ 'distribute': '[D]', 'drop_brackets': '[DROP]', 'evaluate': '[E]' }};
                    return prefixes[edgeType] || '[?]';
                }}
            }},
            template: `
                <div class="tree-node">
                    <div class="node-wrapper">
                        <div :class="['node-content', {{ 'final': node.isFinal }}]">
                            <button v-if="hasVisibleChildren"
                                    :class="['expand-btn', {{ 'collapsed': isCollapsed }}]"
                                    @click="toggle">
                                {{{{ isCollapsed ? '+' : '-' }}}}
                            </button>
                            <span class="node-expression">{{{{ node.expression }}}}</span>
                            <span v-if="showNodeIds" class="node-id">{{{{ node.id }}}}</span>
                            <span v-if="node.isFinal && showResults" class="node-result">= {{{{ node.result }}}}</span>
                        </div>
                    </div>
                    <div class="children-container" v-if="hasVisibleChildren && !isCollapsed">
                        <div v-for="child in filteredChildren" :key="child.id" class="child-row">
                            <span v-if="showEdgeLabels && child.edgeLabel"
                                  :class="['edge-label', child.edgeType]"
                                  :title="child.edgeLabel">
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
            components: {{ TreeNode }},
            data() {{
                const allIds = getAllNodeIds(treeData);
                const initialCollapsed = new Set(allIds.filter(id => id !== treeData.id));

                // Initialize custom policies with first option from each exclusive category
                const customPolicies = {{}};
                for (const [catName, catInfo] of Object.entries(learnerData.policy_categories)) {{
                    if (catInfo.exclusive) {{
                        customPolicies[catName] = catInfo.policies[0];
                    }} else {{
                        customPolicies[catName] = [];
                    }}
                }}

                return {{
                    activeTab: 'learner',
                    treeData: treeData,
                    learnerData: learnerData,
                    showEdgeLabels: true,
                    showNodeIds: false,
                    showResults: true,
                    showDistribute: true,
                    showDropBrackets: true,
                    showEvaluate: true,
                    collapsedNodes: initialCollapsed,
                    selectedLearner: 'expert',
                    customPrecedence: 'bodmas',
                    customPolicies: customPolicies
                }};
            }},
            computed: {{
                currentWalkthrough() {{
                    return this.learnerData.walkthroughs[this.selectedLearner];
                }}
            }},
            methods: {{
                toggleNode(nodeId) {{
                    if (this.collapsedNodes.has(nodeId)) {{
                        this.collapsedNodes.delete(nodeId);
                    }} else {{
                        this.collapsedNodes.add(nodeId);
                    }}
                    this.collapsedNodes = new Set(this.collapsedNodes);
                }},
                expandAll() {{ this.collapsedNodes = new Set(); }},
                collapseAll() {{
                    const allIds = getAllNodeIds(this.treeData);
                    this.collapsedNodes = new Set(allIds);
                }},
                selectLearner(name) {{
                    this.selectedLearner = name;
                    // Update sidebar to reflect selected learner's config
                    const profile = this.learnerData.preset_profiles[name];
                    if (profile) {{
                        this.customPrecedence = profile.precedence;
                    }}
                }},
                updateCustomLearner() {{
                    // For now, just use preset. Custom learner would require backend call.
                    console.log('Custom config:', this.customPrecedence, this.customPolicies);
                }},
                isValidAction(step, action) {{
                    if (!step.valid_actions) return false;
                    return step.valid_actions.some(va =>
                        va.type === action.type &&
                        va.operator === action.operator &&
                        va.operator_index === action.operator_index
                    );
                }},
                isChosenAction(step, action) {{
                    if (!step.chosen_action) return false;
                    return step.chosen_action.type === action.type &&
                           step.chosen_action.operator === action.operator &&
                           step.chosen_action.operator_index === action.operator_index;
                }}
            }}
        }}).mount('#app');
    </script>
</body>
</html>
'''


if __name__ == "__main__":
    import sys

    # Default expression or from command line
    expr = sys.argv[1] if len(sys.argv) > 1 else "(2+3)*4+5"

    print(f"Creating tabbed visualization for: {expr}")
    visualizer = TabbedVisualizer(expr)
    visualizer.generate_html("expression_explorer.html")

    print("\nTo view, open expression_explorer.html in a browser")
