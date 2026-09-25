# frontend/speech_handler.py
import io
import speech_recognition as sr

def transcribe_audio_bytes(audio_bytes: bytes) -> str:
    """
    Converts raw PCM WAV audio bytes directly into text.
    """
    recognizer = sr.Recognizer()
    
    try:
        audio_file = io.BytesIO(audio_bytes)
        with sr.AudioFile(audio_file) as source:
            audio_data = recognizer.record(source)
            return recognizer.recognize_google(audio_data)
            
    except sr.UnknownValueError:
        return "ERROR: Could not understand the audio clearly. Please try speaking again."
    except sr.RequestError as e:
        return f"ERROR: Speech recognition service unavailable: {e}"
    except Exception as e:
        return f"ERROR: Audio processing failed - {e}"