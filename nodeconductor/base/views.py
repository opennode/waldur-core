from django.shortcuts import render

from django.views.generic import FormView
from django.views.generic import TemplateView

# Create your views here.

class IndexView(TemplateView):
    template_name = 'base.html'

