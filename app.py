from flask import Flask, render_template, request, redirect, session
import pyotp

app = Flask(__name__)
app.secret_key = "secret123"

DEV_MODE = True  # Change to False for real use

# Fake database
users = {
    "joe": {
        "password": "password123",
        "otp_secret": pyotp.random_base32()
    }
    ,
    
    "John": {
        "password": "PanthersMan123",
        "otp_secret": pyotp.random_base32()
    }
,
    "Beth": {
        "password": "BethIsSleepy123",
        "otp_secret": pyotp.random_base32()
    }
    ,
    "Joel": {
        "password": "JoelsHere123",
        "otp_secret": pyotp.random_base32()
    }

}

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = users.get(username)

        if user and user["password"] == password:
            session["user"] = username
            return redirect("/otp")

        return "Login failed"

    return render_template("login.html")


@app.route("/otp", methods=["GET", "POST"])
def otp():
    user = users[session["user"]]
    totp = pyotp.TOTP(user["otp_secret"])

    generated_otp = None

    # Generate OTP for showcase
    if DEV_MODE:
        generated_otp = totp.now()

    if request.method == "POST":
        code = request.form["otp"]

        # DEV bypass
        if DEV_MODE and code == "000000":
            return "Login successful (DEV MODE)"

        if totp.verify(code):
            return "Login successful"

        return "Invalid OTP"

    return render_template("otp.html", otp_code=generated_otp)


if __name__ == "__main__":
    print(users["joe"]["otp_secret"])
    app.run(debug=True)