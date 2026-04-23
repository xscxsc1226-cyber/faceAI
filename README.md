# AI 面试官（Streamlit）

支持沉浸式面试、VAD 自动监听、Whisper 转写、自动追问、自动评分、Q&A 回放、Markdown/PDF 报告导出，并已补齐开源前常用能力：Auth、云存储、隐私策略、限流与成本监控。

当前默认推荐使用**火山引擎（方舟 OpenAI 兼容接口）**，不影响现有功能链路。

## 核心能力

- **面试流程**：摄像头 + 麦克风 + 自动语音分段 + Whisper 转写
- **自动追问**：按面试风格生成下一题并自动播报
- **自动复盘**：四维评分（专业度/逻辑性/抗压能力/沟通技巧）+ 改进文案
- **回放与导出**：时间戳 Q&A 回放 + Markdown/PDF 报告下载
- **Auth 与权限隔离**：支持 Supabase Email/Password 登录
- **云端存储**：Supabase Postgres + Storage（录音对象）
- **隐私与合规**：可配置保留周期、加密存储、用户一键删除
- **治理能力**：API 限流（每分钟）与 24 小时成本估算

## 本地启动

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 拷贝环境变量模板

```bash
copy .env.example .env
```

3. 启动

```bash
streamlit run app.py
```

## 环境变量说明

基础模型配置（火山/OpenAI 兼容）：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `QUESTION_MODEL`
- `EVALUATION_MODEL`
- `WHISPER_MODEL`
- `MAX_API_REQUESTS_PER_MIN`

数据与隐私配置：

- `SQLITE_DB_PATH`
- `RETENTION_DAYS`
- `PRIVACY_ENCRYPTION_KEY`（建议使用 Fernet key）

Supabase 配置：

- `ENABLE_SUPABASE=true/false`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_BUCKET`

## Supabase 必做手动步骤（详细）

### 1) 创建 Supabase 项目

在 [Supabase 控制台](https://supabase.com/) 新建项目。

### 2) 获取连接信息

在 `Project Settings -> API` 复制：

- `Project URL` -> 填入 `SUPABASE_URL`
- `anon public key` -> 填入 `SUPABASE_ANON_KEY`

### 3) 创建表与 RLS 策略

在 `SQL Editor` 执行 `supabase/schema.sql` 的全部内容。

### 4) 开启邮箱密码登录

在 `Authentication -> Providers` 中启用 `Email`。

### 5) 创建 Storage Bucket

`supabase/schema.sql` 已包含 bucket 与 policy；如提示已存在可忽略。

### 6) 更新本地 `.env`

```env
ENABLE_SUPABASE=true
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_BUCKET=interview-audio
```

### 7) 重启应用后验证

- 侧边栏切换“启用 Supabase 云端模式”
- 用邮箱注册/登录
- 完成一次面试并生成报告
- 在“历史面试记录”确认可读可导出

## 隐私合规操作流程（你需要手动确认）

1. 设置保留周期：`RETENTION_DAYS`（如 30）
2. 生成加密密钥（Fernet）并填入 `PRIVACY_ENCRYPTION_KEY`
3. 在 README 或仓库说明中明确：
   - 采集范围（语音/文本）
   - 保留时间
   - 删除方式（侧边栏“一键删除我的全部历史数据”）
4. 生产部署建议：将 `.env` 放在服务器密钥管理中，不进 Git

## API 限流与成本监控

- 每分钟限流阈值由 `MAX_API_REQUESTS_PER_MIN` 控制
- 侧边栏展示最近 24 小时请求数与估算成本
- 成本统计为估算值，用于趋势监控而非精确账单

## 开源发布前检查清单

1. `.env` 未提交（`.gitignore` 已配置）
2. `pytest` 通过
3. GitHub Actions CI 通过
4. Supabase schema 已在云端执行
5. License / Contributing / Code of Conduct 文件存在
6. `SECURITY.md` 已阅读并按要求配置密钥与保留策略

## 火山引擎配置示例

```env
OPENAI_API_KEY=你的火山引擎密钥
OPENAI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
QUESTION_MODEL=ep-你的聊天推理模型ID
EVALUATION_MODEL=ep-你的评分模型ID
WHISPER_MODEL=ep-你的语音识别模型ID
```

说明：
- 这里沿用 `OPENAI_*` 变量名，是因为代码走 OpenAI 兼容协议。
- 如果你使用其他兼容厂商，也只需替换 `OPENAI_BASE_URL` 和模型 ID。
