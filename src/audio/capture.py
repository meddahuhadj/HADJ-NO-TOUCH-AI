"""التقاط الميكروفون: إطارات int16 أحادية 16kHz بطول 30ms.

على Windows نستخدم WinMM (waveIn) مباشرة عبر ctypes بدل PortAudio/sounddevice:
تهيئة PortAudio تعدّد كل برامج تشغيل الصوت، وبعضها (WDM-KS على أجهزة Realtek مثلاً)
يعبث بمقابض (handles) لا تخصه، فيُفسد طوابير multiprocessing الموروثة في العملية الفرعية
(PermissionError / "semaphore released too many times" بشكل متقطع).
"""
from __future__ import annotations

import queue
import sys

from audio.vad import FRAME_BYTES, SAMPLE_RATE


class MicCapture:
    def start(self) -> None: ...
    def read(self, timeout: float) -> bytes | None: ...
    def close(self) -> None: ...


def open_microphone(device=None) -> MicCapture:
    if sys.platform == "win32":
        return WinMMCapture(device)
    return SoundDeviceCapture(device)


# ============================ Windows: WinMM ============================
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _winmm = ctypes.WinDLL("winmm")
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class WAVEFORMATEX(ctypes.Structure):
        _fields_ = [("wFormatTag", wintypes.WORD), ("nChannels", wintypes.WORD),
                    ("nSamplesPerSec", wintypes.DWORD), ("nAvgBytesPerSec", wintypes.DWORD),
                    ("nBlockAlign", wintypes.WORD), ("wBitsPerSample", wintypes.WORD),
                    ("cbSize", wintypes.WORD)]

    class WAVEHDR(ctypes.Structure):
        pass

    WAVEHDR._fields_ = [("lpData", ctypes.c_void_p), ("dwBufferLength", wintypes.DWORD),
                        ("dwBytesRecorded", wintypes.DWORD), ("dwUser", ctypes.c_size_t),
                        ("dwFlags", wintypes.DWORD), ("dwLoops", wintypes.DWORD),
                        ("lpNext", ctypes.POINTER(WAVEHDR)), ("reserved", ctypes.c_size_t)]

    class WAVEINCAPSW(ctypes.Structure):
        _fields_ = [("wMid", wintypes.WORD), ("wPid", wintypes.WORD), ("vDriverVersion", wintypes.UINT),
                    ("szPname", wintypes.WCHAR * 32), ("dwFormats", wintypes.DWORD),
                    ("wChannels", wintypes.WORD), ("wReserved1", wintypes.WORD)]

    WAVE_MAPPER = 0xFFFFFFFF
    CALLBACK_EVENT = 0x00050000
    WAVE_FORMAT_PCM = 1
    WHDR_DONE = 0x1
    HWAVEIN = wintypes.HANDLE

    _winmm.waveInOpen.argtypes = (ctypes.POINTER(HWAVEIN), wintypes.UINT, ctypes.POINTER(WAVEFORMATEX),
                                  ctypes.c_size_t, ctypes.c_size_t, wintypes.DWORD)
    for _fn in ("waveInPrepareHeader", "waveInUnprepareHeader", "waveInAddBuffer"):
        getattr(_winmm, _fn).argtypes = (HWAVEIN, ctypes.POINTER(WAVEHDR), wintypes.UINT)
    for _fn in ("waveInStart", "waveInStop", "waveInReset", "waveInClose"):
        getattr(_winmm, _fn).argtypes = (HWAVEIN,)
    _winmm.waveInGetDevCapsW.argtypes = (ctypes.c_size_t, ctypes.POINTER(WAVEINCAPSW), wintypes.UINT)
    _k32.CreateEventW.restype = wintypes.HANDLE
    _k32.CreateEventW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR)
    _k32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    _k32.CloseHandle.argtypes = (wintypes.HANDLE,)

    def list_input_devices() -> list[str]:
        names = []
        for i in range(_winmm.waveInGetNumDevs()):
            caps = WAVEINCAPSW()
            if _winmm.waveInGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps)) == 0:
                names.append(caps.szPname)
        return names

    class WinMMCapture(MicCapture):
        NUM_BUFFERS = 16

        def __init__(self, device=None):
            if isinstance(device, str):
                names = list_input_devices()
                match = [i for i, n in enumerate(names) if device.lower() in n.lower()]
                device = match[0] if match else None
            self.device = WAVE_MAPPER if device is None else int(device)
            self.hwi = HWAVEIN()
            self.event = None
            self.headers: list[WAVEHDR] = []
            self.buffers = []
            self.next = 0
            self.pending: queue.SimpleQueue[bytes] = queue.SimpleQueue()

        def _check(self, rc: int, what: str) -> None:
            if rc != 0:
                raise OSError(f"{what} فشل (MMRESULT={rc})")

        def start(self) -> None:
            fmt = WAVEFORMATEX(WAVE_FORMAT_PCM, 1, SAMPLE_RATE, SAMPLE_RATE * 2, 2, 16, 0)
            self.event = _k32.CreateEventW(None, False, False, None)
            self._check(_winmm.waveInOpen(ctypes.byref(self.hwi), self.device, ctypes.byref(fmt),
                                          self.event, 0, CALLBACK_EVENT), "waveInOpen")
            size = ctypes.sizeof(WAVEHDR)
            for _ in range(self.NUM_BUFFERS):
                buf = ctypes.create_string_buffer(FRAME_BYTES)
                hdr = WAVEHDR(ctypes.cast(buf, ctypes.c_void_p), FRAME_BYTES, 0, 0, 0, 0, None, 0)
                self._check(_winmm.waveInPrepareHeader(self.hwi, ctypes.byref(hdr), size), "prepare")
                self._check(_winmm.waveInAddBuffer(self.hwi, ctypes.byref(hdr), size), "addbuffer")
                self.buffers.append(buf)
                self.headers.append(hdr)
            self._check(_winmm.waveInStart(self.hwi), "waveInStart")

        def _collect(self) -> None:
            size = ctypes.sizeof(WAVEHDR)
            # المخازن تكتمل بالترتيب؛ نجمع كل ما اكتمل ونعيده للجهاز
            while True:
                hdr = self.headers[self.next]
                if not hdr.dwFlags & WHDR_DONE:
                    return
                data = ctypes.string_at(hdr.lpData, hdr.dwBytesRecorded)
                if len(data) == FRAME_BYTES:
                    self.pending.put(data)
                hdr.dwFlags &= ~WHDR_DONE
                hdr.dwBytesRecorded = 0
                _winmm.waveInAddBuffer(self.hwi, ctypes.byref(hdr), size)
                self.next = (self.next + 1) % len(self.headers)

        def read(self, timeout: float) -> bytes | None:
            try:
                return self.pending.get_nowait()
            except queue.Empty:
                pass
            _k32.WaitForSingleObject(self.event, int(timeout * 1000))
            self._collect()
            try:
                return self.pending.get_nowait()
            except queue.Empty:
                return None

        def close(self) -> None:
            if self.hwi:
                _winmm.waveInReset(self.hwi)
                size = ctypes.sizeof(WAVEHDR)
                for hdr in self.headers:
                    _winmm.waveInUnprepareHeader(self.hwi, ctypes.byref(hdr), size)
                _winmm.waveInClose(self.hwi)
                self.hwi = HWAVEIN()
            if self.event:
                _k32.CloseHandle(self.event)
                self.event = None


# ============================ أنظمة أخرى: sounddevice ============================
class SoundDeviceCapture(MicCapture):
    def __init__(self, device=None):
        self.device = device
        self.frames: queue.Queue[bytes] = queue.Queue(maxsize=400)
        self.stream = None

    def start(self) -> None:
        import sounddevice as sd

        def callback(indata, n, t, status):
            try:
                self.frames.put_nowait(bytes(indata))
            except queue.Full:
                pass

        self.stream = sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=FRAME_BYTES // 2,
                                        dtype="int16", channels=1, callback=callback,
                                        device=self.device)
        self.stream.start()

    def read(self, timeout: float) -> bytes | None:
        try:
            return self.frames.get(timeout=timeout)
        except queue.Empty:
            return None

    def close(self) -> None:
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
