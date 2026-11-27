# AgriTrust

Flask demo marketplace for produce, residue, farm supplies, machinery, and transport listings. Browsing and listing do not require an account. Login and signup remain optional.

## Run locally

Python 3.10 or newer is required.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

If Windows Application Control blocks SQLAlchemy's compiled extension, rebuild SQLAlchemy in pure-Python mode and start it again:

```powershell
$env:DISABLE_SQLALCHEMY_CEXT = '1'
.\.venv\Scripts\python.exe -m pip install --force-reinstall --no-binary=SQLAlchemy SQLAlchemy
.\.venv\Scripts\python.exe app.py
```

Open <http://127.0.0.1:5000>. The app creates its SQLite database and local session key in `instance/` and saves uploads in `static/uploads/`.

In VS Code, open this folder, choose **AgriTrust: Run Flask App** in **Run and Debug**, and press **F5**. The pre-launch task creates `.venv` and installs the pinned dependencies if needed.

Signup sends an email OTP when `MAIL_USERNAME` and `MAIL_PASSWORD` are configured. With debug mode enabled and no mail credentials, it displays a development OTP on the verification page. Set `FLASK_SECRET_KEY` and `FLASK_DEBUG=0` for a deployed environment.

Checkout records an order request and receipt for follow-up; it does not process payments or arrange delivery.

## Transaction analytics

Open **Analytics** from the Explore AgriTrust page or **Transaction Analytics** from either dashboard to view order trends, completed value, pending request value, products, and regional demand. On first start, AgriTrust seeds 150 reproducible synthetic transactions across the previous 12 months. Sample records are clearly marked. Checkout and machine rental requests plus manually entered records are saved in the shared SQLite database and included in analysis the next time the page loads. Use **Add a transaction record** to enter your own data or **Export CSV** to download the selected date range.
