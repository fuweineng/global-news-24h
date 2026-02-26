# 阿里云百炼 API 配置指南

## 获取 API Key

1. 访问阿里云百炼控制台：https://bailian.console.aliyun.com/
2. 登录阿里云账号
3. 进入 **API-KEY 管理** 页面
4. 点击 **创建新的 API-KEY**
5. 复制生成的 API Key（格式：`sk-xxxxxxxxxxxxxxxx`）

## 配置方式（3 选 1）

### 方式 1：OpenClaw 全局配置（推荐）

编辑 `~/.openclaw/agents/main/agent/auth-profiles.json`：

```json
{
  "dashscope": {
    "apiKey": "sk-your-api-key-here"
  }
}
```

### 方式 2：项目本地配置

在项目根目录创建 `config.json`：

```json
{
  "dashscope_api_key": "sk-your-api-key-here"
}
```

### 方式 3：环境变量

```bash
export DASHSCOPE_API_KEY="sk-your-api-key-here"
```

## 使用模型

当前配置使用 **qwen-turbo**（快速且经济）：

- **qwen-turbo**: 快速翻译，适合短文本（推荐）
- **qwen-plus**: 更准确的翻译
- **qwen-max**: 最佳质量，适合复杂内容

修改 `src/fetch_news.py` 中的 `TRANSLATION_MODEL` 变量即可切换。

## 价格参考（2025）

- qwen-turbo: ¥0.002 / 1K tokens
- qwen-plus: ¥0.004 / 1K tokens
- qwen-max: ¥0.02 / 1K tokens

翻译 100 条新闻标题（约 5000 tokens）成本约 ¥0.01

## 测试翻译

```bash
cd ~/.openclaw/workspace/global-news-24h
python3 src/fetch_news.py
```

查看输出确认翻译是否正常工作。

## 故障排查

### 问题：未配置阿里云 API Key

**解决**: 按上述方式之一配置 API Key

### 问题：API 调用失败

**检查**:
1. API Key 是否正确
2. 网络连接是否正常
3. 阿里云账号是否有余额

### 问题：翻译质量不佳

**解决**: 
- 切换更高级的模型（qwen-plus 或 qwen-max）
- 调整提示词模板

## 相关链接

- 阿里云百炼控制台：https://bailian.console.aliyun.com/
- API 文档：https://help.aliyun.com/zh/dashscope/
- 模型列表：https://bailian.console.aliyun.com/model
