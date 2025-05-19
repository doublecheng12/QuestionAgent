from QuestionAgent.agent.prompts.prompts import reflection_prompt_zh,critic_prompt_zh,question_generation_prompt_zh,gradient_prompt_zh
import re
import json
import numpy as np
from QuestionAgent.agent.utils.utils import LLMModel
class GradientDescent():
    def __init__(self, 
                 model_type, 
                 model_name,
                 needs, 
                 num_new_thoughts = 1):

     
        self.model_type = model_type
        self.model_name = model_name
        self.num_new_thoughts= num_new_thoughts
        self.optimize_prompt_tempelate = reflection_prompt_zh 
        self.gradient_prompt_tempelate = gradient_prompt_zh
        self.critic_prompt_tempelate = critic_prompt_zh
        self.question_generation_prompt_tempelate = question_generation_prompt_zh
        self.base_model = LLMModel(model_type=self.model_type, model_name=self.model_name)
        

    def forward(self, needs, cur_thought):
        question_generation_prompt = self.question_generation_prompt_tempelate.format(Education_needs=needs, Question_design_thought=cur_thought)
        responses = self.base_model.generate(question_generation_prompt)
        responses = self.extract_question(responses)
        # responses = self.clean_response(responses)
        # responses = json.loads(responses)

        score_prompt = self.critic_prompt_tempelate.format(Education_needs=needs, Question_design_thought=cur_thought)
        score = self.base_model.generate(score_prompt)
        score = self.clean_response(score)
        score_response = json.loads(score)
       
        forward_output = {
            'cur_thought ': cur_thought,
            'cur_question': responses['Question'],
            'score':score_response['score'],
            }

        return forward_output
    
    
    def _build_thought_trajectory_str(self, thoughts):
        thought_path_str = ""
        thought_path_str_tempelate = "({index}) {thought}\n"
        for i, thought in enumerate(thoughts):
            thought_path_str += thought_path_str_tempelate.format(index=i,thought=thought)
        return thought_path_str
        
    def cal_gradient(self, needs, cur_thought, gradient_prompt_tempelate):
        gradient_prompt = gradient_prompt_tempelate.format(Education_needs=needs, Question_design_thought=cur_thought)
        gradient = self.base_model.generate(gradient_prompt)
        gradient = self.clean_response(gradient)
        gradient = json.loads(gradient)
        try:
            return gradient['gradient']
        except:
            return gradient

    def _clean_optim_response(self, response):
        try:
            # response = json.loads(response)
            # return response['optimized_thought']
            return response
        except:
            return response
    def optimize(self, cur_thought, needs, gradient, trajectory_thoughts, 
              optimize_prompt_tempelate):
        optimize_prompt = optimize_prompt_tempelate.format(
            Question_design_thought=cur_thought, 
            Education_needs=needs, 
            gradient=gradient, 
            trajectory_thoughts=trajectory_thoughts,
           )
        
        response = self.base_model.generate(optimize_prompt)
        optimized_thought = self._clean_optim_response(response)
    
        return optimized_thought
    
    def clean_response(self, response):
        # 移除 JSON 代码块标记
        response = response.replace('```json', '').replace('```', '')
        response = response.strip()
        
        # 处理转义字符和特殊字符
        try:
            # 尝试修复常见的转义字符问题
            response = response.encode('utf-8').decode('unicode_escape')
            response = response.replace('\n', '').replace('\r', '')
            response = re.sub(r'\\(?!["\\/bfnrt])', r'\\\\', response)
            
          
            parsed_json = json.loads(response)
            return json.dumps(parsed_json) 
        except Exception as e:
         
            try:
                score_match = re.search(r'"score"\s*:\s*(\d+)', response)
                if score_match:
                    return json.dumps({"score": int(score_match.group(1))})
            except:
                pass
            
         
            return json.dumps({"score": 5})

    def extract_question(self, response):
        question_pattern = r'```json\s*(\{.*?\})\s*```'
        question_match = re.search(question_pattern, response, re.DOTALL)
    
        if question_match:
            extracted_question = question_match.group(1).strip()
            responses = {'Question': extracted_question}
        else:
            responses = {'Question': response}

        return responses
    def gradient_descent_step(self, cur_thought, needs, helper_data):

        forward_output = self.forward(needs=needs, cur_thought=cur_thought)
        # score = forward_output['score']
        
        gradient = self.cal_gradient(
            needs=needs, 
            cur_thought=cur_thought, 
            gradient_prompt_tempelate=self.gradient_prompt_tempelate)
        
        trajectory_thoughts = helper_data['trajectory_thoughts']
        trajectory_thoughts = self._build_thought_trajectory_str(trajectory_thoughts)
        optimized_thought = self.optimize(
            cur_thought=cur_thought, 
            needs=needs, 
            gradient=gradient, 
            trajectory_thoughts=trajectory_thoughts,
            optimize_prompt_tempelate=self.optimize_prompt_tempelate)
        
        gradient_descent_output = forward_output
        gradient_descent_output['gradient'] = gradient
        gradient_descent_output['optimized_thought'] = optimized_thought
        return gradient_descent_output
    
    def __call__(self, needs, cur_thought, helper_data=None):
        gradient_descent_output = self.gradient_descent_step(needs=needs, cur_thought=cur_thought, helper_data=helper_data)
        return gradient_descent_output