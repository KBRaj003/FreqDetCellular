# -*- coding: utf-8 -*-

import math
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.clock import Clock
import nrarfcn as nr

import logging
from kivy.logger import Logger

# Keep only warnings and errors
logging.basicConfig(level=logging.WARNING)
Logger.setLevel(logging.WARNING)



try:
    from jnius import autoclass, cast
    _PA  = autoclass('org.kivy.android.PythonActivity')
    _CTX = autoclass('android.content.Context')
    _TM  = autoclass('android.telephony.TelephonyManager')
    tm = cast(_TM, _PA.mActivity.getSystemService(_CTX.TELEPHONY_SERVICE))
    ANDROID = True
except Exception:
    ANDROID = False
    tm = None

C = 299_792_458.0

def doppler_hz(fc_mhz, v, ang):
    return fc_mhz * 1e6 * (v / C) * math.cos(math.radians(ang))

def drift_hz(fc_mhz, ppm):
    return fc_mhz * 1e6 * ppm * 1e-6

def inst_freq_mhz(fc_mhz, v, ang, ppm):
    return (fc_mhz * 1e6 + doppler_hz(fc_mhz, v, ang) + drift_hz(fc_mhz, ppm)) / 1e6

class Detector:
    def __init__(self, n=20, t=2.5):
        self.w, self.n, self.t = [], n, t
    def update(self, x):
        self.w.append(x)
        if len(self.w) > self.n: self.w.pop(0)
        if len(self.w) < 5: return False
        m = sum(self.w) / len(self.w)
        var = sum((v - m) ** 2 for v in self.w) / len(self.w)
        if var == 0: return False
        return abs((x - m) / math.sqrt(var)) > self.t

class UI(BoxLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.orientation = "vertical"; self.padding = 20; self.spacing = 10
        self.labels = {}
        for name in ["Nominal Frequency", "Raw Frequency", "RSRP", "Velocity"]:
            self.add_widget(Label(text=name, size_hint_y=0.1))
            lbl = Label(text="--", size_hint_y=0.1)
            self.labels[name] = lbl
            self.add_widget(lbl)
        self.lbl_alert = Label(text="", color=(1, 0, 0, 1), size_hint_y=0.2)
        self.add_widget(self.lbl_alert)
        self.det = Detector()
        Clock.schedule_interval(self.tick, 1.0)

    def tick(self, dt):
        earfcn, rsrp, v, ang, ppm = 1300, -95.0, 10.0, 45.0, 0.1
        if ANDROID and tm:
            try: rsrp = tm.getSignalStrength().getLevel() * -10.0
            except Exception as e: logging.warning('Exception: %s', e, exc_info=True)
        try: nom = nr.get_frequency_by_lte_earfcn(earfcn)
        except Exception: nom = 1815.0
        raw = inst_freq_mhz(nom, v, ang, ppm)
        self.lbl_alert.text = "⚠ RSRP anomaly" if self.det.update(rsrp) else ""
        self.labels["Nominal Frequency"].text = f"{nom:.2f} MHz"
        self.labels["Raw Frequency"].text     = f"{raw:.6f} MHz"
        self.labels["RSRP"].text              = f"{rsrp:.1f} dBm"
        self.labels["Velocity"].text          = f"{v:.1f} m/s"

class FreqApp(App):
    def build(self): return UI()

if __name__ == "__main__":
    FreqApp().run()
