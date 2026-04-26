from flask import Flask, request, jsonify, render_template
import requests

app = Flask(__name__)

# Home page (your UI)
@app.route("/")
def home():
    return render_template("index.html")

# This replaces your old heavy /audit logic
@app.route("/audit", methods=["POST"])
def audit():
    data = request.get_json()

    # Call analyzer service
    res = requests.post(
        "http://analyzer:5001/analyze",   # use this for now (no docker)
        json=data
    )

    return jsonify(res.json())


if __name__ == "__main__":
    print("Starting backend...")
    app.run(host="0.0.0.0", port=5000, debug=True)
    