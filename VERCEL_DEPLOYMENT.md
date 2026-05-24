# Vercel 部署准备说明

## 当前结构

```text
BIYESHEJI/
  app.py                 # Vercel Flask WSGI 入口
  vercel.json            # Vercel 路由与函数打包配置
  .vercelignore          # 排除训练数据、模型权重、日志和文档
  .env.example           # 线上环境变量示例
  requirements.txt       # Vercel Python 依赖
  public/                # 前端静态资源
    index.html
    app.js
    styles.css
  backend/               # Flask 后端代码
  artifacts/             # 本地模型产物，默认不部署
  data/                  # 本地训练数据，默认不部署
  scripts/               # 本地数据处理脚本，默认不部署
```

## Vercel 线上必须配置的环境变量

```text
SECRET_KEY=一串足够长的随机字符串
SESSION_COOKIE_SECURE=1
DATABASE_URL=mysql+pymysql://USER:PASSWORD@HOST:3306/domain_security?charset=utf8mb4
```

注意：Vercel 云端不能访问你本机的 `127.0.0.1:3306` MySQL。正式部署前需要准备一个公网可访问或云服务内可访问的 MySQL 兼容数据库，并把连接串写入 `DATABASE_URL`。

## 需要注意

1. 当前 `artifacts/` 和 `data/` 已排除部署，避免 Vercel 函数包体过大。
2. 如果线上仍要使用 `.pt` 深度学习模型，建议后续把模型文件放到对象存储或独立推理服务；当前线上缺少模型文件时会回退到启发式/传统模型逻辑。
3. 本地运行方式不变：

```powershell
D:/Python/python3.11.3/python.exe E:/BIYESHEJI/run.py
```

