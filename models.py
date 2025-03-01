import datetime
import json
import os

# 评论数据存储路径
COMMENTS_FILE = 'comments.json'

class Comment:
    def __init__(self, blog_id, author, content, created_at=None):
        self.id = self._generate_id()
        self.blog_id = blog_id
        self.author = author
        self.content = content
        self.created_at = created_at or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def _generate_id(self):
        """生成唯一ID"""
        import uuid
        return str(uuid.uuid4())
    
    def to_dict(self):
        """将评论转换为字典格式"""
        return {
            'id': self.id,
            'blog_id': self.blog_id,
            'author': self.author,
            'content': self.content,
            'created_at': self.created_at
        }

def save_comment(comment):
    """保存评论到JSON文件"""
    comments = load_comments()
    comments.append(comment.to_dict())
    
    with open(COMMENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(comments, f, ensure_ascii=False, indent=4)

def load_comments(blog_id=None):
    """加载评论数据
    
    从JSON文件中读取所有评论数据。如果指定了blog_id，则只返回该博客的评论。
    如果文件不存在或读取失败，则返回空列表。
    
    参数:
        blog_id: 可选，指定要加载哪个博客的评论
        
    返回:
        评论字典的列表
    """
    if not os.path.exists(COMMENTS_FILE):
        return []
    
    try:
        with open(COMMENTS_FILE, 'r', encoding='utf-8') as f:
            comments = json.load(f)
            
            # 如果指定了blog_id，则只返回该博客的评论
            if blog_id:
                return [c for c in comments if c['blog_id'] == blog_id]
            
            return comments
    except Exception as e:
        print(f"加载评论数据失败: {str(e)}")
        return []