from pydub import AudioSegment
import os, uuid

def mp3_to_wav(src_path: str) -> str:
    """Конвертирует mp3 во временный wav, возвращает путь к wav."""
    sound = AudioSegment.from_mp3(src_path)
    wav_temp = f"{os.path.splitext(src_path)[0]}_tmp.wav"
    sound.export(wav_temp, format="wav")
    return wav_temp