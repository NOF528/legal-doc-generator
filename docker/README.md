# 云端部署指南

## 快速开始（5分钟完成部署）

### 1. 购买服务器

**推荐配置**（按您的选择）：
- 地区：香港/新加坡/东京（免备案）
- 配置：2核4G，50GB SSD
- 带宽：5Mbps（足够10人同时使用）
- 系统：Ubuntu 22.04 LTS
- 价格：约 80-120元/月

**推荐厂商**：
- 阿里云国际版（香港）
- 腾讯云轻量应用服务器
- Vultr / DigitalOcean

### 2. 连接服务器

```bash
# 使用SSH连接（Mac/Linux自带，Windows可用PowerShell）
ssh root@你的服务器IP

# 示例
ssh root@203.0.113.1
```

### 3. 一键部署

```bash
# 下载代码
git clone https://github.com/yourusername/legal-doc-generator.git /opt/legal-doc-generator
cd /opt/legal-doc-generator/docker

# 运行部署脚本
chmod +x deploy.sh
sudo ./deploy.sh
```

### 4. 访问系统

部署完成后会显示：
```
访问地址: http://你的服务器IP
用户名: legaluser
密码: （你设置的密码）
```

**微信分享**：直接分享 `http://服务器IP` 即可

---

## 模板上传

### 方法一：直接上传到服务器

```bash
# 在本地电脑上执行
scp 历史沿革模板.docx root@服务器IP:/opt/legal-doc-generator/backend/templates/word/
```

### 方法二：使用SFTP工具

使用 FileZilla、WinSCP 等工具连接服务器，上传到：
```
/opt/legal-doc-generator/backend/templates/word/
```

### 模板占位符说明

| 占位符 | 说明 |
|--------|------|
| `{{company_name}}` | 公司名称 |
| `{{history_content}}` | 历史沿革正文（自动解析） |
| `{{report_date}}` | 报告生成日期 |
| `{{change_count}}` | 变更次数 |
| `{{law_firm_name}}` | 律所名称（用户填写） |
| `{{lawyer_name}}` | 律师姓名（用户填写） |

---

## 日常维护

### 查看状态
```bash
cd /opt/legal-doc-generator/docker
docker-compose ps
```

### 查看日志
```bash
# 查看所有日志
docker-compose logs -f

# 只看后端日志
docker-compose logs -f backend

# 只看前端日志
docker-compose logs -f frontend
```

### 重启服务
```bash
docker-compose restart
```

### 停止服务
```bash
docker-compose down
```

### 更新代码
```bash
# 更新所有
cd /opt/legal-doc-generator/docker
./update.sh all

# 只更新前端
./update.sh frontend

# 只更新后端
./update.sh backend
```

---

## 模块化设计说明

### 架构图

```
┌─────────────────────────────────────┐
│           Nginx (入口)               │
│    - 密码保护    - 路由分发           │
└──────────────┬──────────────────────┘
               │
      ┌────────┴────────┐
      │                 │
┌─────▼─────┐    ┌──────▼──────┐
│  Frontend │    │   Backend   │
│  (Next.js)│    │  (FastAPI)  │
│  :3000    │    │   :8000     │
└───────────┘    └─────────────┘
      │                 │
      │          ┌──────┴──────┐
      │          │  Templates  │
      │          │  (Word模板)  │
      │          └─────────────┘
```

### 升级策略

**独立升级前端**：
```bash
# 修改前端代码后
./update.sh frontend
# 后端不受影响
```

**独立升级后端**：
```bash
# 修改后端代码后
./update.sh backend
# 前端不受影响
```

**添加新提取器**（工商内档等）：
```bash
# 1. 在 backend/app/services/ 下新建提取器目录
# 2. 添加API路由
# 3. 升级后端
./update.sh backend
```

---

## 安全加固（可选）

### 修改密码

```bash
# 进入docker目录
cd /opt/legal-doc-generator/docker

# 生成新密码文件
htpasswd -cb nginx/.htpasswd legaluser 新密码

# 重启nginx
docker-compose restart nginx
```

### 添加HTTPS（推荐生产环境使用）

```bash
# 1. 准备域名和SSL证书
# 2. 将证书放入 nginx/ssl/ 目录
# 3. 修改 nginx.conf 启用443端口
# 4. 重启
docker-compose restart nginx
```

### 防火墙设置

```bash
# 只开放80和443端口
ufw default deny incoming
ufw default allow outgoing
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 22/tcp  # SSH
ufw enable
```

---

## 故障排查

### 无法访问

1. 检查服务状态
```bash
docker-compose ps
```

2. 检查防火墙
```bash
ufw status
```

3. 检查端口占用
```bash
netstat -tlnp | grep 80
```

### 生成Word失败

查看后端日志：
```bash
docker-compose logs -f backend
```

常见问题：
- 内存不足：检查 `docker stats`
- 模板错误：检查模板占位符格式

### 密码忘记

重新生成密码文件：
```bash
cd /opt/legal-doc-generator/docker
htpasswd -cb nginx/.htpasswd legaluser 新密码
docker-compose restart nginx
```

---

## 成本优化

### 当前配置月费用

| 项目 | 费用 | 说明 |
|------|------|------|
| 云服务器（2核4G） | ~100元 | 香港节点 |
| 流量 | ~20元 | 按实际使用 |
| **总计** | **~120元/月** | 支持5-10人 |

### 降低费用方案

**方案1：按量付费**
- 白天开启，晚上关闭
- 适合非7x24小时使用

**方案2：使用轻量应用服务器**
- 腾讯云/阿里云轻量服务器
- 约 50-80元/月
- 配置略低但够用

---

## 联系支持

如有问题，请查看日志：
```bash
cd /opt/legal-doc-generator/docker
docker-compose logs > error.log 2>&1
```
