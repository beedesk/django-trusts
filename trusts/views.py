
from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.views.generic import CreateView, DetailView


class SelectUserForm(forms.Form):
    user = forms.ModelChoiceField(User.objects.all())


class NewTeamView(CreateView):
    'Create new team'
    model = Group
    fields = ('name',)

    def get_success_url(self):
        return '/'

    def form_valid(self, form):
        r = super(NewTeamView, self).form_valid(form)
        self.request.user.groups.add(self.object)
        return r
newteam = login_required(NewTeamView.as_view())


class TeamView(DetailView):
    'View team, manage its members'
    model = Group

    def dispatch(self, request, pk):
        # forbid access to non members
        if self.get_object() not in request.user.groups.all():
            return HttpResponseForbidden()
        self.adduserform = SelectUserForm(request.POST or None)
        if self.adduserform.is_valid():
            # add team member
            self.adduserform.cleaned_data['user'].groups.add(self.get_object())
            return redirect('.')
        return super(TeamView, self).dispatch(request, pk)
team = login_required(TeamView.as_view())
