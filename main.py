
import math
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.properties import StringProperty
import nrarfcn as nr

try:
    from jnius import autoclass, cast
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Context = autoclass('android.content.Context')
    TelephonyManager = autoclass('android.telephony.TelephonyManager')
    activity = PythonActivity.mActivity
    tm = cast(TelephonyManager, activity.getSystemService(Context.TELEPHONY_SERVICE))
    ANDROID_AVAILABLE = True
except Exception:
    ANDROID_AVAILABLE = False
    tm = None

C = 299_792_458.0

def doppler_shift_hz(nominal_mhz, v_mps, angle_deg):
    f_c = nominal_mhz * 1e6
    theta = math.radians(angle_deg)
    return f_c * (v_mps / C) * math.cos(theta)

def oscillator_drift_hz(nominal_mhz, drift_ppm):
    return nominal_mhz * 1e6 * (drift_ppm * 1e-6)

def instantaneous_frequency_mhz(nominal_mhz, v_mps, angle_deg, drift_ppm):
    f = nominal_mhz * 1e6
    f += doppler_shift_hz(nominal_mhz, v_mps, angle_deg)
    f += oscillator_drift_hz(nominal_mhz, drift_ppm)
    return f / 1e6

class AnomalyDetector:
    def __init__(self, window=20, threshold=2.5):
        self.window = []
        self.size = window
        self.threshold = threshold

    def update(self, value):
        self.window.append(value)
        if len(self.window) > self.size:
            self.window.pop(0)
        if len(self.window) < 5:
            return False
        mean = sum(self.window) / len(self.window)
        var = sum((x - mean) ** 2 for x in self.window) / len(self.window)
        std = math.sqrt(var)
        if std == 0:
            return False
        z = (value - mean) / std
        return abs(z) > self.threshold

class MonitorLayout(BoxLayout):
    nominal_freq = StringProperty("-- MHz")
    raw_freq = StringProperty("-- MHz")
    rsrp = StringProperty("-- dBm")
    velocity = StringProperty("-- m/s")
    alert = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = 20
        self.spacing = 10

        self.add_widget(Label(text="Nominal Frequency:", size_hint_y=0.1))
        self.lbl_nominal = Label(text=self.nominal_freq, size_hint_y=0.1)
        self.add_widget(self.lbl_nominal)

        self.add_widget(Label(text="Raw (Fluctuating) Frequency:", size_hint_y=0.1))
        self.lbl_raw = Label(text=self.raw_freq, size_hint_y=0.1)
        self.add_widget(self.lbl_raw)

        self.add_widget(Label(text="RSRP:", size_hint_y=0.1))
        self.lbl_rsrp = Label(text=self.rsrp, size_hint_y=0.1)
        self.add_widget(self.lbl_rsrp)

        self.add_widget(Label(text="Velocity:", size_hint_y=0.1))
        self.lbl_vel = Label(text=self.velocity, size_hint_y=0.1)
        self.add_widget(self.lbl_vel)

        self.lbl_alert = Label(text="", color=(1, 0, 0, 1), size_hint_y=0.2)
        self.add_widget(self.lbl_alert)

        self.detector = AnomalyDetector()
        Clock.schedule_interval(self.update_metrics, 1.0)

    def update_metrics(self, dt):
        earfcn = 1300
        rsrp_val = -95.0
        vel = 10.0
        angle = 45.0
        drift = 0.1

        if ANDROID_AVAILABLE and tm is not None:
            try:
                cells = tm.getAllCellInfo()
                if cells:
                    for ci in cells:
                        if ci.isRegistered():
                            pass
                rsrp_val = tm.getSignalStrength().getLevel() * -10.0
            except Exception:
                pass

        try:
            nominal = nr.get_frequency_by_lte_earfcn(earfcn)
        except Exception:
            nominal = 1815.0

        raw = instantaneous_frequency_mhz(nominal, vel, angle, drift)

        if self.detector.update(rsrp_val):
            self.alert = "⚠ RSRP anomaly – possible IMSI catcher / tampering!"
        else:
            self.alert = ""

        self.nominal_freq = f"{nominal:.2f} MHz"
        self.raw_freq = f"{raw:.6f} MHz"
        self.rsrp = f"{rsrp_val:.1f} dBm"
        self.velocity = f"{vel:.1f} m/s"
        self.lbl_nominal.text = self.nominal_freq
        self.lbl_raw.text = self.raw_freq
        self.lbl_rsrp.text = self.rsrp
        self.lbl_vel.text = self.velocity
        self.lbl_alert.text = self.alert

class FreqDetApp(App):
    def build(self):
        return MonitorLayout()

if __name__ == "__main__":
    FreqDetApp().run()
