from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.forms import ModelForm, ValidationError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.views import View
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.list import ListView
from tasks.models import Task


class AuthorizedTaskManager(LoginRequiredMixin):
    def get_queryset(self):
        return Task.objects.filter(deleted=False, user=self.request.user)


class UserLoginView(LoginView):
    template_name = "user_login.html"


class StyledUserCreationForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super(StyledUserCreationForm, self).__init__(*args, **kwargs)

        style = "text-black bg-gray-100 rounded-xl w-full my-1 p-3"
        self.fields["username"].widget.attrs.update({"class": style})
        self.fields["password1"].widget.attrs.update({"class": style})
        self.fields["password2"].widget.attrs.update({"class": style})


class UserCreateView(CreateView):
    form_class = StyledUserCreationForm
    template_name = "user_create.html"
    success_url = "/user/login"


class GenericTaskView(LoginRequiredMixin, ListView):
    queryset = Task.objects.filter(deleted=False, completed=False)
    template_name = "tasks.html"
    context_object_name = "tasks"

    def get_queryset(self):
        search_term = self.request.GET.get("search")
        view_type = self.request.GET.get("type")

        if view_type == "pending":
            tasks = Task.objects.filter(
                deleted=False, completed=False, user=self.request.user
            ).order_by("priority")
        elif view_type == "completed":
            tasks = Task.objects.filter(
                deleted=False, completed=True, user=self.request.user
            ).order_by("priority")
        else:
            tasks = Task.objects.filter(deleted=False, user=self.request.user).order_by(
                "priority"
            )
        if search_term:
            tasks = tasks.filter(title__icontains=search_term)
        return tasks

    def get_context_data(self):
        context = {"tasks": self.get_queryset()}
        context["completed_tasks"] = Task.objects.filter(
            deleted=False, completed=True, user=self.request.user
        ).count()
        context["total_tasks"] = Task.objects.filter(
            deleted=False, user=self.request.user
        ).count()
        return context


class GenericTaskDeleteView(AuthorizedTaskManager, DeleteView):
    model = Task
    template_name = "task_delete.html"
    success_url = "/tasks"


class TaskCreateForm(ModelForm):
    def clean_title(self):
        title = self.cleaned_data["title"]
        if len(title) < 3:
            raise ValidationError("Your Title should have more than 3 characters")
        return title

    class Meta:
        model = Task
        fields = ["title", "description", "priority", "completed"]

    def __init__(self, *args, **kwargs):
        super(TaskCreateForm, self).__init__(*args, **kwargs)

        style = "text-black bg-gray-100 rounded-xl w-full my-1 p-3 "

        self.fields["title"].widget.attrs.update({"class": style})
        self.fields["description"].widget.attrs.update({"class": style})
        self.fields["priority"].widget.attrs.update({"class": style})
        self.fields["completed"].widget.attrs.update(
            {
                "class": "form-check-input rounded bg-gray-100 checked:bg-green-500 appearance-none h-4 w-4 text-black"
            }
        )


class GenericTaskUpdateView(AuthorizedTaskManager, UpdateView):
    model = Task
    form_class = TaskCreateForm
    template_name = "task_update.html"
    success_url = "/tasks"

    def form_valid(self, form):
        self.object = form.save()
        self.object.user = None
        self.object.save()
        add_priority(self.object.priority, self.request.user, self.object.completed)
        self.object.user = self.request.user
        self.object.save()
        return HttpResponseRedirect(self.get_success_url())


class GenericTaskCreateView(CreateView):
    form_class = TaskCreateForm
    template_name = "task_create.html"
    success_url = "/tasks"

    def form_valid(self, form):
        self.object = form.save()
        add_priority(self.object.priority, self.request.user, self.object.completed)
        self.object.user = self.request.user
        self.object.save()
        return HttpResponseRedirect(self.get_success_url())


def add_priority(task_priority, username, completed):
    model_a = Task.objects.filter(
        priority=task_priority,
        deleted=False,
        completed=False,
        user=username,
    )
    if model_a.exists() and completed == False:
        model = (
            Task.objects.select_for_update()
            .filter(completed=False, deleted=False, user=username)
            .order_by("priority")
        )

        update_list = []

        for model_obj in model:
            if model_obj.priority == task_priority:
                model_obj.priority += 1
                task_priority += 1
                update_list.append(model_obj)
            elif model_obj.priority > task_priority:
                break
        Task.objects.select_for_update().bulk_update(
            update_list, ["priority"], batch_size=100
        )
