from flask import Blueprint, render_template
from flask_login import login_required, current_user

from backend.login import role_required

home_bp = Blueprint("home", __name__)


# ---------------------------------
# Customer Dashboard
# ---------------------------------
@home_bp.route("/dashboard")
@login_required
@role_required("user")
def dashboard():
    return render_template(
        "home.html",
        user_name=current_user.name,
        user_email=current_user.email,
    )


# ---------------------------------
# Worker Dashboard  (the "admin" area from the Phase 2 spec,
# branded as Worker Dashboard per the request)
# ---------------------------------
@home_bp.route("/worker/dashboard")
@login_required
@role_required("worker")
def worker_dashboard():
    return render_template(
        "worker_dashboard.html",
        worker_name=current_user.name,
        worker_email=current_user.email,
    )