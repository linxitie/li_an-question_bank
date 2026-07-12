# 公安联考题库系统 - FastAPI后端服务

## 项目结构

```
backend/
├── main.py                 # 主应用入口
├── config.py               # 配置管理
├── database.py             # 数据库连接
├── models.py               # SQLAlchemy模型
├── schemas.py              # Pydantic验证模型
├── security.py             # JWT认证与密码加密
├── cache.py                # Redis缓存模块
├── requirements.txt        # 依赖列表
├── .env                    # 环境变量配置
├── start.py                # 启动脚本
└── routers/                # API路由模块
    ├── auth.py             # 认证模块
    ├── question.py         # 题库管理模块
    ├── paper.py            # 试卷管理模块
    ├── exam.py             # 考试执行模块
    ├── video.py            # 视频资源模块
    └── llm.py              # 大模型接口模块
```

## 技术栈

- **框架**: FastAPI 0.104.1
- **数据库**: MySQL 8.0+ (主从架构)
- **缓存**: Redis 6.0+
- **认证**: JWT + BCrypt
- **ORM**: SQLAlchemy 2.0
- **异步**: Uvicorn

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

编辑 `.env` 文件，配置数据库连接等参数：

```env
# 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=police_exam

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379

# JWT配置
JWT_SECRET_KEY=your-secret-key-here
```

### 3. 创建数据库

执行 SQL 文件创建数据库表：

```bash
mysql -u root -p < final_database.sql
```

### 4. 启动服务

```bash
python start.py
```

或使用 uvicorn 直接启动：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. 访问服务

- API文档: http://localhost:8000/docs
- 管理后台: http://localhost:8000/redoc

## API接口概览

### 认证模块
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/auth/login` | POST | 用户登录 |
| `/api/auth/register` | POST | 用户注册 |
| `/api/auth/me` | GET | 获取当前用户 |
| `/api/auth/checkin` | POST | 每日签到 |

### 题库管理
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/questions` | GET | 搜索题目 |
| `/api/questions` | POST | 创建题目 |
| `/api/questions/{id}` | GET | 获取题目详情 |
| `/api/questions/{id}` | PUT | 更新题目 |
| `/api/questions/{id}` | DELETE | 删除题目 |
| `/api/questions/batch` | POST | 批量导入 |

### 试卷管理
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/papers` | POST | 创建试卷 |
| `/api/papers/{id}` | GET | 获取试卷 |
| `/api/papers/{id}/questions` | POST | 添加题目 |
| `/api/papers/{id}/submit` | POST | 提交审批 |
| `/api/papers/{id}/approve` | POST | 审批试卷 |
| `/api/papers/{id}/publish` | POST | 发布试卷 |

### 考试执行
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/exam/start` | POST | 开始考试 |
| `/api/exam/{id}` | GET | 获取考试详情 |
| `/api/exam/{id}/answer` | POST | 提交答案 |
| `/api/exam/{id}/finish` | POST | 完成考试 |
| `/api/exam/{id}/analysis` | GET | 成绩分析 |

### 视频资源
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/video/upload` | POST | 上传视频 |
| `/api/video/upload/init` | POST | 初始化分片上传 |
| `/api/video/upload/chunk` | POST | 上传分片 |
| `/api/video/upload/complete` | POST | 完成上传 |
| `/api/video/{id}/stream` | GET | 流式播放 |

### 大模型接口
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/llm/chat` | POST | 大模型对话 |
| `/api/llm/search` | POST | 智能检索 |
| `/api/llm/generate` | POST | 智能生成题目 |
| `/api/llm/analyze` | POST | 智能分析答案 |

## 核心功能

1. **用户认证**: JWT令牌认证，支持学生/教师/管理员角色
2. **题库管理**: 支持题目CRUD、批量导入、审核流程
3. **试卷管理**: 自动组卷、手动组卷、审批流程、发布管理
4. **考试执行**: 在线答题、实时保存、自动评分、成绩分析
5. **视频资源**: 分片上传、断点续传、流式播放
6. **大模型集成**: 智能检索、题目生成、答案分析
7. **缓存策略**: Redis多级缓存、缓存击穿/穿透/雪崩防护

## 数据库设计

数据库包含以下核心表：

- `sys_user`: 用户信息表
- `question_subject`: 科目分类表
- `question_type`: 题型表
- `knowledge_point`: 知识点表
- `question_bank`: 题库主表
- `exam_paper`: 试卷主表
- `exam_record`: 考试记录表
- `video_resource`: 视频资源表

详细设计请参考 `final_database.sql` 文件。

## 部署建议

### 生产环境配置

1. **数据库**: 使用MySQL主从架构实现读写分离
2. **缓存**: 部署Redis集群
3. **负载均衡**: 使用Nginx或HAProxy
4. **进程管理**: 使用Gunicorn + Uvicorn
5. **日志监控**: 配置ELK或Prometheus + Grafana

### Docker部署

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 许可证

MIT License