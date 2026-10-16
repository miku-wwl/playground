# Kubebuilder Hello World

**难度：Beginner**

从空的 Kubebuilder 项目开始，逐步定义 `Greeting` API、生成 CRD、在 Kind 中使用，再让 Controller 根据 `spec.message` 创建并同步 ConfigMap。

## 学习阶段

### Phase 1 — Hello Kubebuilder

- 安装 Kubebuilder 并创建空 Go 项目。
- 学习 Kubebuilder 是什么、`init` 做什么，以及生成目录的用途。
- 不写业务代码，不需要 Kubernetes 集群。
- 状态：已完成项目初始化。

### Phase 2 — Hello API

- 执行 `kubebuilder create api`，生成 `Greeting` API 和 Controller 框架。
- 学习 `Group`、`Version`、`Kind`、`Spec`、`Status`。

### Phase 3 — Hello CRD

- 给 `GreetingSpec` 添加 `message` 字段，通过 `make manifests` 生成 YAML。
- 学习 Go Struct 如何映射到 CRD YAML，以及代码生成和手写 CRD 的区别。

### Phase 4 — Hello Kubernetes

- 将生成的 CRD 安装到 Kind 集群，用 `kubectl` 创建、查询、修改 `Greeting`。
- 学习 Kubebuilder 生成的 API 如何进入 Kubernetes。

### Phase 5 — Hello Controller

- 运行 Controller，监听 `Greeting` 变化，先只打印日志。
- 学习 Manager、Reconcile、Watch。

### Phase 6 — Hello Operator

- 给 Controller 添加最简单的业务逻辑：读取 `spec.message`，自动创建 ConfigMap，并同步后续修改。
- 学习如何用声明式 API 驱动真实资源。

## Phase 1 项目骨架

当前项目由 Kubebuilder `init` 生成，包含 Manager 入口和部署配置骨架，但还没有 API 类型或业务 Controller：

| 路径 | 用途 |
| --- | --- |
| `cmd/main.go` | 程序入口，创建并启动 Controller Manager |
| `config/` | Manager、RBAC、监控和 Kustomize 配置；创建 API 后会补充 CRD 配置 |
| `hack/` | 项目生成和开发辅助文件，例如 Go 许可证头模板 |
| `Makefile` | 后续生成代码、构建和部署的命令入口 |
| `Dockerfile` | 构建 Manager 容器镜像的模板 |
| `PROJECT` | Kubebuilder 项目元数据及插件布局 |
| `go.mod`、`go.sum` | Go 模块路径和依赖版本 |

本阶段没有生成 `api/`、`internal/controller/`、Greeting 类型、CRD YAML 或业务逻辑；Kind 集群也没有被访问或修改。

## 本项目初始化命令

```powershell
kubebuilder init --domain example.com --repo example.com/kubebuilder-hello-world --plugins=go/v4
```

后续创建 Greeting 时使用 `--group demo --version v1 --kind Greeting`，其 API 组会是 `demo.example.com`。
