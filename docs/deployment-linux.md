# md2doc-web Linux 服务器部署指南

本指南面向"把 md2doc-web 部署到一台 Linux 服务器，供公司内网同事共用"的场景。

部署完成后效果：

- 同事浏览器访问 `http://<服务器IP>:8000` 即可使用
- 服务以 systemd 托管，开机自启、崩溃自动重启
- Nginx 反向代理（可选）+ 公司内网证书，提供 HTTPS 与统一端口
- 同一台机器上可同时部署 pandoc、mmdc、md2doc，无外部依赖

---

## 1. 环境要求

| 组件 | 版本 | 说明 |
|---|---|---|
| OS | CentOS 7+ / Ubuntu 18.04+ / Debian 10+ | 主流 Linux 均可 |
| Python | 3.9 ~ 3.12 | 推荐 3.11 |
| pandoc | ≥ 2.19 | md 转 docx 核心依赖 |
| Node.js | ≥ 18 | mermaid-cli 依赖 |
| mmdc | @mermaid-js/mermaid-cli | mermaid 图渲染 |
| Chromium | 系统包 | mmdc 渲染引擎 |
| 内存 | ≥ 2 GB | mmdc 渲染较吃内存 |

> 服务器无外网时，需在能联网的机器上把上述安装包下载后离线安装。

---

## 2. 安装系统依赖

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv \
                    pandoc nodejs npm \
                    chromium-browser \
                    nginx \
                    ca-certificates
```

### CentOS / RHEL

```bash
sudo yum install -y epel-release
sudo yum install -y python3 python3-pip \
                    pandoc nodejs npm \
                    chromium \
                    nginx \
                    ca-certificates
```

> CentOS 默认源的 Node.js 版本较旧，建议用 NodeSource 仓库装 Node 18：
> ```bash
> curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo bash -
> sudo yum install -y nodejs
> ```

---

## 3. 安装 mermaid-cli

```bash
sudo npm install -g @mermaid-js/mermaid-cli
```

验证：

```bash
mmdc --version         # 应输出版本号
pandoc --version       # 应输出 pandoc x.y
```

> 若 mmdc 在服务器上因 Chromium 沙箱启动失败（常见于容器环境），
> 在后续的 systemd 单元或启动脚本里加：
> ```bash
> export PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser
> export PUPPETEER_ARGS="--no-sandbox"
> ```
> 容器内运行必须 `--no-sandbox`，物理机若无安全约束也可加。

---

## 4. 部署 md2doc 代码

推荐用专用用户运行，避免 root。

```bash
sudo useradd -r -m -d /opt/md2doc -s /bin/bash md2doc
sudo -u md2doc -i
```

### 4.1 获取代码

任选其一：

```bash
# 方式 A：从 Git 仓库克隆
git clone <你的仓库地址> /opt/md2doc/app

# 方式 B：上传代码包（公司无 Git 服务器时）
# 本地打包后 scp 到服务器，解压到 /opt/md2doc/app
```

### 4.2 创建虚拟环境并安装

```bash
cd /opt/md2doc/app
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install ".[web]"
```

验证：

```bash
md2doc --version
md2doc-web --help
```

---

## 5. 配置 systemd 服务

让 md2doc-web 作为系统服务运行，开机自启、崩溃自动拉起。

创建 `/etc/systemd/system/md2doc-web.service`：

```bash
sudo tee /etc/systemd/system/md2doc-web.service > /dev/null <<'EOF'
[Unit]
Description=md2doc-web Service
After=network.target

[Service]
Type=simple
User=md2doc
Group=md2doc
WorkingDirectory=/opt/md2doc/app

# 虚拟环境与 Chrome 路径（按实际安装位置调整）
Environment="PATH=/opt/md2doc/app/.venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser"

# 若在容器中或遇到 Chromium 沙箱问题，取消下行注释
# Environment="PUPPETEER_ARGS=--no-sandbox"

ExecStart=/opt/md2doc/app/.venv/bin/md2doc-web --host 0.0.0.0 --port 8000

Restart=on-failure
RestartSec=3

# 日志
StandardOutput=journal
StandardError=journal
SyslogIdentifier=md2doc-web

[Install]
WantedBy=multi-user.target
EOF
```

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable md2doc-web      # 开机自启
sudo systemctl start md2doc-web       # 立即启动
sudo systemctl status md2doc-web      # 查看状态（应显示 active (running)）
```

