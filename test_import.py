import sys, time
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
print(f'[{time.strftime("%H:%M:%S")}] Starting import...', flush=True)
t0 = time.time()
from PyQt6.QtWebEngineWidgets import QWebEngineView
t1 = time.time()
print(f'[{time.strftime("%H:%M:%S")}] QWebEngineView imported in {t1-t0:.1f}s', flush=True)
from PyQt6.QtWebChannel import QWebChannel
t2 = time.time()
print(f'[{time.strftime("%H:%M:%S")}] QWebChannel imported in {t2-t1:.1f}s', flush=True)
print('All done.', flush=True)
