from flask import Flask, request, jsonify
import requests, ssl, socket, time, logging
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from typing import Tuple, Optional
from datetime import datetime

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Configuration weights
WEIGHTS = {"security": 0.35, "performance": 0.30, "seo": 0.25, "accessibility": 0.10}

# ---------------- UTIL ----------------

def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url

def hostname_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        return parsed.netloc or url
    except Exception:
        return url

def fetch_page(url: str, timeout: float = 15.0):
    try:
        start = time.time()
        resp = requests.get(url, timeout=timeout, allow_redirects=True)
        elapsed = round(time.time() - start, 2)
        return resp, elapsed
    except Exception as e:
        logging.warning(f"Fetch failed: {e}")
        return None, None

def check_ssl_valid(hostname: str) -> Tuple[bool, Optional[str]]:
    try:
        ctx = ssl.create_default_context()
        clean_host = hostname.split(':')[0]
        with socket.create_connection((clean_host, 443), timeout=5.0) as sock:
            with ctx.wrap_socket(sock, server_hostname=clean_host) as ssock:
                ssock.getpeercert()
        return True, "Valid"
    except Exception as e:
        return False, str(e)

def letter_grade(score: int) -> str:
    if score >= 90: return "A+"
    if score >= 80: return "A"
    if score >= 70: return "B"
    if score >= 60: return "C"
    if score >= 50: return "D"
    return "F"

# ---------------- ANALYSIS ----------------

def analyze_security(resp, ssl_ok: bool):
    score, issues = 100, []
    if not ssl_ok:
        score -= 40
        issues.append("Invalid or missing SSL certificate")
    if 'Strict-Transport-Security' not in resp.headers:
        score -= 10
        issues.append("HSTS header missing")
    return {"score": max(0, score)}, issues

def analyze_performance(resp, load_time):
    if resp is None or load_time is None:
        return {"score": 0}, 0, ["No response data"]
    score = 100
    issues = []
    if load_time > 3:
        score -= 30
        issues.append(f"Slow response time: {load_time}s")
    elif load_time > 1.5:
        score -= 10
        issues.append("Moderate response delay")
    return {"load_time": load_time}, max(0, score), issues

def analyze_seo(html: str):
    soup = BeautifulSoup(html, "html.parser")
    issues, score = [], 100
    title = soup.title.string.strip() if soup.title else None
    if not title:
        score -= 30
        issues.append("Missing page title")
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if not meta_desc:
        score -= 20
        issues.append("Missing meta description")
    return {"title": title or "No title"}, max(0, score), issues

def analyze_accessibility(html: str):
    soup = BeautifulSoup(html, "html.parser")
    issues, score = [], 100
    imgs = soup.find_all('img')
    missing_alt = [img for img in imgs if not img.get('alt')]
    if missing_alt:
        score -= 20
        issues.append(f"{len(missing_alt)} images missing alt text")
    return {"images_count": len(imgs)}, max(0, score), issues

# ---------------- MAIN ROUTE ----------------

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json() or {}
        raw_url = data.get("url", "")
        url = normalize_url(raw_url)

        if not url:
            return jsonify({"error": "URL required"}), 400

        host = hostname_from_url(url)
        ssl_ok, ssl_err = check_ssl_valid(host)
        resp, load_time = fetch_page(url)

        if resp is None:
            return jsonify({"error": f"Could not reach {url}"}), 500

        # ---- EXECUTE ANALYSIS ----
        sec_metrics, sec_issues = analyze_security(resp, ssl_ok)
        perf_metrics, perf_score, perf_issues = analyze_performance(resp, load_time)
        seo_metrics, seo_score, seo_issues = analyze_seo(resp.text)
        acc_metrics, acc_score, acc_issues = analyze_accessibility(resp.text)

        # Calculate weighted average
        overall_score = int(
            (sec_metrics["score"] * WEIGHTS["security"]) +
            (perf_score * WEIGHTS["performance"]) +
            (seo_score * WEIGHTS["seo"]) +
            (acc_score * WEIGHTS["accessibility"])
        )

        total_issues = len(sec_issues) + len(perf_issues) + len(seo_issues) + len(acc_issues)

        return jsonify({
            "timestamp": datetime.utcnow().isoformat(),
            "url": url,
            "status": "success",
            "overall": {
                "score": overall_score,
                "grade": letter_grade(overall_score)
            },
            "security": {
                **sec_metrics,
                "issues": sec_issues
            },
            "performance": {
                **perf_metrics,
                "score": perf_score,
                "issues": perf_issues
            },
            "seo": {
                **seo_metrics,
                "score": seo_score,
                "issues": seo_issues
            },
            "accessibility": {
                **acc_metrics,
                "score": acc_score,
                "issues": acc_issues
            },
            "issues_count": {
                "critical": total_issues,
                "minor": 0
            }
        })

    except Exception as e:
        logging.error(f"Server Error: {e}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)