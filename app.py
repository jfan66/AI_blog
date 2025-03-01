import os
import json
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, abort, flash
from flask_caching import Cache
from config import Config
from models import Comment, save_comment, load_comments

# 创建Flask应用实例
app = Flask(__name__)
# 从Config类加载配置信息（包括飞书API凭证、多维表格ID等）
app.config.from_object(Config)

# 时间戳转日期格式的过滤器 - 在模板中可以使用 {{ timestamp|format_timestamp }} 格式调用
@app.template_filter('format_timestamp')
def format_timestamp(timestamp, format='%Y-%m-%d'):
    """将毫秒级时间戳转换为指定格式的日期字符串
    
    参数:
        timestamp: 毫秒级时间戳
        format: 日期格式字符串，默认为年-月-日格式
        
    返回:
        格式化后的日期字符串，如果转换失败则返回原始值
    """
    if not timestamp:
        return ''
    try:
        # 将毫秒级时间戳转换为秒级
        ts = int(timestamp) / 1000
        return datetime.fromtimestamp(ts).strftime(format)
    except (ValueError, TypeError):
        # 如果转换失败，返回原始值
        return timestamp

# 清理文本内容的过滤器 - 处理从飞书多维表格获取的文本，使其在网页中正确显示
@app.template_filter('clean_text')
def clean_text(text):
    """清理文本中的格式字符，使其更加美观
    
    处理从飞书多维表格获取的文本数据，移除多余的格式字符、JSON标记等，
    并将换行符转换为HTML的<br>标签，使文本在网页中正确显示。
    
    参数:
        text: 需要清理的原始文本
        
    返回:
        清理后的文本，适合在HTML中显示
    """
    if not text:
        return ''
    
    # 首先检查数据类型，确保是字符串
    if not isinstance(text, str):
        try:
            # 尝试将非字符串类型转换为字符串
            text = str(text)
        except:
            # 如果无法转换，则返回空字符串
            return ''
    
    try:
        import re
        # 检查是否是JSON字符串，尝试解析
        try:
            # 如果是有效的JSON字符串，尝试解析并提取文本内容
            if text.startswith('"') and text.endswith('"'):
                # 去掉最外层的引号
                text = text[1:-1]
            
            # 处理可能的JSON转义
            text = text.replace('\\"', '"')
        except:
            pass
        
        # 处理JSON格式的文本字段 - 移除JSON字段名称
        text = text.replace('"text":', '')
        text = text.replace('"type":', '')
        text = text.replace('"paragraph":', '')
        text = text.replace('"content":', '')
        
        # 处理换行符 - 将\n和\n转换为HTML的<br>标签
        text = text.replace('\\n', '<br>')
        text = text.replace('\n', '<br>')
        
        # 处理数字列表格式 (如 \n1, \n2 等) - 使列表格式更美观
        text = re.sub(r'\\n(\d+)', r'<br>\1.', text)
        text = re.sub(r'<br>(\d+)\.', r'<br>\1.', text)
        
        # 移除多余的引号、大括号和方括号 - 清理JSON格式的痕迹
        text = text.replace('"{', '')
        text = text.replace('}"', '')
        text = text.replace('"[', '')
        text = text.replace(']"', '')
        text = text.replace('{"', '')
        text = text.replace('"}', '')
        
        # 清理多余的逗号和冒号 - 进一步清理JSON格式
        text = re.sub(r',\s*"', ' ', text)
        text = re.sub(r':\s*', '', text)
        
        # 清理多余的引号 - 移除不必要的引号
        text = text.replace('\"', '"')
        text = re.sub(r'"([^"]+)"', r'\1', text)
        
        # 清理多余的空格和标点 - 使文本更整洁
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    except (ValueError, TypeError, AttributeError) as e:
        # 如果处理失败，返回原始值
        app.logger.error(f"清理文本失败: {str(e)}")
        return str(text) if text else ''

# 初始化缓存 - 用于缓存飞书API的访问令牌和多维表格数据，减少API调用次数
cache = Cache(app)

