import os
import time
import json
from datetime import  timedelta
from QuestionAgent.agent.utils.utils import LLMModel
from QuestionAgent.agent.reflection import get_reflection
from QuestionAgent.agent.iterative_process import get_mcts
from QuestionAgent.agent.prompts.prompts import question_design_prompt_zh
class BaseAgent():
    def __init__(self, **kwargs):
        """
        BaseAgent
        :param base_model: the model that answers the
        :param base_temperature: temperature of base_model
        :param optim_model: the optimizer model that gives error feedback and generate new prompts
        :param optim_temperature: temperature of optim_model
        :param expand_width: number of optimization step in each expansion operation
        :param num_new_prompts: number of new prompts sampled in each optimization step
        :param min_depth: minimum depth of MCTS (early stop is applied only when depth is deeper than min_depth)
        :param depth_limit: maximum depth of MCTS
        :param iteration_num: iteration number of MCTS
        :param w_exp: the weight between exploitation and exploration, default 2.5

        """
    
        self.need_id = kwargs.get('need_id')
        self.log_dir = kwargs.get('log_dir')
        self.data_dir = kwargs.get('data_dir')
        self.base_model_setting = kwargs.get('base_model_setting')
        self.search_setting = kwargs.get('search_setting')
        self.reflection_setting = kwargs.get('reflection_setting')
        #添加need_id
        self.reflection_setting.update({'need_id': self.need_id})
        self.base_model = LLMModel(
            model_type=self.base_model_setting.get("model_type", "deepseek"),
            model_name=self.base_model_setting.get("model_name", "deepseek-chat"),
         
        )
      
        self.reflection = get_reflection()(**self.reflection_setting)
        self.init_thought = self.get_init_thought()
        self.search_algo = get_mcts()(
            # thought=self.init_thought, 
            reflection=self.reflection, 
            **self.search_setting
            )
    def get_init_thought(self):
        with open(self.data_dir, 'r', encoding='utf-8') as f:
            data = json.load(f)

        needs = data[self.need_id]['needs']
        prompt = question_design_prompt_zh.format(Education_needs=needs)
        init_thought = self.base_model.generate(prompt)
        return init_thought
    def run(self):
        """
        Start searching from initial thought
        """

        start_time = time.time()
        states, result_dict = self.search_algo.search(init_state=self.init_thought)
        end_time = time.time()
        exe_time = str(timedelta(seconds=end_time-start_time)).split('.')[0]
        
        return states, result_dict


    