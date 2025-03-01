import os
from dotenv import load_dotenv

# 加载.env文件中的环境变量(如果存在)
# 这允许我们从.env文件中读取配置，而不是硬编码在代码中
load_dotenv()

class Config:
    # 飞书应用配置
    # FEISHU_APP_ID: 飞书开放平台应用的唯一标识
    # FEISHU_APP_SECRET: 飞书应用的密钥，用于API认证
    FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "cli_a73563d3b0fa900d")
    FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "c8gTrrXxvX62KRbfQoBD8drV4NN1SRnH")
    
    # 多维表格配置
    # BASE_ID: 飞书多维表格应用的ID
    # TABLE_ID: 具体表格的ID，存储博客文章数据
    BASE_ID = os.getenv("BASE_ID", "LsKdbdQnaagwSysm5EFccXaUnOc")
    TABLE_ID = os.getenv("TABLE_ID", "tblEDojeqQuUcgPi")
    
    # Flask应用配置
    # SECRET_KEY: Flask会话安全密钥
    # DEBUG: 是否启用调试模式，生产环境应设为False
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    
    # 缓存配置
    CACHE_TYPE = "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = 300  # 缓存过期时间(秒)