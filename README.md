# 📊 波段猎手 - 云端盯盘推送

GitHub Actions 自动运行，无需本地电脑开机。
通过 PushPlus 推送到微信。

## 使用方法

### 1. Fork 这个仓库

点击右上角 Fork 按钮，复制到你自己的 GitHub。

### 2. 设置 Token

进入你 Fork 的仓库 → Settings → Secrets and variables → Actions → New repository secret

- Name: `PUSHPLUS_TOKEN`
- Value: 你的 PushPlus Token

### 3. 自动运行

每个交易日自动推送两次：
- 🌅 **9:00** 早盘分析
- 🌇 **14:20** 尾盘提醒

### 4. 手动测试

Actions 页面 → Stock Morning Report → Run workflow

## 如何修改配置

编辑 `stock_notifier.py` 中的：
- `HOLDINGS` → 持仓（成本、买卖区间）
- `WATCHLIST` → 关注列表

改完提交，自动生效。

## 注意事项

- GitHub Actions 的 cron 有几分钟延迟（正常5-15分钟）
- 如果需要秒级精准，建议配合本地 WorkBuddy 自动化一起用
