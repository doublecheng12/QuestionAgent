import argparse
from agent import *
import yaml
import threading
from concurrent.futures import ThreadPoolExecutor
from QuestionAgent.agent.iterative_process.ablation import MCTSNode
import os
import json
import copy
import traceback
import datetime
from tqdm import tqdm

def load_config(config_path):
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config

def get_data_length(data_path):
    with open(data_path, 'r') as f:
        data = json.load(f)
    return len(data)

def config():
    parser = argparse.ArgumentParser(description='Process prompt search agent arguments')

    parser.add_argument('--config_dir', type=str, default='./config.yaml')
    parser.add_argument('--need_id', type=int, default=None, 
                       help='Override need_id in config file')
    parser.add_argument('--num_threads', type=int, default=4,
                       help='Number of threads to use')
    args = parser.parse_args()

    args = load_config(args.config_dir)
    return args

def process_need_id(need_id, config_dict):
    # print(f"Processing need_id: {need_id}")
    try:
       
        thread_config = copy.deepcopy(config_dict)
        
  
        thread_config['need_id'] = need_id
        thread_config['search_setting'] = copy.deepcopy(thread_config['search_setting'])
        thread_config['search_setting']['need_id'] = need_id 
        thread_config['reflection_setting'] = copy.deepcopy(thread_config['reflection_setting'])
        thread_config['reflection_setting']['need_id'] = need_id
       
        # 检查是否已经处理过
        progress_file = 'progress.json'
        if os.path.exists(progress_file):
            with open(progress_file, 'r') as f:
                progress = json.load(f)
            if str(need_id) in progress and progress[str(need_id)]:
                print(f"Need_id {need_id} already processed, skipping...")
                return
        
    
       
        agent = BaseAgent(**thread_config)
        agent.run()
        
        
        progress = {}
        if os.path.exists(progress_file):
            with open(progress_file, 'r') as f:
                progress = json.load(f)
        progress[str(need_id)] = True
        with open(progress_file, 'w') as f:
            json.dump(progress, f)
            
    except Exception as e:
        error_msg = f"Error processing need_id {need_id}:\n"
        error_msg += f"Error type: {type(e).__name__}\n"
        error_msg += f"Error message: {str(e)}\n"
        error_msg += "Traceback:\n"
        error_msg += traceback.format_exc()
        
        print(error_msg)
    
        with open('error_log.txt', 'a') as f:
            f.write(f"\n--- Error at {datetime.datetime.now()} ---\n")
            f.write(error_msg + "\n")

def main():
    args = config()
    config_dict = args
    
    # 获取数据总长度
    data_length = get_data_length(config_dict['data_dir'])
    
    # 使用线程池并发处理
    num_threads = args.get('num_threads',60)
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = []
        # 使用tqdm创建进度条
        with tqdm(total=data_length, desc="Processing needs") as pbar:
            for need_id in range(data_length):
                future = executor.submit(process_need_id, need_id, config_dict)
                # 添加回调函数来更新进度条
                future.add_done_callback(lambda p: pbar.update(1))
                futures.append(future)
                
            # 等待所有任务完成
            for future in futures:
                future.result()

if __name__ == '__main__':
    args = config()
    main()