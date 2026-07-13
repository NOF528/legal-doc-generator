# 推送到 GitHub 指南

本地仓库已准备好，请按以下步骤推送到你的 GitHub 账号。

## 1. 设置 Git 用户名和邮箱（重要）

把下面的邮箱改成你的 GitHub 注册邮箱：

```bash
cd /Users/yumengyang/Desktop/代码/legal-doc-generator
git config user.name "你的GitHub用户名"
git config user.email "你的GitHub邮箱@example.com"
```

然后修正最近一次提交的作者信息：

```bash
git commit --amend --reset-author --no-edit
```

## 2. 在 GitHub 上创建仓库

1. 登录 https://github.com
2. 点击右上角 `+` → `New repository`
3. 填写：
   - **Repository name**: `history-evolution-generator`（建议，URL 友好）
   - **Description**: `历史沿革生成器 - 基于企查查 PDF 智能生成法律文书历史沿革`
   - **Visibility**: `Public`
4. 不要勾选 `Initialize this repository with a README`
5. 点击 `Create repository`

> 注意：GitHub 仓库名建议使用英文，中文名虽然支持但会导致 URL 和命令行操作不便。

## 3. 关联远程仓库并推送

创建完成后，GitHub 会显示类似下面的命令，直接复制执行：

```bash
cd /Users/yumengyang/Desktop/代码/legal-doc-generator
git remote add origin https://github.com/你的GitHub用户名/history-evolution-generator.git
git branch -M main
git push -u origin main
```

## 4. 验证

推送完成后，访问：

```
https://github.com/你的GitHub用户名/history-evolution-generator
```

应该能看到所有代码文件。

## 5. 如需私有仓库

创建仓库时选择 `Private` 即可，推送命令相同。
