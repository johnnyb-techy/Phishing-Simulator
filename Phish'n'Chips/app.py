from flask import Flask, render_template, request, redirect, url_for
from flask_bcrypt import Bcrypt

from database import db
from models import User


app = Flask(__name__)

bcrypt = Bcrypt(app)


app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///phishing.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


db.init_app(app)


with app.app_context():
    db.create_all()



@app.route("/")
def home():

    return render_template("index.html")



@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        # Check if username already exists
        existing_username = User.query.filter_by(username=username).first()

        if existing_username:
            return "Username already exists"

        # Check if email already exists
        existing_email = User.query.filter_by(email=email).first()

        if existing_email:
            return "Email already registered"

        # Hash the password
        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")

        # Create the new user
        new_user = User(
            username=username,
            email=email,
            password_hash=hashed_password
        )

        # Save the user to the database
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("home"))

    return render_template("register.html")


if __name__ == "__main__":
    app.run(debug=True)