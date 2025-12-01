import pyaudio
import wave
from PySide6.QtCore import QObject, Signal, QRunnable, Slot, QThreadPool
import time
import speech_recognition as sr

# --- Configuration for PyAudio Streaming ---
CHUNK = 1024  
FORMAT = pyaudio.paInt16 
CHANNELS = 1
RATE = 16000 
LANGUAGE_CODE = 'en-US' 
# --------------------------------------------

class MicrophoneSignals(QObject):
    text = Signal(str)
    error = Signal(str)
    started = Signal()
    stopped = Signal()

class MicrophoneWorker(QRunnable):
    def __init__(self, signals, device_index=None):
        super().__init__()
        self.signals = signals
        self._is_running = True
        self.device_index = device_index
        # for google transcription api
        self.recognizer = sr.Recognizer()

    @Slot()
    def run(self):
        self.signals.started.emit()
        
        # non blocking i/o
        p = pyaudio.PyAudio()
        stream = None
        
        # We capture small frames of audio to store in audio_frames
        audio_frames = []

        try:
            stream = p.open(format=FORMAT,
                            channels=CHANNELS,
                            rate=RATE,
                            input=True,
                            frames_per_buffer=CHUNK,
                            input_device_index=self.device_index)

            # Process chunks of 3 seconds at a time
            CHUNK_COUNT_TO_PROCESS = int(RATE / CHUNK * 3.0)
            
            while self._is_running:

                data = stream.read(CHUNK, exception_on_overflow=False)
                audio_frames.append(data)
                
                # Can we process?
                if len(audio_frames) >= CHUNK_COUNT_TO_PROCESS:
                    self._process_chunk(audio_frames,p)
                    audio_frames = [] # reset
                
            # Process remaining chunks if stop recording
            if audio_frames:
                self._process_chunk(audio_frames,p)

        except Exception as e:
            self.signals.error.emit(f"PyAudio Stream Error: {e}")
            
        finally:
            if stream:
                stream.stop_stream()
                stream.close()
            p.terminate()
            
        self.signals.stopped.emit()

    def _process_chunk(self, audio_frames, p):
        # 1. Combine raw audio bytes from the buffer
        raw_data = b''.join(audio_frames)

        # 2. Convert raw bytes to sr.AudioData object needed by recognize_google
        # SR uses pyaudio so it fits nicely :D
        audio_data = sr.AudioData(raw_data, RATE, p.get_sample_size(FORMAT))

        try:
            # Transcribe with Google API
            text = self.recognizer.recognize_google(audio_data, language=LANGUAGE_CODE)
            
            if text:
                self.signals.text.emit(text + " ") 
                
        except sr.UnknownValueError:
            pass
        except sr.RequestError as e:
            # Emit error but don't stop the worker
            self.signals.error.emit(f"Google API Request Error: {e}. Check internet connection.")
        except Exception as e:
            self.signals.error.emit(f"An unexpected error occurred during processing: {e}")

    def stop_recording(self):
        self._is_running = False


class Microphone(QObject):
    text = Signal(str)
    error = Signal(str)
    started = Signal()
    stopped = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.threadpool = QThreadPool.globalInstance()
        self.worker = None

    def toggle(self):
        if self.worker is not None and self.worker._is_running:
            self.stop()
        else:
            self.start()

    def stop(self):
        if self.worker is not None and self.worker._is_running:
            self.worker.stop_recording()

    def start(self):
        if self.worker is None or not self.worker._is_running:
            worker_signals = MicrophoneSignals()
            
            worker_signals.text.connect(self.text.emit)
            worker_signals.error.connect(self.error.emit)
            worker_signals.started.connect(self.started.emit)
            
            def cleanup():
                self.worker = None
                self.stopped.emit()

            worker_signals.stopped.connect(cleanup)
            
            self.worker = MicrophoneWorker(worker_signals)
            self.worker.setAutoDelete(True) 
            self.threadpool.start(self.worker)