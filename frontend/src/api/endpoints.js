export const API_ENDPOINTS = {
    "register": "register/",
    "login": "login/",
    "logout": "logout/",
    "user": "user/",

    "videos": "videos/",                  // GET, POST
    "video_details": (id) => `videos/${id}/`, // GET, PATCH, DELETE
    "video_analysis": (id) => `videos/${id}/analysis/`, // GET
    "video_stream": (id) => `videos/${id}/stream/`,
    "video_thumbnail": (id) => `videos/${id}/thumbnail/`,
    "dance_attempts": "dance-attempts/", // POST
    "dance_attempt_status": (taskId) => `dance-attempts/${taskId}/status/`, // GET
};