from dataclasses import dataclass
from typing import List, Dict, Set, Tuple, Optional
from enum import Enum
import numpy as np
import openai
import itertools
from copy import deepcopy
import os
import json
import logging
from multiprocessing import Value
import ctypes
import fcntl
class MCTSNode:
    # A node of MCTS tree
    def __init__(self, thought:str, action:str, parent: Optional['MCTSNode'] = None):
        self.id = None  # ID将由MCTS实例的_create_node方法设置
        self.thought = thought
        self.is_terminal = False
        self.children: 'Optional[list[MCTSNode]]' = []
        self.cum_rewards: list[float] = []
        self.reward = 0.0
        self.test_metric = -1.0
        self.uct = 0.0
        self.visited = 0
        self.parent = parent
        self.action = action
       
        
        if parent is None:
            self.depth = 0
        else:
            self.depth = parent.depth + 1

    def calc_q(self, x):
        return np.mean(x)
    
    def cal_reward(self):
        return self.reward

    @property
    def Q(self) -> float:
        if len(self.cum_rewards) == 0:
            return self.reward
        else:
            return self.calc_q(self.cum_rewards)
        
    def to_dict(self):
        return {
            'id': self.id,
            'depth':self.depth,
            'parent':-1 if self.parent is None else self.parent.id,
            'visited':self.visited,
            # 'expand_times':self.expand_times,
            'q':self.Q,
            'uct':self.uct,
            'thought': self.thought,
            'reward': self.reward,
            'test_metric':self.test_metric
        }
