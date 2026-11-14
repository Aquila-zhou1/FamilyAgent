import dashvector
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 从环境变量获取配置
api_key = os.getenv('DASHVECTOR_API_KEY')
endpoint = os.getenv('DASHVECTOR_ENDPOINT')

# 创建客户端
client = dashvector.Client(api_key=api_key, endpoint=endpoint)

# 判断 client 是否创建成功（更好的判断方式）
if client:
    print('create client success!')
else:
    print('create client failed!')