from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard_list, name="dashboard_list"),
    path("runs/<int:run_id>/", views.dashboard_detail, name="dashboard_detail"),
    path("runs/<int:run_id>/plot/", views.run_plot, name="run_plot"),
]