# 飞书API相关URL
# FEISHU_HOST: 飞书开放平台的基础URL
FEISHU_HOST = "https://open.feishu.cn"
# TENANT_ACCESS_TOKEN_URL: 获取租户访问令牌的API地址
TENANT_ACCESS_TOKEN_URL = f"{FEISHU_HOST}/open-apis/auth/v3/tenant_access_token/internal"
# BITABLE_RECORDS_URL: 获取多维表格数据的API地址，需要填入应用ID和表格ID
BITABLE_RECORDS_URL = f"{FEISHU_HOST}/open-apis/bitable/v1/apps/{{}}/tables/{{}}/records"

# 获取飞书访问令牌 - 用于访问飞书API的身份验证
def get_tenant_access_token():
    """获取飞书租户访问令牌
    
    首先尝试从缓存中获取令牌，如果缓存中没有或已过期，
    则通过飞书API获取新的令牌并存入缓存。
    
    返回:
        成功返回访问令牌字符串，失败返回None
    """
    # 尝试从缓存获取token - 避免频繁请求API
    token = cache.get('tenant_access_token')
    if token:
        return token
    
    # 如果缓存中没有，则请求新token
    headers = {"Content-Type": "application/json"}
    payload = {
        "app_id": app.config['FEISHU_APP_ID'],
        "app_secret": app.config['FEISHU_APP_SECRET']
    }
    
    try:
        # 发送POST请求获取访问令牌
        response = requests.post(TENANT_ACCESS_TOKEN_URL, headers=headers, json=payload)
        response.raise_for_status()  # 如果请求失败会抛出异常
        data = response.json()
        
        if data.get('code') == 0:  # 0表示成功
            # 获取token成功，存入缓存
            token = data.get('tenant_access_token')
            # 设置缓存，比过期时间少5分钟，确保安全
            cache.set('tenant_access_token', token, timeout=data.get('expire') - 300)
            return token
        else:
            # 记录错误日志
            app.logger.error(f"获取飞书访问令牌失败: {data}")
            return None
    except Exception as e:
        # 捕获并记录所有异常
        app.logger.error(f"获取飞书访问令牌异常: {str(e)}")
        return None

# 获取多维表格数据
@cache.memoize(timeout=300)  # 使用缓存装饰器，缓存结果5分钟，减少API调用
def get_bitable_records():
    """从飞书多维表格获取博客文章数据
    
    使用飞书开放API获取多维表格中的所有记录，这些记录将作为博客文章展示。
    函数结果会被缓存5分钟，减少对飞书API的请求频率。
    
    返回:
        成功返回记录列表，失败返回空列表
    """
    # 首先获取访问令牌
    token = get_tenant_access_token()
    if not token:
        return []
    
    # 设置请求头，包含认证信息
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    # 构建API请求URL，填入应用ID和表格ID
    url = BITABLE_RECORDS_URL.format(
        app.config['BASE_ID'],  # 多维表格应用ID
        app.config['TABLE_ID']  # 具体表格ID
    )
    
    try:
        # 发送GET请求获取表格数据
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # 如果请求失败会抛出异常
        data = response.json()
        
        # 检查返回码，0表示成功
        if data.get('code') == 0:
            # 提取并返回记录列表
            return data.get('data', {}).get('items', [])
        else:
            # 记录错误日志
            app.logger.error(f"获取多维表格数据失败: {data}")
            return []
    except Exception as e:
        # 捕获并记录所有异常
        app.logger.error(f"获取多维表格数据异常: {str(e)}")
        return []