class MCTS:
    def __init__(self, #mcts arguments
                 reflection,
                 need_id,
                 expand_width = 3,
                 w_exp: float = 2.5,
                 depth_limit: int = 8,
                 min_depth: int = 2,
                 iteration_num: int = 12,
                 log_dir: str = '/data/chengc/QuestionAgent/agent/logs',
                 log: bool = True):
        """
        MCTS search algorithm
        :param expand_width: number of batches to be sampled
        :param w_exp: the weight of mcts exploration
        :param depth_limit: the max depth of a single MCTS path
        :param iteration_num: number of MCTS iterations
        :param log: whether to log search process
        """
        self.expand_width = expand_width
        self.depth_limit = depth_limit
        self.w_exp = w_exp
        self.need_id = need_id
        self.iteration_num = iteration_num
        self.min_depth = min_depth # Apply early stop only when depth is larger than min_depth
        self.reflection = reflection
        self.mcts_threshold = 0.0 # The highest reward node globally
        self.min_threshold = 0.0 # The root node's reward as a min threshold
        self.k = 1 # top-k reward nodes
        self.trace_in_each_iter: list[list[MCTSNode]] = None
        self.root: Optional[MCTSNode] = None
        self.log_dir = log_dir
        self.nodes:list[MCTSNode] = []
        self.log = log
        
      
        self._id_counter = Value(ctypes.c_int64, 0)
       
        # if self.log:
        #     if not os.path.exists(self.log_dir):
        #         os.makedirs(self.log_dir)
        #     self.logger = logging.getLogger('MCTS')
        #     self.logger.setLevel(logging.INFO)
        #     fh = logging.FileHandler(os.path.join(self.log_dir, 'mcts.log'))
        #     fh.setLevel(logging.INFO)
        #     formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        #     fh.setFormatter(formatter)
        #     self.logger.addHandler(fh)
        #     self.logger.info('MCTS initialized')

    def simulate_choice(self, x):
        return np.argmax(x)
    
    def increase_threshold(self, threshold):
        if threshold > self.mcts_threshold:
            self.mcts_threshold = threshold
            # if self.log:
            #     self.logger.info(f'New threshold: {threshold}')
    
    def cal_cum_reward(self, rewards):
        return np.sum(rewards)
    
    def _is_terminal_with_depth_limit(self, node: MCTSNode):
        return node.depth >= self.depth_limit
    
    def early_stop(self, node: MCTSNode):
        return node.reward > self.mcts_threshold and node.depth > self.min_depth
    
    def _is_terminal_with_min_threshold(self, node: MCTSNode):
        if node.parent is None:
            min_threshold = self.min_threshold
        else:
            min_threshold = (self.min_threshold + node.parent.reward) / 2
        return node.reward < min_threshold and node.depth > self.min_depth
    
    def is_terminal_node(self, node: MCTSNode):
      
     
        if node.reward < self.min_threshold * 0.8: 
            return True
        return self._is_terminal_with_depth_limit(node) or self._is_terminal_with_min_threshold(node) or node.is_terminal
    
    def _uct(self, node: MCTSNode) -> float:
        #UCT计算
        if node.parent is None:
            N_parent = 0
        else:
            N_parent = len(node.parent.cum_rewards)
        return node.Q + self.w_exp * np.sqrt(np.log(N_parent+1) / max(1, len(node.cum_rewards)))
        


    def _uct_select(self, node: MCTSNode) -> MCTSNode:
        # 原始UCT选择
        return max(node.children, key=self._uct)
    
    
    def _select(self, node: MCTSNode) -> list[MCTSNode]:
        """
        Selection: 
            From root node, keep selecting child node based on UCT
        """
        # if self.log:
        #     self.logger.info('Selection started')
        
        path = []
        while True:
            path.append(node)
            print(vars(node))
            node.visited += 1
            if len(node.children) == 0 or self.is_terminal_node(node):
                # if self.log:
                #     self.logger.info(f'Selection ended at depth {node.depth}')
                return path
            node = self._uct_select(node)
            
    def _expand(self, node: MCTSNode):
        """
        Expansion: 
            Sample batches of data and perform state transition on the given node.
            Generate new child nodes and calculate their temporary reward.
        """
        # if self.log:
        #     self.logger.info(f'Expanding node at depth {node.depth}')
        
   
        i = 0
        # node.expand_times += 1
        while i < self.expand_width:
            needs = self.reflection.get_needs() #sample batch data
            children, gradient_descent_output = self.reflection.step(node) 
            # optim step: sample new child nodes using one batch
            
            i += 1
            for child_node in children: # There could be multiple children in one optim step (num_new_prompts>1)
                self.reflection.evaluate_child_node(node=child_node,needs=needs)
                child_node.reward = child_node.cal_reward()
                child_node.is_terminal = self.is_terminal_node(child_node)
                # if self.log:
                #     self.logger.info(f'New child node created with reward {child_node.reward}')
        
            self.nodes.extend(children)
            node.children.extend(children)

    def _simulate(self, path: list[MCTSNode]):
        """
        mcts的模拟过程
        """
        node = path[-1]

        while True:
            if self.early_stop(node):
                node.is_terminal = self.is_terminal_node(node)
                self.increase_threshold(node.reward)
                return 
            
            self.increase_threshold(node.reward)
            
            if self.is_terminal_node(node):
                return
            
            if len(node.children) == 0:
                self._expand(node)
            
            # 模拟过程
            rewards = [child.reward for child in node.children]
            if len(rewards) != 0:
                node = node.children[self.simulate_choice(rewards)]
            else:
                node.is_terminal = True
            
           
            node.visited += 1
            path.append(node)

    def _back_propagate(self, path: list[MCTSNode]):
        """
        Back Propagation: Update the cumulated rewards of each node in the path.
        """
        # if self.log:
        #     self.logger.info('Back propagation started')
        
        rewards = []
        cum_rewards = []
        
        for node in reversed(path):
            rewards.append(node.reward)
            cum_reward = self.cal_cum_reward(rewards[::-1])
            cum_rewards.append(cum_reward)
            node.cum_rewards.append(cum_reward)
          
        cum_rewards = cum_rewards[::-1]
        # if self.log:
        #     self.logger.info(f'Final cumulative reward: {cum_rewards[0]}')
        return cum_rewards
    
    def iterate(self, node: MCTSNode) -> list[MCTSNode]:
        """
        MCTS iteration: Selection, Expansion, Simulation, Back-Propagation
        """
        # if self.log:
        #     self.logger.info('Starting new iteration')
            
        path = self._select(node)
        if not self._is_terminal_with_depth_limit(path[-1]):
            self._expand(path[-1])
            self._simulate(path)
        cum_rewards = self._back_propagate(path)
                    
        return path, cum_rewards        
    
    def _create_node(self, thought: str, action: str, parent: Optional[MCTSNode] = None) -> MCTSNode:
        with self._id_counter.get_lock():
            self._id_counter.value += 1
            node_id = self._id_counter.value
        
        node = MCTSNode(thought=thought, action=action, parent=parent)
        node.id = node_id
        return node

    def search(self, init_state: str):
        # if self.log:
        #     self.logger.info('Starting MCTS search')

        # 使用 _create_node 方法创建根节点
        self.root = self._create_node(thought=init_state, action="")
        self.root.reward = self.root.cal_reward()
        self.nodes.append(self.root)
     
        if self.min_threshold == 0:
            self.min_threshold = self.root.reward
            self.increase_threshold(self.root.reward)

        self.trace_in_each_iter = []
        for i in range(self.iteration_num):
            # if self.log:
            #     self.logger.info(f'Iteration {i+1}/{self.iteration_num}')
            
            path, cum_rewards = self.iterate(self.root)
            self.trace_in_each_iter.append(deepcopy(path))
        
        mcts_output = self.prepare_output()

        self.output_to_json(mcts_output=mcts_output)
        
        # if self.log:
        #     self.logger.info('MCTS search completed')
            
        return self.trace_in_each_iter, mcts_output
    
    def __call__(self,
                 init_state: str,
                 **kwargs):
        # 每次调用时重置当前MCTS实例的计数器
        with self._id_counter.get_lock():
            self._id_counter.value = 0  # 直接重置计数器，不再调用 reset_id
            
        iteration_paths, mcts_outputs = self.search(init_state)
        return iteration_paths, mcts_outputs
    
    def _sort_helper(self, metric):
        if isinstance(metric, tuple):
            return metric[0]
        else:
            return metric


    def prepare_output(self):
        # if self.log:
        #     self.logger.info('Preparing output')
      
        paths_nodes = []
        paths_ids = []
        paths_qs = []
        paths_rewards = []
        paths_ucts = []
        for i, path in enumerate(self.trace_in_each_iter):
            path_nodes = []
            path_ids = []
            path_qs = []
            path_rewards = []
            path_ucts = []
            for node in path:
                path_ids.append(node.id)
                uct = self._uct(node)
                node.uct = uct
                path_ucts.append(uct)
                path_nodes.append(node)
                path_qs.append(node.Q)
                path_rewards.append(node.reward)

            paths_nodes.append(path_nodes)
            paths_ids.append(path_ids)
            paths_qs.append(path_qs)
            paths_rewards.append(path_rewards)
            paths_ucts.append(path_ucts)
        
        qs_rank = np.argsort([np.mean(row) for row in paths_qs])[::-1].tolist()
        rewards_rank = np.argsort([np.mean(row) for row in paths_rewards])[::-1].tolist()

        best_q_path = paths_nodes[qs_rank[0]]
        best_reward_path = paths_nodes[rewards_rank[0]]
        top_k_reward_nodes = sorted(self.nodes, key=lambda node: node.reward, reverse=True)[:self.k]

        selected_node = sorted(best_reward_path, key=lambda node: self._sort_helper(node.reward), reverse=True)[0]
        
        # if self.log:
        #     self.logger.info(f'Best reward: {selected_node.reward}')
            
        return dict(
            # all_paths = paths_nodes,
            # all_nodes = self.nodes,
            # best_q_path = best_q_path,
            # best_reward_path = best_reward_path,
            # top_k_reward_nodes=top_k_reward_nodes,
            best_reward_path_last_node = [best_reward_path[-1]],
            best_reward_path_selected_node = [selected_node],
        )
    
    def output_to_json(self, mcts_output):
        # if self.log:
        #     self.logger.info('Saving output to JSON')
        # output_file = os.path.join(self.log_dir, 'mcts_results_q2.json')
        # data_to_save = {}
        # paths = []
        # # for path in mcts_output['all_paths']:
        # #     paths.append([node.to_dict() for node in path])
        # # data_to_save['all_paths'] = paths
        
        # for key in mcts_output:
        #     if key != "all_paths":
        #         data_to_save[key] = [node.to_dict() for node in mcts_output[key]]
        # existing_data = []
        # result_dict = {}
        # result_dict['need_id'] = self.need_id
        # result_dict['mcts_output'] = data_to_save
        # if os.path.exists(output_file):
        #     with open(output_file, 'r', encoding='utf-8') as f:
        #         existing_data = json.load(f)
        # existing_data.append(result_dict)
        # with open(os.path.join(self.log_dir, 'mcts_results_q2.json'), 'w', encoding='utf-8') as f:
        #     json.dump(existing_data, f, indent=4, ensure_ascii=False)
            
        # if self.log:
        #     self.logger.info('Output saved successfully')
        output_file = os.path.join(self.log_dir, 'mcts_results_q1_gpt4o.json')
    
        data_to_save = {}
        for key in mcts_output:
            if key != "all_paths":
                data_to_save[key] = [node.to_dict() for node in mcts_output[key]]
        
        result_dict = {
            'need_id': self.need_id,
            'mcts_output': data_to_save
        }
        
        with open(output_file, 'a+', encoding='utf-8') as f:
      
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
             
                f.seek(0)
                content = f.read().strip()
                existing_data = json.loads(content) if content else []
                
          
                f.seek(0)
                f.truncate()
                
             
                existing_data.append(result_dict)
                json.dump(existing_data, f, indent=4, ensure_ascii=False)
                
            finally:
           
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)