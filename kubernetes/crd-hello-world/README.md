# Lesson 2: Greeting Go Controller on Kind

**Prerequisite:** Complete Lesson 1 (CRD + CR), using Kind cluster `playground-crd` and API group `demo.example.com/v1` with `Greeting.spec.message`.

## Files
- `types.go`: Go types that describe `Greeting` and `GreetingList`.
- `controller.go`: the `Reconcile()` loop (read desired, read actual, create/update/no-op).
- `main.go`: select the exact Kind kubeconfig context, register types, start Manager and watches.
- `go.mod`: pinned `controller-runtime` version from KPCP.

## Commands (Windows PowerShell)

```powershell
cd .\kubernetes\crd-hello-world
go version
kubectl --context kind-playground-crd get greetings
go mod tidy
go run .
```

Keep `go run .` running. Open a **second** PowerShell terminal in any folder:

```powershell
kubectl --context kind-playground-crd get greeting hello
kubectl --context kind-playground-crd get cm hello-message -o yaml
kubectl --context kind-playground-crd patch greeting hello --type merge -p '{"spec":{"message":"Hello Controller!"}}'
kubectl --context kind-playground-crd get cm hello-message -o jsonpath='{.data.message}'
kubectl --context kind-playground-crd delete cm hello-message
kubectl --context kind-playground-crd get cm hello-message -o yaml
kubectl --context kind-playground-crd delete greeting hello
kubectl --context kind-playground-crd get cm hello-message
```

For the `kubectl patch` command, use PowerShell 7 or `kubectl apply -f hello.yaml` after editing the message if Windows PowerShell quoting causes a JSON error.

**Expected:** controller creates ConfigMap, updates changed message, restores deleted ConfigMap and (after deleting Greeting) Kubernetes garbage collector removes owned ConfigMap.

The controller runs on your **Windows host**, but connects to the Kind Kubernetes API. It is NOT yet a Deployment inside Kubernetes.

## If something fails
- `go: command not found`: install/update Go and restart terminal.
- `no context exists with name kind-playground-crd`: `kind get clusters`; ensure prior cluster exists.
- `no matches for kind Greeting`: apply `crd.yaml` from Lesson 1, and wait for CRD Established.
- No ConfigMap: inspect console logs from `go run .`, and check `kubectl --context kind-playground-crd get greeting hello -o yaml`.

## Next lesson
Add `Greeting.status` and run a Controller as a Deployment inside Kind, including least-privilege RBAC.
