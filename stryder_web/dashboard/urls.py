from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard_list, name="dashboard_list"),
    path("runs/<int:run_id>/", views.dashboard_detail, name="dashboard_detail"),

]