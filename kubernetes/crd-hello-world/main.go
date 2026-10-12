package main

import (
	"log"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/client-go/tools/clientcmd"
	ctrl "sigs.k8s.io/controller-runtime"
	metricsserver "sigs.k8s.io/controller-runtime/pkg/metrics/server"
)

func main() {
	// Explicitly select the tutorial Kind context. Never use whichever
	// cluster happens to be the user's current kubectl context.
	configLoader := clientcmd.NewNonInteractiveDeferredLoadingClientConfig(
		clientcmd.NewDefaultClientConfigLoadingRules(),
		&clientcmd.ConfigOverrides{CurrentContext: "kind-playground-crd"},
	)
	cfg, err := configLoader.ClientConfig()
	if err != nil {
		log.Fatal(err)
	}

	scheme := runtime.NewScheme()
	if err := corev1.AddToScheme(scheme); err != nil {
		log.Fatal(err)
	}
	gv := schema.GroupVersion{Group: "demo.example.com", Version: "v1"}
	scheme.AddKnownTypes(gv, &Greeting{}, &GreetingList{})
	metav1.AddToGroupVersion(scheme, gv)

	mgr, err := ctrl.NewManager(cfg, ctrl.Options{
		Scheme:  scheme,
		Metrics: metricsserver.Options{BindAddress: "0"},
	})
	if err != nil {
		log.Fatal(err)
	}

	reconciler := &GreetingReconciler{Client: mgr.GetClient(), Scheme: mgr.GetScheme()}
	if err := ctrl.NewControllerManagedBy(mgr).
		For(&Greeting{}).          // Watch the desired custom resources.
		Owns(&corev1.ConfigMap{}). // Also watch ConfigMaps owned by a Greeting.
		Complete(reconciler); err != nil {
		log.Fatal(err)
	}

	log.Println("Greeting controller started for Kind context kind-playground-crd")
	if err := mgr.Start(ctrl.SetupSignalHandler()); err != nil {
		log.Fatal(err)
	}
}
