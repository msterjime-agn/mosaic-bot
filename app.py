from flask import Flask, render_template_string

app = Flask(__name__)

UNIVERSITIES = [
    {"name": "Kütahya Dumlupınar Üniversitesi", "city": "Kütahya", "status": "open", "dates": "14.05.2026 – 09.06.2026", "url": "https://iro.dpu.edu.tr/"},
    {"name": "Çukurova Üniversitesi", "city": "Adana", "status": "open", "dates": "11.05.2026 – 29.05.2026", "url": "https://iso.cu.edu.tr/"},
    {"name": "Trakya Üniversitesi", "city": "Edirne", "status": "unknown", "dates": "2026 takvim bekleniyor", "url": "https://disiliskiler.trakya.edu.tr/"},
    {"name": "Afyon Kocatepe Üniversitesi", "city": "Afyon", "status": "unknown", "dates": "2026 takvim bekleniyor", "url": "https://yos.aku.edu.tr/"},
    {"name": "Zonguldak Bülent Ecevit Üniversitesi", "city": "Zonguldak", "status": "unknown", "dates": "2026 takvim bekleniyor", "url": "https://iso.beun.edu.tr/"},
    {"name": "Uşak Üniversitesi", "city": "Uşak", "status": "unknown", "dates": "2026 takvim bekleniyor", "url": "https://admission.usak.edu.tr/"},
]

HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>University Hunter TR</title>
<style>
body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #0f172a;
    color: white;
}
.header {
    padding: 20px;
    background: #111827;
    position: sticky;
    top: 0;
}
h1 {
    margin: 0;
    font-size: 22px;
}
.sub {
    color: #94a3b8;
    font-size: 13px;
    margin-top: 6px;
}
.container {
    padding: 14px;
}
.card {
    background: #1e293b;
    border-radius: 18px;
    padding: 16px;
    margin-bottom: 14px;
    box-shadow: 0 8px 20px rgba(0,0,0,0.25);
}
.name {
    font-size: 17px;
    font-weight: bold;
}
.city {
    color: #cbd5e1;
    font-size: 14px;
    margin-top: 4px;
}
.badge {
    display: inline-block;
    padding: 6px 10px;
    border-radius: 999px;
    font-size: 13px;
    margin-top: 10px;
}
.open { background: #16a34a; }
.closed { background: #dc2626; }
.soon { background: #ca8a04; }
.unknown { background: #64748b; }
.dates {
    margin-top: 12px;
    color: #e2e8f0;
    font-size: 14px;
}
a {
    display: block;
    text-align: center;
    margin-top: 14px;
    padding: 12px;
    border-radius: 14px;
    background: #2563eb;
    color: white;
    text-decoration: none;
    font-weight: bold;
}
</style>
</head>
<body>
<div class="header">
    <h1>🎓 University Hunter TR</h1>
    <div class="sub">Гос. университеты Турции для иностранных студентов</div>
</div>

<div class="container">
{% for u in universities %}
<div class="card">
    <div class="name">{{ u.name }}</div>
    <div class="city">📍 {{ u.city }}</div>

    {% if u.status == "open" %}
        <div class="badge open">🟢 Приём открыт</div>
    {% elif u.status == "soon" %}
        <div class="badge soon">🟡 Скоро откроется</div>
    {% elif u.status == "closed" %}
        <div class="badge closed">🔴 Закрыт</div>
    {% else %}
        <div class="badge unknown">⚪ Дата неизвестна</div>
    {% endif %}

    <div class="dates">📅 {{ u.dates }}</div>
    <a href="{{ u.url }}" target="_blank">Открыть сайт</a>
</div>
{% endfor %}
</div>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML, universities=UNIVERSITIES)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
