package main

import (
	"context"
	"fmt"
	"log"

	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"
)

type GreetingReconciler struct {
	client.Client
	Scheme *runtime.Scheme
}

func (r *GreetingReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	// 1. Read desired state (Greeting).
	greeting := &Greeting{}
	if err := r.Get(ctx, req.NamespacedName, greeting); err != nil {
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}

	name := greeting.Name + "-message"
	key := types.NamespacedName{Name: name, Namespace: greeting.Namespace}
	actual := &corev1.ConfigMap{}

	// 2. Read actual state (ConfigMap).
	err := r.Get(ctx, key, actual)
	if apierrors.IsNotFound(err) {
		// 3a. Missing: create the desired ConfigMap.
		desired := &corev1.ConfigMap{
			ObjectMeta: metav1.ObjectMeta{Name: name, Namespace: greeting.Namespace},
			Data:       map[string]string{"message": greeting.Spec.Message},
		}
		if err := controllerutil.SetControllerReference(greeting, desired, r.Scheme); err != nil {
			return ctrl.Result{}, err
		}
		log.Printf("CREATE ConfigMap %s/%s message=%q", greeting.Namespace, name, greeting.Spec.Message)
		return ctrl.Result{}, r.Create(ctx, desired)
	}
	if err != nil {
		return ctrl.Result{}, err
	}

	// Do not overwrite a pre-existing ConfigMap owned by someone else.
	if !metav1.IsControlledBy(actual, greeting) {
		return ctrl.Result{}, fmt.Errorf("ConfigMap %s/%s is not controlled by Greeting %s", actual.Namespace, actual.Name, greeting.Name)
	}

	// 3b. Different: update the existing ConfigMap.
	if actual.Data == nil {
		actual.Data = map[string]string{}
	}
	if actual.Data["message"] != greeting.Spec.Message {
		actual.Data["message"] = greeting.Spec.Message
		log.Printf("UPDATE ConfigMap %s/%s message=%q", greeting.Namespace, name, greeting.Spec.Message)
		return ctrl.Result{}, r.Update(ctx, actual)
	}

	// 3c. Already correct: do nothing (idempotent).
	log.Printf("UNCHANGED ConfigMap %s/%s", greeting.Namespace, name)
	return ctrl.Result{}, nil
}