查看实时日志：

```bash
sudo journalctl -u md2doc-web -f
```

---

## 6. 防火墙放行

### firewalld（CentOS 默认）

```bash
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

### ufw（Ubuntu 默认）

```bash
sudo ufw allow 8000/tcp
```

### iptables（无 firewalld/ufw 的环境）

```bash
sudo iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
# 持久化（Debian/Ubuntu）
sudo apt install iptables-persistent -y
sudo netfilter-persistent save
```

---

## 7. 验证访问

### 服务器本机

```bash
curl http://127.0.0.1:8000/ | head -5
# 应返回 HTML（index.html 内容）
```

### 内网同事

1. 查服务器 IP：
   ```bash
   ip addr | grep "inet " | grep -v 127.0.0.1
   # 例如：192.168.1.50
   ```
2. 同事浏览器访问：`http://192.168.1.50:8000`

---

## 8. （可选）Nginx 反向代理 + HTTPS

优势：用 80/443 标准端口、统一日志、加访问控制或 SSL。

### 8.1 安装 Nginx

```bash
sudo apt install -y nginx   # Ubuntu
sudo yum install -y nginx   # CentOS
```

### 8.2 配置站点

创建 `/etc/nginx/conf.d/md2doc.conf`：

```nginx
server {
    listen 80;
    server_name md2doc.intra.company.com;   # 改成你的内网域名或 IP

    client_max_body_size 20M;                # 上传上限（略大于 md2doc 的 10MB 限制）

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 长连接超时（mermaid 渲染可能耗时较长）
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

### 8.3 （可选）内网 HTTPS

将公司内网 CA 签发的证书放到 `/etc/nginx/ssl/`，在 server 块加：

```nginx
listen 443 ssl;
ssl_certificate     /etc/nginx/ssl/md2doc.crt;
ssl_certificate_key /etc/nginx/ssl/md2doc.key;
```

并把 80 端口重定向到 443：

```nginx
server {
    listen 80;
    server_name md2doc.intra.company.com;
    return 301 https://$host$request_uri;
}
```

### 8.4 启用

```bash
sudo nginx -t                    # 语法检查
sudo systemctl reload nginx
```

启用 Nginx 后，可把 md2doc-web 改为只监听本机：

```bash
# 编辑 /etc/systemd/system/md2doc-web.service
ExecStart=/opt/md2doc/app/.venv/bin/md2doc-web --host 127.0.0.1 --port 8000

sudo systemctl daemon-reload
sudo systemctl restart md2doc-web
```

---

## 9. （可选）基本访问控制

md2doc-web 本身无鉴权。若不想让整个内网随便访问，两种方案：

### 方案 A：Nginx Basic Auth（最简单）

```bash
sudo apt install -y apache2-utils          # 提供 htpasswd
sudo htpasswd -c /etc/nginx/.htpasswd colleague1
sudo htpasswd /etc/nginx/.htpasswd colleague2
```

Nginx 配置 `location /` 加：

```nginx
auth_basic           "Restricted";
auth_basic_user_file /etc/nginx/.htpasswd;
```

### 方案 B：内网 IP 白名单

```nginx
location / {
    allow 192.168.1.0/24;     # 允许的部门网段
    allow 10.0.0.0/8;
    deny  all;
    proxy_pass http://127.0.0.1:8000;
    ...
}
```

---

## 10. 日常运维

| 操作 | 命令 |
|---|---|
| 查看状态 | `sudo systemctl status md2doc-web` |
| 启动 / 停止 / 重启 | `sudo systemctl start|stop|restart md2doc-web` |
| 查看日志 | `sudo journalctl -u md2doc-web -f` |
| 查看最近 100 行日志 | `sudo journalctl -u md2doc-web -n 100` |
| 查看错误日志 | `sudo journalctl -u md2doc-web -p err` |
| 更新代码 | `cd /opt/md2doc/app && git pull && pip install -U . && sudo systemctl restart md2doc-web` |

---

## 11. 常见问题排查

### 11.1 启动失败：`address already in use`

端口被占用。查占用进程：
```bash
sudo ss -lntp | grep 8000
```
或换端口：`--port 8001`。

### 11.2 mermaid 渲染失败：mmdc 报 Chromium 错误

服务器缺少 Chrome 字体或沙箱权限不足。检查：
```bash
sudo -u md2doc mmdc -i /tmp/test.mmd -o /tmp/test.png
```
报 `No usable sandbox` → 在 systemd 单元加 `Environment="PUPPETEER_ARGS=--no-sandbox"`，并确认 `PUPPETEER_EXECUTABLE_PATH` 指向系统 chromium。

中文字体方块 → 安装中文字体：
```bash
sudo apt install -y fonts-noto-cjk fonts-wqy-zenhei   # Ubuntu
sudo yum install -y wqy-zenhei-cjk-fonts               # CentOS
```

### 11.3 mermaid 渲染失败：`ERR_FILE_NOT_FOUND`（dist/index.html）

**典型症状**：手动 `mmdc -i test.mmd -o test.png` 正常，通过 web 服务调用报此错。

**根因**：mmdc 渲染时会让无头浏览器加载自己安装目录下的 `dist/index.html`。若浏览器是 **snap 版 Chromium**（Ubuntu 20.04+ 的 `/usr/bin/chromium-browser` 默认是 snap 包装脚本），其沙箱**看不到 `/usr/lib/node_modules` 等路径**，于是真实存在的文件在浏览器视角里"不存在"。手动跑没问题，是因为登录 shell 没设 `PUPPETEER_EXECUTABLE_PATH`，mmdc 用的是 puppeteer 自带的非 snap Chromium；而 web 服务（systemd 单元或 md2doc 代码自动探测）注入了 snap 路径。

定位（确认是 snap）：

```bash
# 1) chromium-browser 是不是 snap 包装脚本（输出指向 /snap/... 即是）
readlink -f /usr/bin/chromium-browser

