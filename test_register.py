import re
from app import create_app

app = create_app()

with app.test_client() as c:
    r = c.get('/register')
    html = r.get_data(as_text=True)
    m = re.search(r'<div class="otp-box">(\d{6})</div>', html)
    otp = m.group(1) if m else None
    print('OTP:', otp)
    data = {
        'username': 'test_user_otp',
        'password': 'pass1234',
        'phone': '0900000000',
        'email': 'test@example.com',
        'otp': otp or '000000'
    }
    p = c.post('/register', data=data, follow_redirects=False)
    print('POST status:', p.status_code)
    print('Location:', p.headers.get('Location'))
