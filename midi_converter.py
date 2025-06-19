import numpy as np
import soundfile as sf
import mido

def convert_wav_to_midi(wav_path, midi_path):
    y, sr = sf.read(wav_path)
    if len(y.shape) > 1:
        y = np.mean(y, axis=1)

    frame_size = 2048
    hop_length = 512
    threshold = 0.02
    window = np.hanning(frame_size)
    onsets = []

    energy = []
    pitches = []
    times = []

    for i in range(0, len(y) - frame_size, hop_length):
        frame = y[i:i+frame_size] * window
        mag = np.abs(np.fft.rfft(frame))
        energy_val = np.sum(mag)
        energy.append(energy_val)

        freq_res = sr / frame_size
        peak_index = np.argmax(mag)
        freq = peak_index * freq_res
        pitch = 69 + 12 * np.log2(freq / 440.0) if freq > 0 else 60
        pitches.append(int(round(pitch)))
        times.append(i / sr)

    energy = np.array(energy)
    energy_diff = np.diff(energy, prepend=0)

    for i in range(1, len(energy_diff)):
        if energy_diff[i] > threshold and energy_diff[i - 1] <= threshold:
            t = times[i]
            note = pitches[i]
            onsets.append((t, note))

    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)

    prev_ticks = 0
    for t, note in onsets:
        ticks = int(mido.second2tick(t, 480, mido.bpm2tempo(120)))
        delta = ticks - prev_ticks
        track.append(mido.Message('note_on', note=note, velocity=64, time=delta))
        track.append(mido.Message('note_off', note=note, velocity=64, time=100))
        prev_ticks = ticks

    mid.save(midi_path)
