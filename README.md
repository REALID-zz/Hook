# Hook

`Hook` 是一个 Ahelpis 原型仓库，当前同时包含：

- `app/`：`Starlette + SQLite` 后端，负责页面、接口、WebSocket 和文档路由
- `src/`：`Vite + React + TypeScript` 前端实验界面
- `android/`、`ios/`：`Capacitor` 原生壳工程
- `docs/`、`scripts/`、`tools/`：文档与辅助脚本

## 主要能力

- 社交通行证 / 卡片式主页
- `Now / Past / Future` 信息分层
- 场所级互动、邀约与公共入口
- `Universe`、`Emergency` 等原型页面
- 本地 `SQLite` 数据和上传目录

## 本地运行

### 后端

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

访问：

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/docs`

### 前端

```powershell
npm install
npm run dev
```

默认地址：

- `http://127.0.0.1:5173/`

### 原生端

```powershell
npm run build
npx cap sync
```

然后按需打开：

- `npx cap open android`
- `npx cap open ios`

## 数据与本地文件

- 本地数据库：`abang.sqlite3`
- 上传目录：`app/static/uploads/`
- 这些内容默认只建议本地保留，不建议直接提交

## 开发说明

- 场所种子数据在 `app/main.py` 中初始化
- 前端入口在 `src/main.tsx`
- 原生壳配置在 `capacitor.config.ts`
- 仓库已通过 `.gitignore` 排除依赖、构建产物、数据库、备份包和敏感文件

## 目录结构

```text
app/        Starlette 后端
src/        React 前端
android/    Capacitor Android
ios/        Capacitor iOS
docs/       项目文档
scripts/    辅助脚本
tools/      开发工具
```

