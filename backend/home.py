from flask import Blueprint, render_template, jsonify
from flask_login import current_user, login_required

# ---------------------------------
# Home / Dashboard Blueprint
# ---------------------------------

home_bp = Blueprint("home", __name__)


@home_bp.route("/dashboard")
@login_required
def dashboard():
    """
    Shown right after the user successfully signs in
    (login.js redirects here on success).
    """
    return render_template(
        "home.html",
        user_name=current_user.name,
        user_email=current_user.email
    )


@home_bp.route("/api/dashboard")
@login_required
def dashboard_data():
    """Optional JSON endpoint for the dashboard page to fetch user info."""
    return jsonify({
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email
    })