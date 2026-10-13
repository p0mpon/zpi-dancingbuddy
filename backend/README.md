I used python 3.14.5 for the venv. Check if other python versions will work too (3.14 probably will). 

Create venv ```python -m venv .venv``` and activate it.

Run ```pip install -r backend_requirements.txt``` to install the requirements inside your venv.

Activation command for fish users: ```source backend/.venv/bin/activate.fish``` (run from main)

### Essentia usage guide:

insert music into essentia/insert_example_music

load the track using ```MusicLoader.load_track()```

analyse the track using MusicProcessor, available methods:
* ```song_segmentation()```
* ```beat_detection()```
* ```onset_detection()```