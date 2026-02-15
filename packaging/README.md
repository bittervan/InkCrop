# InkCrop 打包说明（Windows / macOS / Linux）

目标：给最终用户一个可双击运行的包，不需要再安装 Python。

## 核心原则

- 必须在目标系统各自构建：
  - Windows 包在 Windows 上构建
  - macOS 包在 macOS 上构建
  - Linux 包在 Linux 上构建
- 不建议跨平台交叉编译 GUI 应用（稳定性差）。

## 1) 安装打包依赖

在项目根目录执行：

```bash
python -m pip install -U pip
python -m pip install -r packaging/requirements-build.txt
```

## 2) 构建

### 默认（`onefile`，便携分发）

```bash
python packaging/build.py
```

### 可选（`onedir`，目录包，启动略快）

```bash
python packaging/build.py --onedir
```

## 3) 构建产物

- 原始产物：
  - `dist/InkCrop`（Windows/Linux）
  - `dist/InkCrop.app`（macOS）
- 已打包分发文件：
  - `release/InkCrop-<system>-<arch>.zip`

## 4) 给最终用户的建议

- Windows：把 `zip` 解压后双击 `InkCrop.exe`
- macOS：把 `InkCrop.app` 拖到“应用程序”目录再运行
- Linux：解压后运行 `InkCrop`（必要时先 `chmod +x`）

## 5) 上线前建议

- Windows：建议给可执行文件做代码签名，减少 SmartScreen 拦截
- macOS：建议做 codesign + notarization，避免“无法验证开发者”提示
- Linux：尽量在较老版本系统构建，提高 glibc 兼容性

## 6) GitHub Actions 自动构建

仓库已提供工作流：`.github/workflows/build-binaries.yml`

- 手动触发：
  - GitHub → `Actions` → `Build InkCrop Binaries` → `Run workflow`
  - 会自动构建 `Windows amd64`、`Linux amd64`、`macOS amd64(Intel)`、`macOS arm64(Apple Silicon)` 并上传 artifacts
  - 当前 runner 标签：`macos-15-intel`（Intel）和 `macos-15`（Apple Silicon）
- 自动发布 Release：
  - 推送标签（例如 `v1.0.0`）后会构建全部平台并把 `zip` 附件发布到 GitHub Release