# 2) 手动复现：注入同样变量跑 mmdc —— 预期报出一模一样的错
PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser \
  mmdc -i /tmp/test.mmd -o /tmp/test.png
```

修复（任选其一，按优先级排序）：

```bash
# 方案 A（推荐）：装非 snap 的 Chrome，并让服务指过去
# Ubuntu:
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | \
  sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt update && sudo apt install -y google-chrome-stable
# systemd 单元里改为：Environment="PUPPETEER_EXECUTABLE_PATH=/usr/bin/google-chrome-stable"

# 方案 B：不指定浏览器，用 puppeteer 自带 Chromium（手动跑已验证可用）
# 删掉 systemd 单元中的 PUPPETEER_EXECUTABLE_PATH 行；
# 同时确认 md2doc ≥ 本版本（代码已自动跳过 snap 浏览器）

# 改完任意方案后重启
sudo systemctl daemon-reload && sudo systemctl restart md2doc-web
```

> 代码侧已修复（`src/md2doc/mermaid.py`）：Linux 上自动探测 Chrome 时会跳过
> `/snap/bin` 及指向 snap 的包装脚本，避免误注入。服务器需 `git pull` 更新代码。

### 11.4 同事浏览器打不开

按顺序排查：
1. 服务器进程在跑：`systemctl status md2doc-web`
2. 服务器本机能访问：`curl http://127.0.0.1:8000/`
3. 防火墙放行：`sudo firewall-cmd --list-ports` 或 `sudo ufw status`
4. IP 正确：让同事 `ping <服务器IP>` 看是否通

### 11.5 大文件转换超时

默认 Nginx 60s 超时。把 `proxy_read_timeout` 调到 300s（已在上方配置中给出）。

### 11.6 上传报 413

Nginx 默认 `client_max_body_size` 是 1MB。已在示例中设为 20M，若仍报错按需调大。

---

## 12. 部署清单（一次性核对）

- [ ] 系统依赖已装：pandoc、node、npm、chromium、nginx
- [ ] `mmdc --version` 与 `pandoc --version` 正常
- [ ] md2doc 代码已部署到 `/opt/md2doc/app`
- [ ] 虚拟环境已创建，`pip install ".[web]"` 成功
- [ ] systemd 单元已创建并 `enable + start`，状态 active
- [ ] 防火墙放行 8000（或 Nginx 的 80/443）
- [ ] 服务器本机 `curl` 验证通过
- [ ] 内网同事浏览器访问成功，能上传、预览、下载 docx
- [ ] （可选）Nginx 反向代理、HTTPS、访问控制已配置
- [ ] 中文字体已安装（mermaid 图含中文时不会显示方块）

---

*文档版本：2026-08-09*
