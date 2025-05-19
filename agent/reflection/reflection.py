from typing import Generic
from QuestionAgent.agent.iterative_process.mcts import MCTSNode
from QuestionAgent.agent.reflection.gradient import *
from tqdm import tqdm
import json
import os
import logging
from QuestionAgent.agent.utils.utils import LLMModel

class Reflection():
    def __init__(self,
                 need_id,
                 num_new_thoughts: int = 1,
                 model_type: str = 'glm',
                 model_name: str = 'GLM-4-Plus',
                 train_data: str = None,
                 log_dir: str = '',
                 log: bool = True
                 ):
        self.model_type = model_type
        self.model_name = model_name
        self.need_id = need_id
        self.num_new_thoughts = num_new_thoughts
        self.log = log
        self.log_dir = log_dir
        self.train_data = train_data
        self.base_model = LLMModel(model_type=self.model_type, model_name=self.model_name)
       
       

        # if self.log:
        #     if not os.path.exists(self.log_dir):
        #         os.makedirs(self.log_dir)
        #     self.logger = logging.getLogger('Reflection')
        #     self.logger.setLevel(logging.INFO)
        #     fh = logging.FileHandler(os.path.join(self.log_dir, 'reflection.log'))
        #     fh.setLevel(logging.INFO)
        #     formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        #     fh.setFormatter(formatter)
        #     self.logger.addHandler(fh)
        #     self.logger.info('Reflection initialized')
        self.needs = self.get_needs()
        self.gradient_descent = GradientDescent(model_type=self.model_type, model_name=self.model_name,num_new_thoughts=self.num_new_thoughts,needs=self.needs)
      
    def get_needs(self):
        if self.train_data is None:
            return self.need_id
        with open(self.train_data, 'r',encoding='utf-8') as f:
            train_data = json.load(f)
       
        needs = train_data[self.need_id]['needs']
      
        # if self.log:
        #     self.logger.info(f'Loaded needs: {needs}')
        return needs

    def _get_trajectory_thoughts(self, node: MCTSNode):
        """
        Collect the trajectory of prompts from the root node to the given node.
        """
        trajectory_thoughts = []
        temp_node = node
        while True:
            trajectory_thoughts.append(temp_node.thought)
            if temp_node.parent is not None:
                temp_node = temp_node.parent
            else:
                break
        # if self.log:
        #     self.logger.info(f'Got trajectory thoughts of length {len(trajectory_thoughts)}')
        return trajectory_thoughts[::-1]
    
    def build_root(self, init_thought):
        """
        Build the root node with the initial thought.
        """
        node = MCTSNode(thought=init_thought,action=None,parent=None)
        node.reward = self.evaluate_thought(init_thought, self.needs)
        
        return node
    
    def step(self, node: MCTSNode):
        """
        Optimization step: 
        1. Gradient descent to optimize the thought
        2. Build new nodes with the optimized thought
        """
        # if self.log:
        #     self.logger.info('Starting optimization step')
        new_nodes, gradient_descent_output = self._gradient_descent_step(node, self.needs)
        # if self.log:
        #     self.logger.info(f'Created {len(new_nodes)} new nodes')
        return new_nodes, gradient_descent_output

    def _gradient_descent_step(self, node, needs):
        trajectory_thoughts = self._get_trajectory_thoughts(node = node)
        helper_data = dict(trajectory_thoughts=trajectory_thoughts)
        gradient_descent_output = self.gradient_descent(needs=needs, cur_thought=node.thought, helper_data=helper_data)
        new_nodes = []
        thought = gradient_descent_output['optimized_thought']
        child_node = MCTSNode(
            thought=thought,
            action = gradient_descent_output['optimized_thought'],
            parent = node,
            )
        new_nodes.append(child_node)
        return new_nodes, gradient_descent_output
    
    def evaluate_child_node(self, node: MCTSNode, needs):
        """
        Evaluate the child node.
        """
        score = self.evaluate_thought(node.thought, needs)
        node.reward = score
     
        # if self.log:
        #     self.logger.info(f'Evaluated child node with reward {score}')

    def clean_response(self, response):
        response = response.replace('```json', '').replace('```', '')
        return response
    
    def evaluate_thought(self, thought,needs):
        """
        Evaluate the thought.
        """
        # if self.log:
        #     self.logger.info('Evaluating thought')
        # self.logger.info(f'Thought and Question: {thought}')
        score_response = self.base_model.generate(critic_prompt_zh.format(Education_needs=needs, Question_design_thought=thought))
        score_response = self.clean_response(score_response)
        score_response = score_response.replace("\\","\\\\")
       
        try:
            score = json.loads(score_response)['score']
        except:
            score = 5
       
        return score