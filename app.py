from functools import wraps

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from markupsafe import Markup, escape
from sqlalchemy import func

from analyzer import analyze_resume, split_items
from config import Config
from extensions import db
from models import Resume, User
from pdf_utils import generate_resume_pdf


RESUME_FIELDS = [
    "full_name",
    "email",
    "phone",
    "address",
    "career_objective",
    "skills",
    "education",
    "experience",
    "projects",
    "certifications",
    "languages",
    "achievements",
    "template",
]

TEMPLATES = {
    "professional": "Professional Template",
    "modern": "Modern Template",
    "simple": "Simple Template",
}


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)

    register_template_helpers(app)
    register_routes(app)
    register_cli(app)
    if app.config.get("AUTO_CREATE_DATABASE"):
        with app.app_context():
            db.create_all()
            ensure_admin_user(app)
    return app


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not get_current_user():
            flash("Please login to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        user = get_current_user()
        if not user:
            flash("Admin login required.", "warning")
            return redirect(url_for("admin_login", next=request.path))
        if not user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped_view


def owner_or_admin(resume):
    user = get_current_user()
    return user and (resume.user_id == user.id or user.is_admin)


def password_matches(user, password):
    try:
        return user.check_password(password)
    except ValueError:
        return False


def ensure_admin_user(app):
    admin = User.query.filter_by(email=app.config["ADMIN_EMAIL"]).first()
    if not admin:
        admin = User(
            full_name=app.config["ADMIN_NAME"],
            email=app.config["ADMIN_EMAIL"],
            is_admin=True,
        )
        admin.set_password(app.config["ADMIN_PASSWORD"])
        db.session.add(admin)
        db.session.commit()
        return "created"

    changed = False
    if not admin.is_admin:
        admin.is_admin = True
        changed = True
    if not password_matches(admin, app.config["ADMIN_PASSWORD"]):
        admin.set_password(app.config["ADMIN_PASSWORD"])
        changed = True
    if changed:
        db.session.commit()
        return "updated"
    return "exists"


def register_template_helpers(app):
    @app.context_processor
    def inject_globals():
        return {"current_user": get_current_user(), "resume_templates": TEMPLATES}

    @app.template_filter("nl2br")
    def nl2br(value):
        return Markup(escape(value or "").replace("\n", "<br>"))

    @app.template_filter("items")
    def items(value):
        return split_items(value)


def resume_from_form(resume):
    for field in RESUME_FIELDS:
        value = request.form.get(field, "").strip()
        if field == "template" and value not in TEMPLATES:
            value = "professional"
        setattr(resume, field, value)


def validate_resume_form():
    required = {
        "full_name": "Full name",
        "email": "Email",
        "phone": "Phone number",
    }
    errors = []
    for field, label in required.items():
        if not request.form.get(field, "").strip():
            errors.append(f"{label} is required.")
    return errors


def register_routes(app):
    @app.route("/")
    def index():
        if get_current_user():
            return redirect(url_for("dashboard"))
        return render_template("index.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            full_name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")

            if not full_name or not email or not password:
                flash("All fields are required.", "danger")
            elif password != confirm_password:
                flash("Password and confirm password do not match.", "danger")
            elif len(password) < 6:
                flash("Password must be at least 6 characters.", "danger")
            elif User.query.filter_by(email=email).first():
                flash("An account with this email already exists.", "danger")
            else:
                user = User(full_name=full_name, email=email)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                flash("Registration successful. Please login.", "success")
                return redirect(url_for("login"))

        return render_template("auth/register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email).first()

            if user and user.check_password(password):
                session.clear()
                session["user_id"] = user.id
                session["is_admin"] = user.is_admin
                flash("Login successful.", "success")
                next_url = request.args.get("next")
                if next_url:
                    return redirect(next_url)
                return redirect(url_for("dashboard"))

            flash("Invalid email or password.", "danger")

        return render_template("auth/login.html")

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email, is_admin=True).first()

            if user and user.check_password(password):
                session.clear()
                session["user_id"] = user.id
                session["is_admin"] = True
                flash("Admin login successful.", "success")
                return redirect(request.args.get("next") or url_for("admin_dashboard"))

            flash("Invalid admin credentials.", "danger")

        return render_template("auth/admin_login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been logged out.", "info")
        return redirect(url_for("index"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        user = get_current_user()
        resumes = (
            Resume.query.filter_by(user_id=user.id)
            .order_by(Resume.updated_at.desc())
            .all()
        )
        reports = []
        for resume in resumes:
            reports.append({"resume": resume, "analysis": analyze_resume(resume)})

        return render_template("dashboard.html", reports=reports)

    @app.route("/resume/new", methods=["GET", "POST"])
    @login_required
    def create_resume():
        resume = Resume(user_id=get_current_user().id, template="professional")
        if request.method == "POST":
            errors = validate_resume_form()
            resume_from_form(resume)
            if errors:
                for error in errors:
                    flash(error, "danger")
            else:
                db.session.add(resume)
                db.session.commit()
                flash("Resume created successfully.", "success")
                return redirect(url_for("preview_resume", resume_id=resume.id))

        return render_template("resume/form.html", resume=resume, mode="Create")

    @app.route("/resume/<int:resume_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_resume(resume_id):
        resume = db.session.get(Resume, resume_id) or abort(404)
        if not owner_or_admin(resume):
            abort(403)

        if request.method == "POST":
            errors = validate_resume_form()
            resume_from_form(resume)
            if errors:
                for error in errors:
                    flash(error, "danger")
            else:
                db.session.commit()
                flash("Resume updated successfully.", "success")
                return redirect(url_for("preview_resume", resume_id=resume.id))

        return render_template("resume/form.html", resume=resume, mode="Edit")

    @app.route("/resume/<int:resume_id>/preview")
    @login_required
    def preview_resume(resume_id):
        resume = db.session.get(Resume, resume_id) or abort(404)
        if not owner_or_admin(resume):
            abort(403)
        analysis = analyze_resume(resume)
        return render_template("resume/preview.html", resume=resume, analysis=analysis)

    @app.route("/resume/<int:resume_id>/analysis")
    @login_required
    def resume_analysis(resume_id):
        resume = db.session.get(Resume, resume_id) or abort(404)
        if not owner_or_admin(resume):
            abort(403)
        analysis = analyze_resume(resume)
        return render_template("resume/analysis.html", resume=resume, analysis=analysis)

    @app.route("/resume/<int:resume_id>/print")
    @login_required
    def print_resume(resume_id):
        resume = db.session.get(Resume, resume_id) or abort(404)
        if not owner_or_admin(resume):
            abort(403)
        return render_template("resume/print.html", resume=resume)

    @app.route("/resume/<int:resume_id>/download")
    @login_required
    def download_resume(resume_id):
        resume = db.session.get(Resume, resume_id) or abort(404)
        if not owner_or_admin(resume):
            abort(403)

        pdf = generate_resume_pdf(resume)
        filename = f"{resume.full_name.replace(' ', '_')}_resume.pdf"
        return send_file(
            pdf,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )

    @app.route("/resume/<int:resume_id>/delete", methods=["POST"])
    @login_required
    def delete_resume(resume_id):
        resume = db.session.get(Resume, resume_id) or abort(404)
        if not owner_or_admin(resume):
            abort(403)
        db.session.delete(resume)
        db.session.commit()
        flash("Resume deleted successfully.", "info")
        if get_current_user().is_admin:
            return redirect(url_for("admin_resumes"))
        return redirect(url_for("dashboard"))

    @app.route("/admin/dashboard")
    @admin_required
    def admin_dashboard():
        total_users = User.query.count()
        total_resumes = Resume.query.count()
        admin_count = User.query.filter_by(is_admin=True).count()
        latest_users = User.query.order_by(User.created_at.desc()).limit(5).all()
        latest_resumes = Resume.query.order_by(Resume.created_at.desc()).limit(5).all()
        template_stats = (
            db.session.query(Resume.template, func.count(Resume.id))
            .group_by(Resume.template)
            .all()
        )
        return render_template(
            "admin/dashboard.html",
            total_users=total_users,
            total_resumes=total_resumes,
            admin_count=admin_count,
            latest_users=latest_users,
            latest_resumes=latest_resumes,
            template_stats=template_stats,
        )

    @app.route("/admin/users")
    @admin_required
    def admin_users():
        users = User.query.order_by(User.created_at.desc()).all()
        return render_template("admin/users.html", users=users)

    @app.route("/admin/resumes")
    @admin_required
    def admin_resumes():
        resumes = Resume.query.order_by(Resume.created_at.desc()).all()
        reports = [{"resume": resume, "analysis": analyze_resume(resume)} for resume in resumes]
        return render_template("admin/resumes.html", reports=reports)

    @app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
    @admin_required
    def admin_delete_user(user_id):
        user = db.session.get(User, user_id) or abort(404)
        if user.id == get_current_user().id:
            flash("You cannot delete the active admin account.", "warning")
            return redirect(url_for("admin_users"))
        db.session.delete(user)
        db.session.commit()
        flash("User and related resumes deleted successfully.", "info")
        return redirect(url_for("admin_users"))

    @app.route("/health")
    def health():
        return {"status": "ok", "project": "AI Resume Builder and Analyzer"}


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        db.create_all()
        admin_status = ensure_admin_user(app)
        if admin_status == "created":
            print(f"Admin created: {app.config['ADMIN_EMAIL']} / {app.config['ADMIN_PASSWORD']}")
        elif admin_status == "updated":
            print(f"Admin updated: {app.config['ADMIN_EMAIL']} / {app.config['ADMIN_PASSWORD']}")
        else:
            print("Database tables created. Admin already exists.")


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
