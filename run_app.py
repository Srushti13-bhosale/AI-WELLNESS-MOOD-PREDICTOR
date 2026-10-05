import threading
import time
import webbrowser

from app import app


def open_browser():
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:5000/")


if __name__ == "__main__":

    browser_thread = threading.Thread(
        target=open_browser
    )

    browser_thread.daemon = True
    browser_thread.start()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )