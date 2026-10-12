package main

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
)

type GreetingSpec struct {
	Message string `json:"message"`
}

type Greeting struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`
	Spec              GreetingSpec `json:"spec,omitempty"`
}

type GreetingList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []Greeting `json:"items"`
}

// These two methods let controller-runtime safely copy our custom types.
// In larger projects, Kubebuilder generates the deepcopy methods for you.
func (in *Greeting) DeepCopyObject() runtime.Object {
	if in == nil {
		return nil
	}
	out := *in
	out.ObjectMeta = *in.ObjectMeta.DeepCopy()
	return &out
}

func (in *GreetingList) DeepCopyObject() runtime.Object {
	if in == nil {
		return nil
	}
	out := *in
	if in.Items != nil {
		out.Items = make([]Greeting, len(in.Items))
		for i := range in.Items {
			out.Items[i] = *(in.Items[i].DeepCopyObject().(*Greeting))
		}
	}
	return &out
}
