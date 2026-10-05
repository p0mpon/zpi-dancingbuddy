import music_loader as ml
import music_processor

loader = ml.MusicLoader("./insert_example_music", "./output_example_music")

audio = loader.load_track("your_song.mp3")

processor = music_processor.MusicProcessor(44100, 1024, 512)


segments = processor.song_segmentation(audio)
bpm, beats = processor.beat_detection(audio, 'multifeature')
onsets = processor.onset_detection(audio, 'hfc')
# onsets = processor.superflux_detection(audio)

processor.play_and_visualize(audio, segments = segments, onsets = onsets)


