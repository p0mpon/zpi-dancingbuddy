"""
Fake rows shaped like the VIDEO table, used by the API until the Video model
exists. Delete this module once the views query the database.
"""

import math

JOINTS = ['left_knee', 'right_knee', 'left_hip', 'right_hip', 'left_elbow', 'right_elbow']


def _fake_frames(seconds, fps=30):
    """A big_ass_json: a list of Frame dicts (zpi_app/zpi_app/video_frame_model.py)."""
    return [
        {
            'frame_id': frame_id,
            'timestamp': round(frame_id / fps, 4),
            'joints': {
                name: {
                    'angle': round(90 + 45 * math.sin(frame_id / fps * 2 + i), 2),
                    'angular_velocity': None,
                    'angular_acceleration': None,
                    'visibility': 0.95,
                }
                for i, name in enumerate(JOINTS)
            },
            'hip_rotation': None,
            'hip_height': None,
        }
        for frame_id in range(seconds * fps)
    ]


VIDEOS = [
    {
        'id': 1,
        'title': 'Salsa basic step',
        'user_id': 1,
        'big_ass_json': _fake_frames(seconds=10),
        'path_to_resource': 'videos/salsa.mp4',
        'file_size': 48_213_504.0,
    },
    {
        'id': 2,
        'title': 'Bachata turn practice (not analysed yet)',
        'user_id': 1,
        'big_ass_json': None,
        'path_to_resource': 'videos/bachata.mp4',
        'file_size': 31_457_280.0,
    },
]


def find_video(video_id):
    return next((video for video in VIDEOS if video['id'] == int(video_id)), None)
