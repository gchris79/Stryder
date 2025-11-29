from django.shortcuts import render
from stryder_core.bootstrap import bootstrap_context_core
from stryder_core.path_memory import load_json, CONFIG_PATH
from stryder_core.usecases import get_last_week_for_ui


# Create your views here.
def dashboard_list(request):
    data = load_json(CONFIG_PATH)
    resolved = bootstrap_context_core(data)
    runs = get_last_week_for_ui()
    return render(
        request,"dashboard/dashboard_list.html",
        {"runs": runs},
    )