# 处理多维表格数据，转换为博客文章格式
def process_blog_data(records):
    """将飞书多维表格记录转换为博客文章格式
    
    从飞书API获取的原始数据格式不适合直接在模板中使用，
    此函数将其转换为更友好的格式，并按日期排序。
    
    参数:
        records: 从飞书多维表格获取的原始记录列表
        
    返回:
        处理后的博客文章列表，按日期降序排列
    """
    blogs = []
    for record in records:
        fields = record.get('fields', {})
        blog = {
            'id': record.get('record_id'),  # 记录ID作为博客ID
            'title': fields.get('标题', '无标题'),  # 获取标题，默认为'无标题'
            'date': fields.get('创建日期', ''),  # 创建日期
            'quote': fields.get('金句输出', ''),  # 文章金句
            'summary': fields.get('概要内容输出', ''),  # 文章摘要
            'link': fields.get('AI知识文章链接', '')  # 原文链接
        }
        blogs.append(blog)
    
    # 按日期排序，最新的在前面
    blogs.sort(key=lambda x: x.get('date', ''), reverse=True)
    return blogs

# 路由：首页
@app.route('/')
def index():
    """首页路由处理函数
    
    获取所有博客文章数据并渲染首页模板。
    首页显示所有博客文章的列表，按日期降序排列。
    
    返回:
        渲染后的首页HTML
    """
    records = get_bitable_records()
    blogs = process_blog_data(records)
    return render_template('index.html', blogs=blogs)

# 路由：文章详情页
@app.route('/blog/<string:blog_id>', methods=['GET', 'POST'])
def blog_detail(blog_id):
    """博客详情页路由处理函数
    
    显示指定ID的博客文章详情和评论列表，并处理新评论的提交。
    支持GET和POST两种请求方法：
    - GET: 显示博客详情和评论列表
    - POST: 提交新评论
    
    参数:
        blog_id: 博客文章的唯一标识符
        
    返回:
        GET请求: 渲染后的详情页HTML
        POST请求: 重定向到详情页
        找不到博客: 404错误页面
    """
    # 处理评论提交
    if request.method == 'POST':
        author = request.form.get('author', '匿名')  # 获取评论作者，默认为'匿名'
        content = request.form.get('content', '')  # 获取评论内容
        
        if content.strip():  # 确保评论内容不为空
            # 创建并保存评论
            comment = Comment(blog_id, author, content)
            save_comment(comment)
            return redirect(url_for('blog_detail', blog_id=blog_id))  # 重定向回详情页
    
    # 获取博客详情
    records = get_bitable_records()
    for record in records:
        if record.get('record_id') == blog_id:  # 找到匹配的博客记录
            blog = process_blog_data([record])[0]  # 处理博客数据
            # 加载该博客的评论
            comments = load_comments(blog_id)
            return render_template('detail.html', blog=blog, comments=comments)
    
    # 如果找不到对应的博客，返回404
    abort(404)

# 错误处理 - 自定义404页面
@app.errorhandler(404)
def page_not_found(e):
    """处理404错误，显示自定义的404页面
    
    参数:
        e: 错误对象
        
    返回:
        渲染后的404页面和404状态码
    """
    return render_template('404.html'), 404

# 清除缓存的路由（仅在开发环境使用）
@app.route('/clear-cache')
def clear_cache():
    """清除应用缓存的路由
    
    用于开发环境中手动清除缓存，便于测试数据更新。
    只有在DEBUG模式下才允许访问此路由。
    
    返回:
        成功: 成功消息和200状态码
        失败: 禁止访问消息和403状态码
    """
    if app.config['DEBUG']:
        cache.clear()
        return "缓存已清除", 200
    return "禁止访问", 403

if __name__ == '__main__':
    """应用程序入口点
    
    当直接运行此脚本时执行以下操作：
    1. 创建必要的目录结构
    2. 启动Flask Web服务器
    """
    # 创建必要的目录 - 确保应用所需的静态文件和模板目录存在
    os.makedirs('static/css', exist_ok=True)  # CSS文件目录
    os.makedirs('static/js', exist_ok=True)   # JavaScript文件目录
    os.makedirs('templates', exist_ok=True)   # HTML模板目录
    
    # 启动应用 - 监听所有网络接口，端口5000
    app.run(host='0.0.0.0', port=5000, debug=app.config['DEBUG'])